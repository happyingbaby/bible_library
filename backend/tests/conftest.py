import os
import tempfile
os.environ['BIBLE_DATA_DIR'] = tempfile.mkdtemp(prefix='bible-tests-')
os.environ['BIBLE_APP_KEY'] = 'test-local-app-key'
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app import database
from app.modules import accounts

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_URL', 'sqlite:///' + str(tmp_path / 'test.sqlite'))
    accounts.attempts.clear()
    with TestClient(app, headers={'X-App-Key': 'test-local-app-key'}) as client:
        yield client

@pytest.fixture
def admin(client):
    result = client.post('/api/setup', json={'username': 'admin', 'display_name': '管理员', 'password': 'admin-password-123'}).json()
    client.headers['Authorization'] = 'Bearer ' + result['token']
    return result

def login(client, username, password):
    result = client.post('/api/login', json={'username': username, 'password': password})
    assert result.status_code == 200, result.text
    client.headers['Authorization'] = 'Bearer ' + result.json()['token']
    return result.json()
