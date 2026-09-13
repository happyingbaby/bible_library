"""Build a self-contained service, including Pandoc and Alembic migrations."""
from pathlib import Path
import subprocess
import sys
import os
import json
import tempfile
root = Path(__file__).resolve().parents[2]
args = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onedir', '--name', 'bible-backend', '--distpath', str(root / 'backend/dist'), '--workpath', str(root / 'backend/build'), '--specpath', str(root / 'backend'), '--paths', str(root / 'backend'), '--collect-all', 'uvicorn', '--collect-all', 'alembic', '--hidden-import', 'pymysql', '--hidden-import', 'app.main', '--hidden-import', 'sqlalchemy.dialects.mysql.pymysql', '--add-data', f'{root / "backend/migrations"}:migrations']
if sys.maxsize > 2**32:
    import pypandoc
    pandoc = Path(pypandoc.get_pandoc_path())
    if not pandoc.exists() and sys.platform == 'win32':
        pandoc_exe = pandoc.with_suffix('.exe')
        if pandoc_exe.exists():
            pandoc = pandoc_exe
    args.extend(['--collect-all', 'pypandoc', '--add-binary', f'{pandoc}:pypandoc/files'])
args.append(str(root / 'backend/launcher.py'))
# Credentials enter the distributable only; never source control or build logs.
with tempfile.TemporaryDirectory(prefix='bible-build-config-') as temporary:
    config = {'host':'39.102.143.118', 'port':3306, 'username':'bible_library', 'database':'bible_library'}
    local_config = root / '.local' / 'database-defaults.json'
    if os.environ.get('BIBLE_DB_PASSWORD'):
        config['password'] = os.environ['BIBLE_DB_PASSWORD']
    elif local_config.is_file():
        saved = json.loads(local_config.read_text())
        if any(saved.get(key) != value for key, value in config.items()):
            raise SystemExit('Local package database target differs from the expected online database')
        config['password'] = saved.get('password', '')
    if not config.get('password'):
        raise SystemExit('Set BIBLE_DB_PASSWORD or .local/database-defaults.json before packaging')
    bundled = Path(temporary) / 'database-defaults.json'
    bundled.write_text(json.dumps(config), encoding='utf-8')
    bundled.chmod(0o600)
    args[-1:-1] = ['--add-data', f'{bundled}:.']
    subprocess.run(args, check=True)
