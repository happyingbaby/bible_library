import pytest
from test_workflows import create_lecture, create_reader, become_reader


def seed_translation(client, code='search-test'):
    preview = client.post('/api/translations/preview', json=dict(
        code=code, name='检索测试译本', language='zh', verses=[
            dict(book='Gen', chapter=1, verse=1, text='创造天地，创造万物。'),
            dict(book='Gen', chapter=1, verse=2, text='测试 100% 与 a_b 和 [字符]。'),
            dict(book='Exod', chapter=2, verse=3, text='创造的测试内容。'),
        ])).json()
    assert client.post('/api/translations/confirm', json=dict(preview_id=preview['preview_id'])).status_code == 200


def test_search_all_translations_pagination_and_literal_keywords(client, admin):
    seed_translation(client)
    seed_translation(client, 'search-second')
    page = client.get('/api/verses/search', params=dict(q=' 创造 ', limit=1)).json()
    assert page['total'] == 4
    first = page['items'][0]
    assert (first['book_name'], first['chapter'], first['verse']) == ('创世记', 1, 1)
    assert first['translation_name'] == '检索测试译本'
    remaining = client.get('/api/verses/search', params=dict(q='创造', offset=1)).json()
    assert len(remaining['items']) == 3
    assert first['id'] not in [v['id'] for v in remaining['items']]
    assert remaining['items'][-1]['book_name'] == '出埃及记'
    for keyword in ('%', '_', '[字符]'):
        result = client.get('/api/verses/search', params=dict(q=keyword)).json()
        assert result['total'] == 2
        assert all(keyword in v['text'] for v in result['items'])
    assert client.get('/api/verses/search?q=没有匹配').json() == dict(total=0, items=[])


@pytest.mark.parametrize('query', ['', '   ', 'a' * 201])
def test_search_rejects_invalid_input(client, admin, query):
    assert client.get('/api/verses/search', params=dict(q=query)).status_code == 422


def test_reverse_references_full_content_dedup_and_visibility(client, admin):
    path = '/api/verses/lectures?book=Gen&chapter=1&verse=2'
    published = create_lecture(client, '# 完整正文\n\n【创1:1-3】【创1:2】\n\n正文末尾。')
    client.patch(f'/api/lectures/{published["id"]}/publish', json=dict(published=True))
    draft = create_lecture(client, '草稿【创1:2上】')
    deleted = create_lecture(client, '已删除【创1:2】')
    client.patch(f'/api/lectures/{deleted["id"]}/trash', json=dict(deleted=True))
    create_lecture(client, '不匹配【创1:3】【创2:2】【出1:2】`【创1:2】`')
    rows = client.get(path).json()
    assert {l['id'] for l in rows} == {published['id'], draft['id']}
    assert len(rows) == 2
    full = next(l for l in rows if l['id'] == published['id'])
    assert full['markdown'] == published['markdown']
    assert '正文末尾。' in full['html']
    create_reader(client)
    become_reader(client)
    assert [l['id'] for l in client.get(path).json()] == [published['id']]
    assert client.get('/api/verses/search?q=创造').status_code == 200
    assert client.get('/api/verses/lectures?book=Gen&chapter=50&verse=1').json() == []


def test_reverse_references_follow_saved_content(client, admin):
    lecture = create_lecture(client, '【创1:1-3】')
    path = '/api/verses/lectures?book=Gen&chapter=1&verse=2'
    assert len(client.get(path).json()) == 1
    assert client.put(f'/api/lectures/{lecture["id"]}', json=dict(title='修改后', markdown='【创1:4】', revision=1)).status_code == 200
    assert client.get(path).json() == []
    histories = client.get(f'/api/lectures/{lecture["id"]}/history').json()
    original = next(h for h in histories if h['revision'] == 1)
    assert client.post(f'/api/lectures/{lecture["id"]}/history/{original["id"]}/restore').status_code == 200
    assert len(client.get(path).json()) == 1


def test_search_auth_and_invalid_verse(client):
    assert client.get('/api/verses/search?q=创造').status_code == 401
    assert client.get('/api/verses/lectures?book=Gen&chapter=1&verse=1').status_code == 401


@pytest.mark.parametrize('params', [dict(book='Unknown', chapter=1, verse=1), dict(book='Gen', chapter=51, verse=1), dict(book='Gen', chapter=1, verse=0)])
def test_reverse_references_validate_location(client, admin, params):
    assert client.get('/api/verses/lectures', params=params).status_code == 422
