"""Create a NEW isolated application database in an existing Docker MySQL.
Never alters an existing schema or rotates an existing user password.
Credentials are saved only to an owner-readable local configuration file.
"""
import argparse
import json
import os
import secrets
import subprocess
from pathlib import Path
parser = argparse.ArgumentParser()
parser.add_argument('--container', required=True)
parser.add_argument('--port', type=int, required=True)
parser.add_argument('--config', type=Path, required=True)
args = parser.parse_args()

def sql(statement):
    p = subprocess.run(['docker','exec','-i',args.container,'sh','-c','MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot --default-character-set=utf8mb4 --batch --skip-column-names'], input=statement, text=True, capture_output=True)
    if p.returncode:
        raise SystemExit('MySQL operation failed; no credentials printed. Check container root access.')
    return p.stdout.strip()
if args.config.exists():
    raise SystemExit('Configuration already exists; refusing to overwrite it.')
if sql("SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME='bible_library'; SELECT User FROM mysql.user WHERE User='bible_library_app';"):
    raise SystemExit('Database or dedicated user already exists; refusing to modify it.')
password = secrets.token_urlsafe(32)
sql(f"CREATE DATABASE bible_library CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci; CREATE USER 'bible_library_app'@'%' IDENTIFIED BY '{password}'; GRANT ALL PRIVILEGES ON bible_library.* TO 'bible_library_app'@'%';")
args.config.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
fd=os.open(args.config,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
with os.fdopen(fd,'w') as stream:
    json.dump({'host':'127.0.0.1','port':args.port,'username':'bible_library_app','password':password,'database':'bible_library'},stream)
print(f'Created isolated bible_library database. Connection saved to {args.config}. No existing databases changed.')
