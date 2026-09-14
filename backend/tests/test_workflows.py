import io
import json
import zipfile
import subprocess
from pathlib import Path
import pytest
from sqlalchemy import select
from app import database
from app.models import Reference
from app.modules.references import render
from conftest import login


def create_lecture(client, text='# 第一课\n\n阅读【创1:1-3】。'):
    response = client.post('/api/lectures', json={'title': '创世记讲义', 'author': '张牧师', 'sermon_date': '2026-09-12', 'markdown': text, 'category': '旧约', 'tags': ['创世记']})
    assert response.status_code == 200, response.text
    return response.json()


def create_reader(client):
    response = client.post('/api/users', json={'username': 'reader', 'display_name': '阅读者', 'password': 'initial-password-123', 'role': 'reader'})
    assert response.status_code == 200, response.text
    return response.json()


def become_reader(client):
    login(client, 'reader', 'initial-password-123')
    response = client.post('/api/password', json={'old_password': 'initial-password-123', 'new_password': 'reader-password-456'})
    assert response.status_code == 200
    client.headers['Authorization'] = 'Bearer ' + response.json()['token']


def test_setup_login_and_required_password(client, admin):
    assert client.post('/api/setup', json={'username': 'other', 'display_name': '其他', 'password': 'password-12345'}).status_code == 409
    create_reader(client)
    first = login(client, 'reader', 'initial-password-123')
    assert first['user']['must_change_password'] is True
    assert client.get('/api/lectures').status_code == 403
    assert client.get('/api/translations').status_code == 403
    assert client.post('/api/password', json={'old_password': 'incorrect', 'new_password': 'new-password-123'}).status_code == 400
    become_reader(client)
    assert client.get('/api/lectures').status_code == 200
    assert client.get('/api/users').status_code == 403
    assert client.get('/api/status', headers={'X-App-Key': 'bad'}).status_code == 403


def test_logout_and_relogin_after_initial_setup(client):
    assert client.get('/api/status').json()['initialized'] is False
    setup = client.post('/api/setup', json={'username': 'admin', 'display_name': '管理员', 'password': 'admin-password-123'})
    assert setup.status_code == 200
    client.headers['Authorization'] = 'Bearer ' + setup.json()['token']
    create_reader(client)
    assert client.post('/api/logout').status_code == 200
    assert client.get('/api/me').status_code == 401
    assert client.get('/api/status').json()['initialized'] is True
    assert login(client, 'admin', 'admin-password-123')['user']['role'] == 'admin'
    assert client.post('/api/logout').status_code == 200
    assert login(client, 'reader', 'initial-password-123')['user']['must_change_password'] is True
    become_reader(client)
    assert client.post('/api/logout').status_code == 200
    assert login(client, 'reader', 'reader-password-456')['user']['must_change_password'] is False
    assert client.get('/api/lectures').status_code == 200


def test_reader_visibility_and_direct_write_access(client, admin):
    lecture = create_lecture(client)
    create_reader(client)
    become_reader(client)
    reader_token = client.headers['Authorization']
    assert client.get('/api/lectures').json() == []
    assert client.get(f'/api/lectures/{lecture["id"]}').status_code == 404
    forbidden = [('POST', '/api/users', {'username': 'evil', 'display_name': 'evil', 'password': 'password-123'}), ('POST', '/api/lectures', {'title': 'evil', 'markdown': ''}), ('PUT', f'/api/lectures/{lecture["id"]}', {'title': 'evil', 'markdown': '', 'revision': 1}), ('PATCH', f'/api/lectures/{lecture["id"]}/publish', {'published': True}), ('PATCH', f'/api/lectures/{lecture["id"]}/trash', {'deleted': True}), ('POST', '/api/render', {'markdown': ''})]
    for method, path, data in forbidden:
        assert client.request(method, path, json=data).status_code == 403, path
    for path in ('/api/backups', f'/api/lectures/{lecture["id"]}/history', f'/api/lectures/{lecture["id"]}/export', f'/api/lectures/{lecture["id"]}/original'):
        assert client.get(path).status_code == 403
    assert client.post('/api/imports/preview', files={'file': ('a.md', b'text')}).status_code == 403
    assert client.post('/api/backups/preview', files={'file': ('a.zip', b'bad')}).status_code == 403
    client.headers['Authorization'] = 'Bearer ' + admin['token']
    assert client.patch(f'/api/lectures/{lecture["id"]}/publish', json={'published': True}).status_code == 200
    client.headers['Authorization'] = reader_token
    assert len(client.get('/api/lectures?q=创世').json()) == 1
    assert client.get(f'/api/lectures/{lecture["id"]}').status_code == 200
    client.headers['Authorization'] = 'Bearer ' + admin['token']
    client.patch(f'/api/lectures/{lecture["id"]}/publish', json={'published': False})
    client.headers['Authorization'] = reader_token
    assert client.get(f'/api/lectures/{lecture["id"]}').status_code == 404
    client.headers['Authorization'] = 'Bearer ' + admin['token']
    client.patch(f'/api/lectures/{lecture["id"]}/publish', json={'published': True})
    client.patch(f'/api/lectures/{lecture["id"]}/trash', json={'deleted': True})
    client.headers['Authorization'] = reader_token
    assert client.get('/api/lectures?trash=true').json() == []
    assert client.get(f'/api/lectures/{lecture["id"]}').status_code == 404


def test_revocation_and_last_admin(client, admin):
    reader = create_reader(client)
    become_reader(client)
    reader_token = client.headers['Authorization']
    client.headers['Authorization'] = 'Bearer ' + admin['token']
    assert client.patch(f'/api/users/{admin["user"]["id"]}', json={'active': False}).status_code == 409
    assert client.patch(f'/api/users/{reader["id"]}', json={'active': False}).status_code == 200
    assert client.get('/api/me', headers={'Authorization': reader_token}).status_code == 401
    client.patch(f'/api/users/{reader["id"]}', json={'active': True})
    login(client, 'reader', 'reader-password-456')
    reader_token = client.headers['Authorization']
    client.headers['Authorization'] = 'Bearer ' + admin['token']
    assert client.post(f'/api/users/{reader["id"]}/reset-password', json={'password': 'reset-password-789'}).status_code == 200
    assert client.get('/api/me', headers={'Authorization': reader_token}).status_code == 401
    result = login(client, 'reader', 'reset-password-789')
    assert result['user']['must_change_password'] is True

@pytest.mark.parametrize('raw,end', [('【创1:1】',1),('【创1:1-3】',3),('【创1:1-5上】',5),('（创1:1）',1),('（创1:1-3）',3),('（创1:1-5a）',5),('( 创 1 ： 1 – 3 )',3)])
def test_six_reference_forms(raw,end):
    result = render(raw)
    assert len(result['references']) == 1
    ref = result['references'][0]
    assert (ref['book'],ref['book_name'],ref['chapter'],ref['start'],ref['end'],ref['status']) == ('Gen','创世记',1,1,end,'valid')


@pytest.mark.parametrize('raw', ['【约壹4:9-10】', '【約壹4:9-10】'])
def test_first_john_financial_numeral_alias(raw):
    result = render(raw)
    assert len(result['references']) == 1
    ref = result['references'][0]
    assert (ref['book'], ref['book_name'], ref['chapter'], ref['start'], ref['end'], ref['status']) == (
        '1John', '约翰一书', 4, 9, 10, 'valid'
    )


@pytest.mark.parametrize(
    ('raw', 'book', 'book_name'),
    [
        ('【约贰1:1-2】', '2John', '约翰二书'),
        ('【約貳1:1-2】', '2John', '约翰二书'),
        ('【约叁1:1-2】', '3John', '约翰三书'),
        ('【約參1:1-2】', '3John', '约翰三书'),
    ],
)
def test_second_and_third_john_financial_numeral_aliases(raw, book, book_name):
    result = render(raw)
    assert len(result['references']) == 1
    ref = result['references'][0]
    assert (ref['book'], ref['book_name'], ref['chapter'], ref['start'], ref['end'], ref['status']) == (
        book, book_name, 1, 1, 2, 'valid'
    )


def test_reference_exclusions_and_invalid():
    result = render('`【创1:1】` [【创1:2】](https://example.com)\n\n```\n【创1:3】\n```\n\n【创1:5-1】【未知1:1】【创51:1】【创1:1】【创1:1】\n\n<script>alert(1)</script>')
    assert len(result['references']) == 5
    assert [r['status'] for r in result['references']] == ['invalid','invalid','invalid','valid','valid']
    assert '<script>' not in result['html']
    assert [r['ordinal'] for r in result['references']] == list(range(5))


def test_edit_history_export_and_index(client, admin):
    lecture = create_lecture(client)
    assert lecture['author'] == '张牧师' and lecture['sermon_date'] == '2026-09-12'
    response = client.put(f'/api/lectures/{lecture["id"]}', json={'title':'修改','author':'李牧师','sermon_date':'2026-09-13','markdown':'新内容（约3:16）','revision':lecture['revision'],'category':'新约','tags':['标签']})
    assert response.status_code == 200, response.text
    assert response.json()['author'] == '李牧师' and response.json()['sermon_date'] == '2026-09-13'
    assert len(client.get('/api/lectures?q=李牧师').json()) == 1
    assert client.put(f'/api/lectures/{lecture["id"]}', json={'title':'过期','markdown':'','revision':1}).status_code == 409
    versions = client.get(f'/api/lectures/{lecture["id"]}/history').json()
    assert len(versions) == 2
    result = client.post(f'/api/lectures/{lecture["id"]}/history/{versions[-1]["id"]}/restore').json()
    assert result['markdown'] == lecture['markdown']
    assert result['author'] == '张牧师' and result['sermon_date'] == '2026-09-12'
    assert result['revision'] == 3
    assert len(client.get(f'/api/lectures/{lecture["id"]}/history').json()) == 3
    assert client.get(f'/api/lectures/{lecture["id"]}/export').text == lecture['markdown']
    with database.factory() as db:
        refs = list(db.scalars(select(Reference)))
        assert len(refs) == 1 and refs[0].payload['book'] == 'Gen'
    database.connect(__import__('os').environ['DATABASE_URL'])
    assert client.get(f'/api/lectures/{lecture["id"]}').json()['revision'] == 3


def test_markdown_import_and_duplicates(client, admin):
    markdown = '# 标题\n\n**完整文字**\n\n- 列表\n\n【创1:1】'
    preview = client.post('/api/imports/preview', files={'file':('讲义.md',markdown.encode(),'text/markdown')})
    assert preview.status_code == 200, preview.text
    assert preview.json()['markdown'] == markdown
    confirmed = client.post('/api/imports/confirm', json={'preview_id':preview.json()['preview_id'],'title':'导入讲义','author':'王牧师','sermon_date':'2026-09-10','category':'主日讲道','tags':['恩典','约翰福音']})
    assert confirmed.status_code == 200
    assert confirmed.json()['category'] == '主日讲道'
    assert confirmed.json()['tags'] == ['恩典', '约翰福音']
    assert confirmed.json()['published'] is False
    assert confirmed.json()['author'] == '王牧师' and confirmed.json()['sermon_date'] == '2026-09-10'
    assert client.get(f'/api/lectures/{confirmed.json()["id"]}/original').content == markdown.encode()
    assert client.post('/api/imports/confirm', json={'preview_id':preview.json()['preview_id'],'title':'再次确认'}).status_code == 404
    assert client.post('/api/imports/preview', files={'file':('bad.docx',b'bad')}).status_code == 422
    assert client.post('/api/imports/preview', files={'file':('bad.md',b'\xff')}).status_code == 422


def test_real_docx_conversion(client, admin, tmp_path):
    import pypandoc
    source = tmp_path / 'source.md'
    source.write_text('# 标题\n\n正文与**加粗**。\n\n1. 第一项\n2. 第二项\n\n【创1:1-5上】', encoding='utf-8')
    target = tmp_path / 'source.docx'
    subprocess.run([pypandoc.get_pandoc_path(),str(source),'-o',str(target)],check=True)
    result = client.post('/api/imports/preview', files={'file':('source.docx',target.read_bytes())})
    assert result.status_code == 200, result.text
    text = result.json()['markdown']
    assert '# 标题' in text and '**加粗**' in text and '第一项' in text and '第二项' in text
    assert '【创1:1-5上】' in text
    assert not result.json()['warnings']


def test_compatible_docx_conversion(client, admin, tmp_path, monkeypatch):
    import pypandoc
    source = tmp_path / 'compatible.md'
    source.write_text('# 标题\n\n正文与**加粗**。\n\n1. 第一项\n2. 第二项\n\n【创1:1-5上】', encoding='utf-8')
    target = tmp_path / 'compatible.docx'
    subprocess.run([pypandoc.get_pandoc_path(), str(source), '-o', str(target)], check=True)
    monkeypatch.setenv('BIBLE_FORCE_BASIC_DOCX', '1')
    result = client.post('/api/imports/preview', files={'file': ('compatible.docx', target.read_bytes())})
    assert result.status_code == 200, result.text
    text = result.json()['markdown']
    assert '# 标题' in text and '**加粗**' in text
    assert '1. 第一项' in text and '1. 第二项' in text
    assert '【创1:1-5上】' in text
    assert any('兼容转换器' in message for message in result.json()['warnings'])


def scripture_payload():
    return {'code':'test-zh','name':'测试译本','language':'zh','source':'测试数据','verses':[{'book':'Gen','chapter':1,'verse':1,'text':'测试第一节'},{'book':'Gen','chapter':1,'verse':3,'text':'测试第三节'}]}


def test_scripture_diff_validation_and_missing(client, admin):
    payload = scripture_payload()
    preview = client.post('/api/translations/preview', json=payload)
    assert preview.status_code == 200, preview.text
    assert '2' in preview.json()['warnings'][0]
    assert client.get('/api/translations').json() == []
    assert client.post('/api/translations/confirm',json={'preview_id':preview.json()['preview_id']}).status_code == 200
    translation = client.get('/api/translations').json()[0]
    verses = client.get(f'/api/verses?translation_id={translation["id"]}&book=Gen&chapter=1&start=1&end=3').json()
    assert verses[1]['missing'] and verses[0]['text'] == '测试第一节'
    payload['verses'][0]['text'] = '修改第一节'
    payload['verses'].pop()
    next_preview = client.post('/api/translations/preview',json=payload).json()
    assert next_preview['summary'] == {'added':0,'changed':1,'removed':1}
    concurrent = client.post('/api/translations/preview',json=payload).json()
    assert client.post('/api/translations/confirm',json={'preview_id':next_preview['preview_id']}).status_code == 200
    assert client.post('/api/translations/confirm',json={'preview_id':concurrent['preview_id']}).status_code == 409
    payload['verses'].append(payload['verses'][0])
    assert client.post('/api/translations/preview',json=payload).status_code == 422
    payload['verses'] = [{'book':'Unknown','chapter':1,'verse':1,'text':'x'}]
    assert client.post('/api/translations/preview',json=payload).status_code == 422


def test_backup_restore_roundtrip(client, admin):
    preview = client.post('/api/imports/preview', files={'file':('original.md', '# 原始【创1:1】'.encode())}).json()
    lecture = client.post('/api/imports/confirm',json={'preview_id':preview['preview_id'],'title':'原始','author':'张牧师','sermon_date':'2026-09-12'}).json()
    create_reader(client)
    p = client.post('/api/translations/preview',json=scripture_payload()).json()
    client.post('/api/translations/confirm',json={'preview_id':p['preview_id']})
    backup = client.get('/api/backups')
    assert backup.status_code == 200, backup.text if backup.status_code != 200 else ''
    with zipfile.ZipFile(io.BytesIO(backup.content)) as archive:
        data = json.loads(archive.read('database.json'))
        assert data['version'] == 2
        assert data['tables']['lectures'][0]['author'] == '张牧师'
        assert 'sessions' not in data['tables'] and 'password' not in data['tables']['users'][0]
        original = archive.read('originals/' + data['tables']['lectures'][0]['original_file'])
    legacy = io.BytesIO()
    data['version'] = 1
    for table_name in ('lectures', 'histories'):
        for row in data['tables'][table_name]:
            row.pop('author')
            row.pop('sermon_date')
    with zipfile.ZipFile(legacy, 'w') as archive:
        archive.writestr('database.json', json.dumps(data))
        archive.writestr('originals/' + data['tables']['lectures'][0]['original_file'], original)
    assert client.post('/api/backups/preview', files={'file': ('legacy.zip', legacy.getvalue())}).status_code == 200
    create_lecture(client,'new')
    restore = client.post('/api/backups/preview',files={'file':('backup.zip',backup.content)})
    assert restore.status_code == 200, restore.text
    result = client.post('/api/backups/restore',json={'preview_id':restore.json()['preview_id']})
    assert result.status_code == 200, result.text
    assert Path(result.json()['safety_backup']).is_file()
    assert client.get('/api/me').status_code == 401
    login(client,'admin','admin-password-123')
    assert len(client.get('/api/lectures').json()) == 1
    assert len(client.get('/api/users').json()) == 2
    assert client.get(f'/api/lectures/{lecture["id"]}/original').content == '# 原始【创1:1】'.encode()
    assert len(client.get(f'/api/lectures/{lecture["id"]}/history').json()) == 1


def test_bad_backup_rejected_without_changes(client, admin):
    create_lecture(client)
    archive = io.BytesIO()
    with zipfile.ZipFile(archive,'w') as output:
        output.writestr('../escape','bad')
    assert client.post('/api/backups/preview',files={'file':('bad.zip',archive.getvalue())}).status_code == 422
    assert len(client.get('/api/lectures').json()) == 1


def test_reader_cannot_reconfigure_database_or_import_scripture(client, admin):
    create_reader(client)
    become_reader(client)
    assert client.post('/api/connection', json={'host':'127.0.0.1','port':3307,'username':'root','password':'x','database':'other'}).status_code == 403
    assert client.post('/api/translations/preview',json=scripture_payload()).status_code == 403
    assert client.post('/api/translations/confirm',json={'preview_id':'a'*32}).status_code == 403
    assert client.post('/api/backups/restore',json={'preview_id':'a'*32}).status_code == 403


def test_remote_mode_disables_connection_configuration(client, monkeypatch):
    from app import main
    monkeypatch.setattr(main, 'ALLOW_CONNECTION_CONFIG', False)
    response = client.post('/api/connection', json={
        'host':'127.0.0.1', 'port':3306, 'username':'root',
        'password':'x', 'database':'bible_library',
    })
    assert response.status_code == 403
    assert '服务器管理员' in response.json()['detail']


def test_backup_foreign_key_corruption_rejected(client, admin):
    lecture = create_lecture(client)
    raw = client.get('/api/backups').content
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        payload = json.loads(archive.read('database.json'))
    payload['tables']['lectures'][0]['created_by'] = 99999
    invalid = io.BytesIO()
    with zipfile.ZipFile(invalid,'w') as archive:
        archive.writestr('database.json',json.dumps(payload))
    assert client.post('/api/backups/preview',files={'file':('bad.zip',invalid.getvalue())}).status_code == 422
    assert client.get(f'/api/lectures/{lecture["id"]}').status_code == 200


def test_docx_unsupported_content_warns(client, admin, tmp_path):
    import pypandoc
    source = tmp_path / 'table.md'
    source.write_text('| 列一 | 列二 |\n|---|---|\n| 内容甲 | 内容乙 |\n')
    target = tmp_path / 'table.docx'
    subprocess.run([pypandoc.get_pandoc_path(),str(source),'-o',str(target)],check=True)
    result = client.post('/api/imports/preview',files={'file':('table.docx',target.read_bytes())})
    assert result.status_code == 200
    assert any('表格' in message for message in result.json()['warnings'])
    assert '内容甲' in result.json()['markdown'] and '内容乙' in result.json()['markdown']
