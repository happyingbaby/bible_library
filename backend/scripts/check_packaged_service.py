"""Verify the frozen service includes both migrations and the Word converter."""
from pathlib import Path
import subprocess
import tempfile
import httpx
import pypandoc
client=httpx.Client(base_url='http://127.0.0.1:8766/api',headers={'X-App-Key':'packaged-test-key'})
assert client.get('/status').json()['connected']
credentials={'username':'packaged','display_name':'打包测试','password':'packaged-password-123'}
result=client.post('/setup',json=credentials)
if result.status_code==409:result=client.post('/login',json=credentials)
result.raise_for_status()
client.headers['Authorization']='Bearer '+result.json()['token']
with tempfile.TemporaryDirectory() as temporary:
    root=Path(temporary)
    (root/'source.md').write_text('# 打包转换测试\n\n**正文完整**【创1:1】')
    subprocess.run([pypandoc.get_pandoc_path(),str(root/'source.md'),'-o',str(root/'source.docx')],check=True)
    result=client.post('/imports/preview',files={'file':('source.docx',(root/'source.docx').read_bytes())})
    result.raise_for_status()
    assert '**正文完整**' in result.json()['markdown']
    assert result.json()['references'][0]['book']=='Gen'
print('Frozen service migration, login and bundled Pandoc conversion passed.')
