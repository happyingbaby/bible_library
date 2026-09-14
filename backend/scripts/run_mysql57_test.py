"""Test the production MySQL version in a disposable, loopback-only container."""
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import time

root = Path(__file__).resolve().parents[2]
name = 'bible-test-mysql57-' + secrets.token_hex(6)
password = secrets.token_urlsafe(24)
created = False


def sql(statement):
    return subprocess.run(
        ['docker', 'exec', '-i', name, 'sh', '-c',
         'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot --batch --skip-column-names'],
        input=statement, text=True, capture_output=True)


try:
    subprocess.run([
        'docker', 'create', '--platform', 'linux/amd64', '--name', name,
        '-p', '127.0.0.1::3306', '--tmpfs', '/var/lib/mysql:rw',
        '-e', 'MYSQL_ROOT_PASSWORD', 'mysql:5.7.40',
        '--character-set-server=utf8mb4', '--collation-server=utf8mb4_unicode_ci',
    ], env=dict(os.environ, MYSQL_ROOT_PASSWORD=password), check=True,
        stdout=subprocess.DEVNULL)
    created = True
    subprocess.run(['docker', 'start', name], check=True, stdout=subprocess.DEVNULL)
    deadline = time.monotonic() + 180
    while True:
        ready = sql('SELECT VERSION();')
        # During initialization the entrypoint runs a socket-only temporary server.
        # Check TCP too before launching the application.
        tcp = subprocess.run(['docker', 'exec', name, 'sh', '-c',
            'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -h127.0.0.1 -uroot -e "SELECT 1"'],
            capture_output=True)
        if ready.returncode == 0 and tcp.returncode == 0:
            break
        if time.monotonic() >= deadline:
            raise RuntimeError('MySQL 5.7 did not become ready within 180 seconds')
        time.sleep(2)
    version = ready.stdout.strip()
    assert version == '5.7.40', version
    print('Verified isolated server version:', version, flush=True)
    result = sql(f"CREATE DATABASE bible_test_compat CHARACTER SET utf8mb4; "
        f"CREATE USER 'bible_test_compat'@'%' IDENTIFIED BY '{password}'; "
        "GRANT ALL ON bible_test_compat.* TO 'bible_test_compat'@'%';")
    if result.returncode:
        raise RuntimeError('Unable to initialize disposable database')
    address = subprocess.check_output(['docker', 'port', name, '3306/tcp'], text=True).strip()
    assert address.startswith('127.0.0.1:'), address
    port = int(address.rsplit(':', 1)[1])
    with tempfile.TemporaryDirectory(prefix='bible-mysql57-') as directory:
        env = dict(os.environ,
            MYSQL_TEST_URL=f'mysql+pymysql://bible_test_compat:{password}@127.0.0.1:{port}/bible_test_compat',
            MYSQL_TEST_DATA_DIR=directory)
        subprocess.run([sys.executable, str(root / 'backend/scripts/mysql_smoke.py')],
            env=env, check=True)
finally:
    if created:
        subprocess.run(['docker', 'rm', '-f', '-v', name], check=True,
            stdout=subprocess.DEVNULL)
        print('Removed disposable MySQL 5.7 container and database.', flush=True)
