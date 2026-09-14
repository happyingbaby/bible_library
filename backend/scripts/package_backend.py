"""Build a self-contained service, including Pandoc and Alembic migrations."""
from pathlib import Path
import subprocess
import sys
import os
import tempfile
from dotenv import load_dotenv, set_key
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
    local_config = root / '.env'
    if local_config.is_file():
        load_dotenv(local_config, override=False)
    variables = {'host':'BIBLE_DB_HOST','port':'BIBLE_DB_PORT','username':'BIBLE_DB_USER','password':'BIBLE_DB_PASSWORD','database':'BIBLE_DB_NAME'}
    config.update({field:os.environ[variable] for field,variable in variables.items() if variable in os.environ})
    if local_config.is_file():
        missing = [variable for variable in variables.values() if variable not in os.environ]
        if missing:
            raise SystemExit('Local .env is missing: ' + ', '.join(missing))
    if not config.get('password') and os.environ.get('BIBLE_CREDENTIAL_FREE_BUILD') != '1':
        raise SystemExit('Set database values in .env before packaging')
    config.setdefault('password', '')
    bundled = Path(temporary) / '.env'
    bundled.touch(mode=0o600)
    for field,variable in variables.items():
        set_key(bundled, variable, str(config[field]), quote_mode='always', encoding='utf-8')
    bundled.chmod(0o600)
    args[-1:-1] = ['--add-data', f'{bundled}:.']
    subprocess.run(args, check=True)
