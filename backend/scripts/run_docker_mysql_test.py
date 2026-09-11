"""Create and remove only a uniquely named disposable test database and account."""
import os
import secrets
import subprocess
import sys
from pathlib import Path
root = Path(__file__).resolve().parents[2]
name = 'bible_test_' + secrets.token_hex(5)
password = secrets.token_urlsafe(24)
def sql(statement):
    result = subprocess.run(['docker','exec','-i','petcompanion_mysql_1','sh','-c','MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot --batch'],input=statement,text=True,capture_output=True)
    if result.returncode:
        raise RuntimeError('Test database operation failed')
try:
    sql(f"CREATE DATABASE {name} CHARACTER SET utf8mb4; CREATE USER '{name}'@'%' IDENTIFIED BY '{password}'; GRANT ALL ON {name}.* TO '{name}'@'%';")
    env = dict(os.environ,MYSQL_TEST_URL=f'mysql+pymysql://{name}:{password}@127.0.0.1:3307/{name}')
    subprocess.run([sys.executable,str(root/'backend/scripts/mysql_smoke.py')],env=env,check=True)
finally:
    sql(f"DROP DATABASE IF EXISTS {name}; DROP USER IF EXISTS '{name}'@'%';")
