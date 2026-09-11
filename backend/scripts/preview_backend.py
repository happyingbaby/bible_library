"""Browser QA only: isolated SQLite data, no production database configuration."""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'backend'))
os.environ.setdefault('BIBLE_DATA_DIR', '/private/tmp/bible-library-preview')
os.environ.setdefault('DATABASE_URL', 'sqlite:////private/tmp/bible-library-preview.sqlite')
os.environ.setdefault('BIBLE_APP_KEY', 'bible-local-preview-key')
import uvicorn
if __name__ == '__main__':
    uvicorn.run('app.main:app',host='127.0.0.1',port=8765,access_log=False)
