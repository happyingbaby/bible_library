"""Build a self-contained service, including Pandoc and Alembic migrations."""
from pathlib import Path
import subprocess
import sys
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
subprocess.run(args, check=True)
