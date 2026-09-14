import pytest


@pytest.mark.parametrize('origin', ['https://library.fdeline.com', 'http://127.0.0.1:5174', 'http://127.0.0.1:5173', 'null'])
def test_local_clients_can_preflight_and_read_status(client, origin):
    preflight = client.options('/api/status', headers={
        'Origin': origin,
        'Access-Control-Request-Method': 'GET',
        'Access-Control-Request-Headers': 'X-App-Key',
    })
    assert preflight.status_code == 200
    assert preflight.headers['access-control-allow-origin'] == origin
    response = client.get('/api/status', headers={'Origin': origin})
    assert response.status_code == 200
    assert response.json()['connected'] is True
    assert response.headers['access-control-allow-origin'] == origin
    login_preflight = client.options('/api/login', headers={
        'Origin': origin,
        'Access-Control-Request-Method': 'POST',
        'Access-Control-Request-Headers': 'Content-Type, X-App-Key, Authorization',
    })
    assert login_preflight.status_code == 200
    assert login_preflight.headers['access-control-allow-origin'] == origin
    forbidden = client.get('/api/status', headers={'Origin': origin, 'X-App-Key': 'wrong-key'})
    assert forbidden.status_code == 403


@pytest.mark.parametrize('origin', ['https://example.com', 'http://127.0.0.1:5175'])
def test_other_origins_cannot_preflight(client, origin):
    response = client.options('/api/status', headers={
        'Origin': origin,
        'Access-Control-Request-Method': 'GET',
        'Access-Control-Request-Headers': 'X-App-Key',
    })
    assert response.status_code == 400
    assert 'access-control-allow-origin' not in response.headers
