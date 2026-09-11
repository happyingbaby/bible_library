from sqlalchemy import select, func
from app import database
from app.models import Testament as BibleTestament, Book, Chapter
from conftest import login


def test_catalog_seed(client, admin):
    data = client.get('/api/bible/catalog').json()
    assert [(t['code'], len(t['books'])) for t in data] == [('OT', 39), ('NT', 27)]
    assert data[0]['books'][0] == dict(code='Gen', name='创世记', chapters=50, position=1)
    chapters = client.get('/api/bible/books/Gen/chapters').json()
    assert len(chapters) == 50
    assert chapters[0]['reference_verse_count'] == 31
    assert chapters[0]['stored_count'] == 0
    assert chapters[1]['reference_verse_count'] is None
    with database.factory() as db:
        assert db.scalar(select(func.count()).select_from(BibleTestament)) == 2
        assert db.scalar(select(func.count()).select_from(Book)) == 66
        assert db.scalar(select(func.count()).select_from(Chapter)) == 1189


def test_verse_edits_conflict_import_and_backup(client, admin):
    metadata = dict(code='test-zh', name='测试译本', language='zh', source='测试来源')
    result = client.post('/api/translations', json=metadata)
    assert result.status_code == 200
    tid = result.json()['id']
    assert client.post('/api/translations', json=metadata).status_code == 409
    path = f'/api/bible/translations/{tid}/Gen/1'
    assert client.put(path+'/1', json=dict(text=' ', revision=1)).status_code == 422
    assert client.put(f'/api/bible/translations/{tid}/Gen/51/1', json=dict(text='无效', revision=1)).status_code == 422
    assert client.put(path+'/1', json=dict(text='测试正文😀', revision=1)).json()['revision'] == 2
    assert client.put(path+'/1', json=dict(text='过期更新', revision=1)).status_code == 409
    preview = client.post('/api/translations/preview', json={**metadata, 'verses':[dict(book='Gen', chapter=1, verse=1, text='待导入内容')]}).json()
    assert client.put(path+'/1', json=dict(text='修改后😀', revision=2)).json()['revision'] == 3
    assert client.post('/api/translations/confirm', json=dict(preview_id=preview['preview_id'])).status_code == 409
    assert client.get('/api/verses', params=dict(translation_id=tid, book='Gen', chapter=1, start=1, end=1)).json()[0]['text'] == '修改后😀'
    assert client.get('/api/bible/books/Gen/chapters', params=dict(translation_id=tid)).json()[0]['stored_count'] == 1
    backup = client.get('/api/backups').content
    assert client.delete(path+'/1?revision=2').status_code == 409
    assert client.delete(path+'/1?revision=3').json()['revision'] == 4
    assert client.get(path).json()['verses'] == []
    preview = client.post('/api/backups/preview', files={'file':('b.zip', backup)}).json()
    assert client.post('/api/backups/restore', json=dict(preview_id=preview['preview_id'])).status_code == 200
    login(client, 'admin', 'admin-password-123')
    assert client.get(path).json()['verses'][0]['text'] == '修改后😀'
    assert len(client.get('/api/bible/catalog').json()[0]['books']) == 39


def test_reader_cannot_manage_verses(client, admin):
    tid = client.post('/api/translations', json=dict(code='reader-test', name='测试', language='zh')).json()['id']
    assert client.post('/api/users', json=dict(username='reader', display_name='读者', password='reader-password-123', role='reader')).status_code == 200
    login(client, 'reader', 'reader-password-123')
    result = client.post('/api/password', json=dict(old_password='reader-password-123', new_password='reader-new-password-123')).json()
    client.headers['Authorization'] = 'Bearer ' + result['token']
    assert client.get('/api/bible/catalog').status_code == 200
    assert client.post('/api/translations', json=dict(code='x', name='测试', language='zh')).status_code == 403
    assert client.put(f'/api/bible/translations/{tid}/Gen/1/1', json=dict(text='无权限', revision=1)).status_code == 403
    assert client.delete(f'/api/bible/translations/{tid}/Gen/1/1?revision=1').status_code == 403


def test_upgrade_existing_0001_preserves_verses(tmp_path):
    import sqlalchemy as sa
    from alembic import command
    from alembic.config import Config
    from pathlib import Path
    from app.models import Base
    engine = sa.create_engine('sqlite:///' + str(tmp_path / 'old.sqlite'))
    old = sa.MetaData()
    for table in Base.metadata.sorted_tables:
        if not table.name.startswith('bible_'):
            table.to_metadata(old)
    verses = old.tables['verses']
    fk = next(c for c in verses.constraints if c.name == 'fk_verses_chapter')
    verses.constraints.remove(fk)
    for element in fk.elements:
        verses.foreign_keys.discard(element)
        element.parent.foreign_keys.discard(element)
    old.create_all(engine)
    with engine.begin() as conn:
        conn.execute(old.tables['translations'].insert(), dict(id=1, code='old', name='原译本', language='zh', source='', revision=7))
        conn.execute(verses.insert(), dict(id=1, translation_id=1, book='Gen', chapter=1, verse=1, text='已有正文😀'))
        config = Config()
        config.set_main_option('script_location', str(Path(__file__).resolve().parents[1] / 'migrations'))
        config.attributes['connection'] = conn
        command.stamp(config, '0001')
        command.upgrade(config, 'head')
        assert conn.execute(sa.text('SELECT text FROM verses')).scalar() == '已有正文😀'
        assert conn.execute(sa.text('SELECT revision FROM translations')).scalar() == 7
        assert conn.execute(sa.text('SELECT count(*) FROM bible_chapters')).scalar() == 1189
        assert any(f['name']=='fk_verses_chapter' for f in sa.inspect(conn).get_foreign_keys('verses'))
    engine.dispose()


def test_delete_preflight(client):
    response = client.options('/api/bible/translations/1/Gen/1/1', headers={
        'Origin':'http://127.0.0.1:5173', 'Access-Control-Request-Method':'DELETE',
        'Access-Control-Request-Headers':'authorization,x-app-key'})
    assert response.status_code == 200
