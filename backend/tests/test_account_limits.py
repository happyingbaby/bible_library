import pytest
from conftest import login

@pytest.mark.parametrize('password', ['12345', 'x' * 129])
def test_setup_rejects_password_outside_limits(client, password):
    assert client.post('/api/setup', json=dict(username='admin', display_name='管理员', password=password)).status_code == 422


def test_six_character_password_lifecycle(client):
    result = client.post('/api/setup', json=dict(username='ADMIN', display_name='管理员', password='abc123'))
    assert result.status_code == 200
    client.headers['Authorization'] = 'Bearer ' + result.json()['token']
    user = client.post('/api/users', json=dict(username='Test_1.a-b', display_name='读者', password='def456'))
    assert user.status_code == 200
    assert user.json()['username'] == 'test_1.a-b'
    uid = user.json()['id']
    assert client.post('/api/users', json=dict(username='TEST_1.A-B', display_name='重复', password='def456')).status_code == 409
    assert client.post('/api/users', json=dict(username='short', display_name='读者', password='12345')).status_code == 422
    reader = login(client, 'TEST_1.A-B', 'def456')
    assert reader['user']['must_change_password']
    assert client.post('/api/password', json=dict(old_password='def456', new_password='12345')).status_code == 422
    changed = client.post('/api/password', json=dict(old_password='def456', new_password='ghi789'))
    assert changed.status_code == 200
    assert not changed.json()['user']['must_change_password']
    assert client.get('/api/me').status_code == 401
    login(client, 'admin', 'abc123')
    assert client.post(f'/api/users/{uid}/reset-password', json=dict(password='12345')).status_code == 422
    assert client.post(f'/api/users/{uid}/reset-password', json=dict(password='jkl012')).status_code == 200
    assert login(client, 'test_1.a-b', 'jkl012')['user']['must_change_password']


@pytest.mark.parametrize('username', ['', 'a' * 81, '中文', 'a b', 'a@b'])
def test_username_limits(client, admin, username):
    assert client.post('/api/users', json=dict(username=username, display_name='读者', password='abc123')).status_code == 422


def test_username_length_boundaries(client, admin):
    for username in ['a', 'b' * 80]:
        assert client.post('/api/users', json=dict(username=username, display_name='读者', password='abc123')).status_code == 200
