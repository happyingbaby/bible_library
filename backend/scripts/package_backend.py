"""Build a self-contained service, including Pandoc and Alembic migrations."""
from pathlib import Path
import subprocess
import sys
import pypandoc
root = Path(__file__).resolve().parents[2]
pandoc = Path(pypandoc.get_pandoc_path())
subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onedir', '--name', 'bible-backend', '--distpath', str(root / 'backend/dist'), '--workpath', str(root / 'backend/build'), '--specpath', str(root / 'backend'), '--paths', str(root / 'backend'), '--collect-all', 'uvicorn', '--collect-all', 'pypandoc', '--collect-all', 'alembic', '--hidden-import', 'pymysql', '--hidden-import', 'app.main', '--hidden-import', 'sqlalchemy.dialects.mysql.pymysql', '--add-data', f'{root / "backend/migrations"}:migrations', '--add-binary', f'{pandoc}:pypandoc/files', str(root / 'backend/launcher.py')], check=True)
