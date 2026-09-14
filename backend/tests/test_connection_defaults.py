import json
import pytest
from dotenv import dotenv_values
from pydantic import ValidationError
from app import database
from app.main import Connection


DATABASE_VARIABLES = (*database.ENV_FIELDS.values(), 'BIBLE_ENV_FILE', 'BIBLE_DATABASE_CONFIG')


@pytest.fixture(autouse=True)
def clean_database_environment(monkeypatch):
    for variable in DATABASE_VARIABLES:
        monkeypatch.delenv(variable, raising=False)


def env_config(**overrides):
    config = dict(host='db.example.com', port=3306, username='db-user', password='db-secret', database='bible_library')
    config.update(overrides)
    return config


def test_remote_form_accepts_ips_and_dns():
    for host in ['39.102.143.118','localhost','127.0.0.1','::1','db.example.com']:
        assert Connection(host=host, username='u', password='p', database='bible_library').host == host
    for host in ['https://example.com','db:3306','a/b','a b','a..b','-host']:
        with pytest.raises(ValidationError):
            Connection(host=host, username='u', password='p', database='bible_library')


def test_first_install_and_environment_override(monkeypatch,tmp_path):
    monkeypatch.setattr(database,'DATA_DIR',tmp_path)
    monkeypatch.delenv('DATABASE_URL',raising=False)
    calls=[]
    monkeypatch.setattr(database,'connect',calls.append)
    database.initialize()
    assert not calls
    assert database.connection_defaults()['host']=='39.102.143.118'
    assert '首次连接' in database.connection_error
    monkeypatch.setenv('BIBLE_DB_PASSWORD','runtime-test-secret')
    database.initialize()
    assert calls[-1].host=='39.102.143.118'
    assert calls[-1].password=='runtime-test-secret'
    monkeypatch.setenv('DATABASE_URL','sqlite:///:memory:')
    database.initialize()
    assert calls[-1]=='sqlite:///:memory:'


def test_dotenv_is_complete_and_overrides_user_config(monkeypatch,tmp_path):
    data=tmp_path/'data';data.mkdir()
    project=tmp_path/'.env'
    project_config=env_config(host='project.example.com',port=3310)
    database.write_connection_env(project,project_config)
    database.write_connection_env(data/'.env',env_config(host='saved.example.com'))
    monkeypatch.setattr(database,'DATA_DIR',data)
    monkeypatch.delenv('DATABASE_URL',raising=False)
    monkeypatch.setenv('BIBLE_ENV_FILE',str(project))
    calls=[];monkeypatch.setattr(database,'connect',calls.append)
    database.initialize()
    assert calls[-1].host=='project.example.com'
    assert calls[-1].port==3310
    assert calls[-1].password=='db-secret'
    assert database.connection_defaults()=={key:project_config[key] for key in database.DEFAULT_CONNECTION}
    assert database.writable_connection_path()==project


def test_incomplete_dotenv_is_rejected(monkeypatch,tmp_path):
    project=tmp_path/'.env';project.write_text('BIBLE_DB_HOST=incomplete.example.com\n')
    monkeypatch.setattr(database,'DATA_DIR',tmp_path/'data')
    monkeypatch.setenv('BIBLE_ENV_FILE',str(project))
    calls=[];monkeypatch.setattr(database,'connect',calls.append)
    database.initialize()
    assert not calls
    assert '配置' in database.connection_error


def test_legacy_json_is_migrated_once(monkeypatch,tmp_path):
    legacy=tmp_path/'database.json'
    legacy.write_text(json.dumps(env_config()))
    monkeypatch.setattr(database,'DATA_DIR',tmp_path)
    calls=[];monkeypatch.setattr(database,'connect',calls.append)
    database.initialize()
    assert calls[-1].host=='db.example.com'
    assert not legacy.exists()
    values=dotenv_values(tmp_path/'.env')
    assert values['BIBLE_DB_PASSWORD']=='db-secret'
    assert oct((tmp_path/'.env').stat().st_mode & 0o777)=='0o600'


def test_safe_errors_and_remote_configuration(client,admin,monkeypatch,tmp_path):
    import pymysql
    assert '认证失败' in database.connection_message(pymysql.err.OperationalError(1045,'secret'))
    assert '防火墙' in database.connection_message(pymysql.err.OperationalError(2003,'secret'))
    assert 'secret' not in database.connection_message(ValueError('secret'))
    project_config=tmp_path/'.env'
    monkeypatch.setenv('BIBLE_ENV_FILE',str(project_config))
    calls=[];monkeypatch.setattr(database,'connect',calls.append)
    result=client.post('/api/connection',json=dict(host='39.102.143.118',port=3306,username='bible_library',database='bible_library',password='test-only'))
    assert result.status_code==200,result.text
    assert calls[0].host=='39.102.143.118'
    assert dotenv_values(project_config)['BIBLE_DB_HOST']=='39.102.143.118'
    assert oct(project_config.stat().st_mode & 0o777)=='0o600'


def test_packaged_dotenv_and_user_override(monkeypatch,tmp_path):
    import sys
    data=tmp_path/'data';data.mkdir()
    resources=tmp_path/'resources';resources.mkdir()
    database.write_connection_env(data/'.env',env_config(host='custom.example.com'))
    database.write_connection_env(resources/'.env',env_config(host='packaged.example.com'))
    monkeypatch.setattr(database,'DATA_DIR',data)
    monkeypatch.setattr(sys,'frozen',True,raising=False)
    monkeypatch.setattr(sys,'_MEIPASS',str(resources),raising=False)
    calls=[];monkeypatch.setattr(database,'connect',calls.append)
    database.initialize()
    assert calls[-1].host=='custom.example.com'
    assert calls[-1].password=='db-secret'


def test_packager_includes_temporary_dotenv(monkeypatch,tmp_path):
    import runpy
    import subprocess
    import sys
    from pathlib import Path
    script=tmp_path/'backend/scripts/package_backend.py'
    script.parent.mkdir(parents=True)
    script.write_text((Path(__file__).parents[1]/'scripts/package_backend.py').read_text())
    database.write_connection_env(tmp_path/'.env',env_config(host='custom-db.example.com',port=3309,password=''))
    monkeypatch.setattr(sys,'maxsize',2**31-1)
    monkeypatch.setenv('BIBLE_DB_PASSWORD','build-test-secret')
    captured=[]
    def run(args,check):
        spec=args[args.index('--add-data',args.index('--add-data')+1)+1]
        path=Path(spec.rsplit(':',1)[0])
        config=dotenv_values(path)
        assert config['BIBLE_DB_HOST']=='custom-db.example.com'
        assert config['BIBLE_DB_PORT']=='3309'
        assert config['BIBLE_DB_PASSWORD']=='build-test-secret'
        assert not any('build-test-secret' in arg for arg in args)
        captured.append(path)
    monkeypatch.setattr(subprocess,'run',run)
    runpy.run_path(str(script),run_name='__main__')
    assert captured and not captured[0].exists()
    monkeypatch.setenv('BIBLE_DB_PASSWORD','')
    with pytest.raises(SystemExit,match='Set database values'):
        runpy.run_path(str(script),run_name='__main__')


def test_credential_free_ci_package(monkeypatch,tmp_path):
    import runpy, subprocess, sys
    from pathlib import Path
    script=tmp_path/'backend/scripts/package_backend.py'
    script.parent.mkdir(parents=True)
    script.write_text((Path(__file__).parents[1]/'scripts/package_backend.py').read_text())
    monkeypatch.setattr(sys,'maxsize',2**31-1)
    monkeypatch.setenv('BIBLE_CREDENTIAL_FREE_BUILD','1')
    def run(args,check):
        spec=args[args.index('--add-data',args.index('--add-data')+1)+1]
        config=dotenv_values(Path(spec.rsplit(':',1)[0]))
        assert config['BIBLE_DB_PASSWORD']==''
        assert config['BIBLE_DB_HOST']=='39.102.143.118'
    monkeypatch.setattr(subprocess,'run',run)
    runpy.run_path(str(script),run_name='__main__')
