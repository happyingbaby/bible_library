import json
import os
import threading
import sys
from pathlib import Path
from dotenv import load_dotenv, set_key
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
ENV_FIELDS = {
    'host':'BIBLE_DB_HOST',
    'port':'BIBLE_DB_PORT',
    'username':'BIBLE_DB_USER',
    'password':'BIBLE_DB_PASSWORD',
    'database':'BIBLE_DB_NAME',
}


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


def write_connection_env(path, config):
    """Update only database keys in an environment file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.touch(mode=0o600)
    for field, variable in ENV_FIELDS.items():
        set_key(path, variable, str(config[field]), quote_mode='always', encoding='utf-8')
    path.chmod(0o600)


def migrate_legacy_connection():
    """Convert the previous per-user JSON connection file once."""
    legacy = DATA_DIR / 'database.json'
    target = DATA_DIR / '.env'
    if target.exists() or not legacy.exists():
        return
    config = json.loads(legacy.read_text(encoding='utf-8'))
    write_connection_env(target, config)
    legacy.unlink()


def load_database_environment():
    explicit = os.environ.get('BIBLE_ENV_FILE')
    if not explicit:
        migrate_legacy_connection()
    candidates = [Path(explicit)] if explicit else [DATA_DIR / '.env']
    if getattr(sys, 'frozen', False):
        candidates.append(Path(sys._MEIPASS) / '.env')
    for path in candidates:
        if path.is_file():
            load_dotenv(path, override=False)
            return path
    return None


def environment_connection(require_complete=False):
    values = {field:os.environ.get(variable) for field, variable in ENV_FIELDS.items()}
    if not any(value is not None for value in values.values()):
        return None
    if require_complete:
        missing = [ENV_FIELDS[field] for field, value in values.items() if value is None]
        if missing:
            raise ValueError('.env 缺少配置：' + '、'.join(missing))
    config = dict(DEFAULT_CONNECTION)
    config.update({field:value for field, value in values.items() if value is not None})
    if config.get('port') is not None:
        config['port'] = int(config['port'])
    return config


def writable_connection_path():
    """Persist UI changes to the active development config when configured."""
    return Path(os.environ.get('BIBLE_ENV_FILE') or DATA_DIR / '.env')


def connection_defaults():
    """Only non-secret fields are exposed to the connection form."""
    loaded = load_database_environment()
    config = dict(DEFAULT_CONNECTION)
    try:
        configured = environment_connection(require_complete=bool(loaded))
        if configured:
            config.update({key:configured[key] for key in config})
    except (ValueError, OSError, TypeError):
        pass
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
        loaded = load_database_environment()
        if os.environ.get('DATABASE_URL'):
            connect(os.environ['DATABASE_URL'])
        elif configured := environment_connection(require_complete=bool(loaded)):
            connect(mysql_url(configured))
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
