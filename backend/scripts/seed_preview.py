"""Populate only the explicit throwaway browser-QA service."""
import json
from pathlib import Path
import httpx
root = Path(__file__).resolve().parents[2]
client = httpx.Client(base_url='http://127.0.0.1:8765/api', headers={'X-App-Key':'bible-local-preview-key'})
credentials = {'username':'preview_admin','password':'preview-password-123','display_name':'示例管理员'}
result = client.post('/setup', json=credentials)
if result.status_code == 409:
    result = client.post('/login',json=credentials)
result.raise_for_status()
client.headers['Authorization'] = 'Bearer ' + result.json()['token']
if not client.get('/lectures').json():
    lecture = client.post('/lectures',json={'title':'起初：从经文开始阅读','markdown':(root / 'examples/讲义示例.md').read_text(),'category':'创世记','tags':['示例','经文研读']}).json()
    client.patch(f'/lectures/{lecture["id"]}/publish',json={'published':True})
for code in ['zh','en']:
    payload = json.loads((root / f'examples/demo-{code}.json').read_text())
    result = client.post('/translations/preview',json=payload)
    result.raise_for_status()
    client.post('/translations/confirm',json={'preview_id':result.json()['preview_id']}).raise_for_status()
print('Isolated preview data ready. Login: preview_admin / preview-password-123')
