"""Run integration checks against an explicitly disposable MySQL test database."""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'backend'))
url = os.environ.get('MYSQL_TEST_URL')
if not url or 'bible_test' not in url:
    raise SystemExit('Set MYSQL_TEST_URL to the disposable bible_test database')
os.environ['DATABASE_URL'] = url
os.environ['BIBLE_DATA_DIR'] = '/private/tmp/bible-mysql-smoke'
os.environ['BIBLE_APP_KEY'] = 'mysql-smoke-key'
from fastapi.testclient import TestClient
from app.main import app
from app import database
from app.models import Base, Guard
# Exercise the real upgrade path from a pre-catalog 0001 database.
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
candidate = sa.create_engine(url)
assert not sa.inspect(candidate).get_table_names(), 'Use a fresh bible_test database'
old = sa.MetaData()
for table in Base.metadata.sorted_tables:
    if not table.name.startswith('bible_'):
        table.to_metadata(old)
verse_table = old.tables['verses']
fk = next(c for c in verse_table.constraints if c.name == 'fk_verses_chapter')
verse_table.constraints.remove(fk)
for element in fk.elements:
    verse_table.foreign_keys.discard(element)
    element.parent.foreign_keys.discard(element)
old.create_all(candidate)
with candidate.begin() as conn:
    conn.execute(old.tables['guards'].insert(), {'id':1})
    conn.execute(old.tables['translations'].insert(), {'id':1, 'code':'legacy', 'name':'旧译本', 'language':'zh', 'source':'', 'revision':5})
    conn.execute(verse_table.insert(), {'translation_id':1, 'book':'Gen', 'chapter':1, 'verse':1, 'text':'升级前经文😀'})
    config = Config()
    config.set_main_option('script_location', str(Path(__file__).resolve().parents[1] / 'migrations'))
    config.attributes['connection'] = conn
    command.stamp(config, '0001')
candidate.dispose()
with TestClient(app, headers={'X-App-Key':'mysql-smoke-key'}) as c:
    assert c.get('/api/status').json()['connected'], c.get('/api/status').text
    # This script refuses to overwrite a nonempty DB.
    assert not c.get('/api/status').json()['initialized'], 'Use a fresh bible_test database'
    result = c.post('/api/setup',json={'username':'admin','display_name':'测试管理员','password':'mysql-smoke-password'})
    assert result.status_code == 200, result.text
    c.headers['Authorization'] = 'Bearer '+result.json()['token']
    result = c.post('/api/lectures',json={'title':'MySQL 中文讲义😀','markdown':'# 中文\n\n【创1:1-5上】','tags':['中文😀']})
    assert result.status_code == 200, result.text
    lecture = result.json()
    assert lecture['references'][0]['end'] == 5
    assert c.get('/api/bible/translations/1/Gen/1').json() == {'revision':5, 'verses':[{'verse':1, 'text':'升级前经文😀'}]}
    catalog = c.get('/api/bible/catalog').json()
    assert [len(t['books']) for t in catalog] == [39, 27]
    chapters = c.get('/api/bible/books/Gen/chapters').json()
    assert len(chapters) == 50 and chapters[0]['reference_verse_count'] == 31
    result = c.post('/api/translations', json={'code':'mysql-test', 'name':'测试译本', 'language':'zh'})
    assert result.status_code == 200, result.text
    verse_path = f"/api/bible/translations/{result.json()['id']}/Gen/1/1"
    result = c.put(verse_path, json={'text':'测试经文😀', 'revision':1})
    assert result.status_code == 200, result.text
    assert c.put(verse_path, json={'text':'过期修改', 'revision':1}).status_code == 409
    data = c.get('/api/backups')
    assert data.status_code == 200, data.text
    restore = c.post('/api/backups/preview',files={'file':('backup.zip',data.content)})
    assert restore.status_code == 200, restore.text
    result = c.post('/api/backups/restore',json={'preview_id':restore.json()['preview_id']})
    assert result.status_code == 200, result.text
    assert c.get('/api/me').status_code == 401
    result = c.post('/api/login',json={'username':'admin','password':'mysql-smoke-password'})
    assert result.status_code == 200
    c.headers['Authorization'] = 'Bearer '+result.json()['token']
    assert c.get('/api/lectures').json()[0]['title'] == 'MySQL 中文讲义😀'
    assert c.get(verse_path.rsplit('/', 1)[0]).json()['verses'][0]['text'] == '测试经文😀'
    print('MySQL migration, utf8mb4, reference index, backup restore and session revocation passed.')
