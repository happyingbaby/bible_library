from conftest import login


def lecture(client, markdown='# 标题\n\n第一段😀\n\n第二段【创1:1】'):
    row = client.post('/api/lectures', json={'title':'批注测试','markdown':markdown}).json()
    client.patch(f'/api/lectures/{row["id"]}/publish', json={'published':True})
    return row


def create(client, row, index=1, **extra):
    return client.post('/api/annotations', json=dict(lecture_id=row['id'],
        lecture_revision=row['revision'], paragraph_index=index, content='个人思考😀', **extra))


def test_owner_only_and_validation(client, admin):
    row=lecture(client)
    token=admin['token']
    for name in ('one','two'):
        client.post('/api/users',json=dict(username=name,display_name=name,password='initial-password',role='reader'))
    login(client,'one','initial-password')
    assert create(client,row).status_code==403
    changed=client.post('/api/password',json=dict(old_password='initial-password',new_password='new-password')).json()
    client.headers['Authorization']='Bearer '+changed['token']
    note=create(client,row).json()
    assert note['quote']=='第一段😀'
    assert create(client,row,user_id=1).status_code==422
    assert create(client,row, index=500).status_code==422
    assert client.put(f'/api/annotations/{note["id"]}',json={'content':'  ','revision':1}).status_code==422
    assert client.put(f'/api/annotations/{note["id"]}',json={'content':'编辑','revision':1}).json()['revision']==2
    assert client.put(f'/api/annotations/{note["id"]}',json={'content':'过期','revision':1}).status_code==409
    assert client.delete(f'/api/annotations/{note["id"]}?revision=1').status_code==409
    for name,password in [('admin','admin-password-123'),('two','initial-password')]:
        login(client,name,password)
        if name=='two':
            result=client.post('/api/password',json=dict(old_password=password,new_password='another-password')).json()
            client.headers['Authorization']='Bearer '+result['token']
        assert client.get('/api/annotations').json()==[]
        assert client.get(f'/api/annotations/{note["id"]}').status_code==404
        assert client.put(f'/api/annotations/{note["id"]}',json={'content':'越权','revision':2}).status_code==404
        assert client.delete(f'/api/annotations/{note["id"]}?revision=2').status_code==404
    login(client,'one','new-password')
    assert client.delete(f'/api/annotations/{note["id"]}?revision=2').status_code==200
    assert client.get('/api/annotations').json()==[]


def test_anchor_moves_changes_and_duplicates(client,admin):
    row=lecture(client)
    note=create(client,row).json()
    assert 'data-paragraph-index="1"' in row['html']
    def save(markdown):
        nonlocal row
        row=client.put(f'/api/lectures/{row["id"]}',json=dict(title=row['title'],markdown=markdown,revision=row['revision'])).json()
    save('新增段落\n\n'+row['markdown'])
    assert client.get(f'/api/annotations/{note["id"]}').json()['paragraph_index']==2
    save('第一段已修改')
    assert client.get(f'/api/annotations/{note["id"]}').json()['paragraph_index'] is None
    save('第一段😀\n\n第一段😀')
    assert client.get(f'/api/annotations/{note["id"]}').json()['paragraph_index'] is None
    repeated=create(client,row,index=1).json()
    assert repeated['paragraph_index']==1
    save('其他\n\n'+row['markdown'])
    assert client.get(f'/api/annotations/{repeated["id"]}').json()['paragraph_index'] is None
    save('第一段😀')
    assert client.get(f'/api/annotations/{repeated["id"]}').json()['paragraph_index'] is None
    old=dict(row);old['revision']=1
    assert create(client,old).status_code==409


def test_hidden_lecture_notes_remain_private_and_backup_safe(client,admin):
    row=lecture(client)
    client.post('/api/users',json=dict(username='reader',display_name='reader',password='initial-password',role='reader'))
    login(client,'reader','initial-password')
    changed=client.post('/api/password',json=dict(old_password='initial-password',new_password='reader-password')).json()
    client.headers['Authorization']='Bearer '+changed['token']
    note=create(client,row).json()
    login(client,'admin','admin-password-123')
    backup=client.get('/api/backups')
    import io,zipfile
    with zipfile.ZipFile(io.BytesIO(backup.content)) as archive:
        assert '个人思考' not in archive.read('database.json').decode()
    preview=client.post('/api/backups/preview',files={'file':('backup.zip',backup.content)}).json()
    assert client.post('/api/backups/restore',json={'preview_id':preview['preview_id']}).status_code==409
    client.patch(f'/api/lectures/{row["id"]}/publish',json={'published':False})
    login(client,'reader','reader-password')
    hidden=client.get('/api/annotations').json()[0]
    assert not hidden['available'] and hidden['quote']==''
    assert hidden['content']=='个人思考😀'
    assert create(client,row).status_code==404
    assert client.put(f'/api/annotations/{note["id"]}',json={'content':'保留笔记','revision':1}).status_code==200


def test_nested_markdown_paragraphs_and_pagination(client,admin):
    row=lecture(client,'# 标题\n\n- 列表一\n- 列表二\n\n> 引用段\n\n普通 **加粗** [链接](https://example.com)')
    assert len(row['paragraphs'])==5
    for i in range(5):
        assert create(client,row,index=i).status_code==200
    first=client.get('/api/annotations?limit=2').json()
    second=client.get('/api/annotations?limit=2&offset=2').json()
    assert len(first)==len(second)==2 and first[0]['id']!=second[0]['id']


def test_existing_database_migration(client,admin):
    from pathlib import Path
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import inspect
    from app import database
    row=lecture(client)
    config=Config()
    config.set_main_option('script_location',str(Path(__file__).resolve().parents[1]/'migrations'))
    with database.engine.begin() as connection:
        config.attributes['connection']=connection
        command.downgrade(config,'0003')
        assert 'annotations' not in inspect(connection).get_table_names()
        command.upgrade(config,'head')
        assert 'annotations' in inspect(connection).get_table_names()
    assert client.get(f'/api/lectures/{row["id"]}').json()['markdown']==row['markdown']
    assert create(client,row).status_code==200
