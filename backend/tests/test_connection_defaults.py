import json
import pytest
from pydantic import ValidationError
from app import database
from app.main import Connection


def test_remote_form_accepts_ips_and_dns():
    for host in ['39.102.143.118','localhost','127.0.0.1','::1','db.example.com']:
        assert Connection(host=host, username='u', password='p', database='bible_library').host == host
    for host in ['https://example.com','db:3306','a/b','a b','a..b','-host']:
        with pytest.raises(ValidationError):
            Connection(host=host, username='u', password='p', database='bible_library')


def test_first_install_and_environment_override(monkeypatch,tmp_path):
    monkeypatch.setattr(database,'DATA_DIR',tmp_path)
    monkeypatch.delenv('DATABASE_URL',raising=False)
    monkeypatch.delenv('BIBLE_DB_PASSWORD',raising=False)
    calls=[]
    monkeypatch.setattr(database,'connect',calls.append)
    database.initialize()
    assert not calls
    assert database.connection_defaults()['host']=='39.102.143.118'
    assert database.connection_defaults()['port']==3306
    assert '首次连接' in database.connection_error
    monkeypatch.setenv('BIBLE_DB_PASSWORD','runtime-test-secret')
    database.initialize()
    assert calls[-1].host=='39.102.143.118'
    assert calls[-1].password=='runtime-test-secret'
    (tmp_path/'database.json').write_text(json.dumps(dict(host='saved.example.com',port=3308,username='saved',database='saved',password='saved-secret')))
    database.initialize()
    assert calls[-1].host=='saved.example.com'
    assert 'password' not in database.connection_defaults()
    monkeypatch.setenv('DATABASE_URL','sqlite:///:memory:')
    database.initialize()
    assert calls[-1]=='sqlite:///:memory:'


def test_safe_errors_and_remote_configuration(client,admin,monkeypatch,tmp_path):
    import pymysql
    assert '认证失败' in database.connection_message(pymysql.err.OperationalError(1045,'secret'))
    assert '防火墙' in database.connection_message(pymysql.err.OperationalError(2003,'secret'))
    assert 'secret' not in database.connection_message(ValueError('secret'))
    monkeypatch.setattr(database,'DATA_DIR',tmp_path)
    calls=[]
    monkeypatch.setattr(database,'connect',calls.append)
    result=client.post('/api/connection',json=dict(host='39.102.143.118',port=3306,username='bible_library',database='bible_library',password='test-only'))
    assert result.status_code==200,result.text
    assert calls[0].host=='39.102.143.118'
    assert json.loads((tmp_path/'database.json').read_text())['host']=='39.102.143.118'


def test_packaged_defaults_and_saved_override(monkeypatch,tmp_path):
    import sys
    data=tmp_path/'data';data.mkdir()
    resources=tmp_path/'resources';resources.mkdir()
    monkeypatch.setattr(database,'DATA_DIR',data)
    monkeypatch.delenv('DATABASE_URL',raising=False)
    monkeypatch.delenv('BIBLE_DB_PASSWORD',raising=False)
    monkeypatch.setattr(sys,'frozen',True,raising=False)
    monkeypatch.setattr(sys,'_MEIPASS',str(resources),raising=False)
    config={**database.DEFAULT_CONNECTION,'password':'package-test-secret'}
    (resources/'database-defaults.json').write_text(json.dumps(config))
    calls=[];monkeypatch.setattr(database,'connect',calls.append)
    database.initialize()
    assert calls[-1].host=='39.102.143.118'
    assert calls[-1].password=='package-test-secret'
    (data/'database.json').write_text(json.dumps({**config,'host':'custom.example.com'}))
    database.initialize()
    assert calls[-1].host=='custom.example.com'


def test_packager_includes_temporary_config(monkeypatch,tmp_path):
    import runpy
    import subprocess
    import sys
    from pathlib import Path
    script=tmp_path/'backend/scripts/package_backend.py'
    script.parent.mkdir(parents=True)
    script.write_text((Path(__file__).parents[1]/'scripts/package_backend.py').read_text())
    monkeypatch.setattr(sys,'maxsize',2**31-1)
    monkeypatch.setenv('BIBLE_DB_PASSWORD','build-test-secret')
    captured=[]
    def run(args,check):
        spec=args[args.index('--add-data',args.index('--add-data')+1)+1]
        path=Path(spec.rsplit(':',1)[0])
        config=json.loads(path.read_text())
        assert config['host']=='39.102.143.118'
        assert config['password']=='build-test-secret'
        assert not any('build-test-secret' in arg for arg in args)
        captured.append(path)
    monkeypatch.setattr(subprocess,'run',run)
    runpy.run_path(str(script),run_name='__main__')
    assert captured and not captured[0].exists()
    monkeypatch.delenv('BIBLE_DB_PASSWORD')
    with pytest.raises(SystemExit,match='Set BIBLE_DB_PASSWORD'):
        runpy.run_path(str(script),run_name='__main__')



def test_credential_free_ci_package(monkeypatch,tmp_path):
    import runpy, subprocess, sys
    from pathlib import Path
    script=tmp_path/'backend/scripts/package_backend.py'
    script.parent.mkdir(parents=True)
    script.write_text((Path(__file__).parents[1]/'scripts/package_backend.py').read_text())
    monkeypatch.setattr(sys,'maxsize',2**31-1)
    monkeypatch.delenv('BIBLE_DB_PASSWORD',raising=False)
    monkeypatch.setenv('BIBLE_CREDENTIAL_FREE_BUILD','1')
    def run(args,check):
        spec=args[args.index('--add-data',args.index('--add-data')+1)+1]
        config=json.loads(Path(spec.rsplit(':',1)[0]).read_text())
        assert config['password']==''
        assert config['host']=='39.102.143.118'
    monkeypatch.setattr(subprocess,'run',run)
    runpy.run_path(str(script),run_name='__main__')
