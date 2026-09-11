import json
import os
import threading
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker

DATA_DIR = Path(os.environ.get('BIBLE_DATA_DIR', '.data')).resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)
(DATA_DIR / 'originals').mkdir(exist_ok=True)
LOCK = threading.Lock()
engine = None
factory = None
connection_error = None


def connect(url):
    global engine, factory, connection_error
    candidate = create_engine(url, pool_pre_ping=True, **({'connect_args': {'check_same_thread': False}} if str(url).startswith('sqlite') else {'connect_args': {'connect_timeout': 5}, 'isolation_level': 'READ COMMITTED'}))
    try:
        from alembic.config import Config
        from alembic import command
        config = Config()
        config.set_main_option('script_location', str(Path(__file__).parent.parent / 'migrations'))
        with candidate.begin() as connection:
            config.attributes['connection'] = connection
            command.upgrade(config, 'head')
    except Exception:
        candidate.dispose()
        raise
    if engine:
        engine.dispose()
    engine = candidate
    factory = sessionmaker(engine, expire_on_commit=False)
    connection_error = None


def mysql_url(config):
    return URL.create('mysql+pymysql', username=config['username'], password=config['password'], host=config.get('host', '127.0.0.1'), port=int(config.get('port', 3306)), database=config['database'], query={'charset': 'utf8mb4'})


def initialize():
    global connection_error
    try:
        if os.environ.get('DATABASE_URL'):
            connect(os.environ['DATABASE_URL'])
        elif (DATA_DIR / 'database.json').exists():
            connect(mysql_url(json.loads((DATA_DIR / 'database.json').read_text())))
    except Exception:
        connection_error = '无法连接数据库，请检查 MySQL 服务、数据库名称和连接账户。'


def get_db():
    from fastapi import HTTPException
    with LOCK:
        if factory is None:
            raise HTTPException(503, '请先配置数据库连接')
        with factory() as db:
            try:
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise
