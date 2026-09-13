import json
import os
import threading
import sys
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
DEFAULT_CONNECTION = {'host':'39.102.143.118', 'port':3306, 'database':'bible_library', 'username':'bible_library'}
CONNECTION_KEYS = ('host', 'port', 'username', 'password', 'database')


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


def read_connection_config(path):
    """Read one complete connection file without logging its credentials."""
    config = json.loads(Path(path).read_text(encoding='utf-8'))
    missing = [key for key in CONNECTION_KEYS if key not in config]
    if missing:
        raise ValueError('数据库配置缺少字段：' + '、'.join(missing))
    return {key:config[key] for key in CONNECTION_KEYS}


def project_connection_config():
    path = os.environ.get('BIBLE_DATABASE_CONFIG')
    return read_connection_config(path) if path else None


def writable_connection_path():
    """Persist UI changes to the active development config when configured."""
    return Path(os.environ.get('BIBLE_DATABASE_CONFIG') or DATA_DIR / 'database.json')


def connection_defaults():
    """Only non-secret fields are exposed to the connection form."""
    config = dict(DEFAULT_CONNECTION)
    paths = [Path(os.environ['BIBLE_DATABASE_CONFIG'])] if os.environ.get('BIBLE_DATABASE_CONFIG') else []
    paths.append(DATA_DIR / 'database.json')
    for path in paths:
        if not path.is_file():
            continue
        try:
            saved = read_connection_config(path)
            config.update({key:saved[key] for key in config if key in saved})
        except (ValueError, OSError, TypeError):
            pass
        break
    return config


def connection_message(exc):
    original = getattr(exc, 'orig', exc)
    code = original.args[0] if original.args else None
    if code == 1045:
        return '数据库认证失败，请检查数据库用户名、密码及服务器账户的来源主机授权。'
    if code in (2003, 2005, 2006, 2013):
        return '无法连接数据库服务器，请检查网络、服务器地址、端口及防火墙放行规则。'
    if code == 1049:
        return '目标数据库不存在，请核对数据库名称。'
    if code in (1044, 1142, 1143):
        return '数据库账户权限不足，需要目标数据库的读写和结构迁移权限。'
    return '数据库连接或结构升级失败，请核对连接配置及数据库迁移兼容性。'


def initialize():
    global connection_error
    try:
        if os.environ.get('DATABASE_URL'):
            connect(os.environ['DATABASE_URL'])
        elif os.environ.get('BIBLE_DATABASE_CONFIG'):
            connect(mysql_url(project_connection_config()))
        elif (DATA_DIR / 'database.json').exists():
            connect(mysql_url(read_connection_config(DATA_DIR / 'database.json')))
        elif os.environ.get('BIBLE_DB_PASSWORD'):
            connect(mysql_url({**DEFAULT_CONNECTION, 'password':os.environ['BIBLE_DB_PASSWORD']}))
        elif getattr(sys, 'frozen', False) and (Path(sys._MEIPASS) / 'database-defaults.json').is_file():
            connect(mysql_url(read_connection_config(Path(sys._MEIPASS) / 'database-defaults.json')))
        else:
            connection_error = '已预设线上资料库地址，请输入数据库密码完成首次连接；无需在此电脑安装 MySQL。'
    except Exception as exc:
        connection_error = connection_message(exc)


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
