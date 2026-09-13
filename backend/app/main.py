import json
import os
import secrets
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from app import database
from app.models import User
from app.modules import accounts, backups, lectures, scripture

APP_KEY = os.environ.get('BIBLE_APP_KEY', '')

@asynccontextmanager
async def lifespan(app):
    database.initialize()
    yield

app = FastAPI(title='圣经讲义管理平台', docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=['http://127.0.0.1:5173', 'http://127.0.0.1:5174', 'null'], allow_methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE'], allow_headers=['Authorization', 'Content-Type', 'X-App-Key'])

@app.middleware('http')
async def local_client(request: Request, call_next):
    if request.method != 'OPTIONS':
        if not APP_KEY or not secrets.compare_digest(request.headers.get('X-App-Key', ''), APP_KEY):
            return JSONResponse(status_code=403, content={'detail': '请通过桌面应用访问本地服务'})
        length = request.headers.get('content-length')
        if length and int(length) > 205 * 1024 * 1024:
            return JSONResponse(status_code=413, content={'detail': '请求过大'})
    return await call_next(request)

@app.exception_handler(SQLAlchemyError)
async def database_error(request, exc):
    return JSONResponse(status_code=503, content={'detail': '数据库操作失败，请检查连接或数据是否冲突；未保存的内容请先保留。'})

@app.get('/api/status')
def status():
    with database.LOCK:
        if database.factory is None:
            return {'connected': False, 'initialized': False, 'error': database.connection_error, 'connection': database.connection_defaults()}
        try:
            with database.factory() as db:
                initialized = db.scalar(select(User.id).limit(1)) is not None
                return {'connected': True, 'initialized': initialized}
        except SQLAlchemyError:
            return {'connected': False, 'initialized': False, 'error': 'MySQL 连接已中断，请检查服务或重新配置连接。'}

class Connection(BaseModel):
    host: str = Field(default=database.DEFAULT_CONNECTION['host'], min_length=1, max_length=253)

    @field_validator('host')
    @classmethod
    def valid_host(cls, value):
        import ipaddress
        import re
        value = value.strip()
        try:
            ipaddress.ip_address(value)
            return value
        except ValueError:
            if not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?', value) or any(not label or len(label)>63 or label.startswith('-') or label.endswith('-') for label in value.split('.')):
                raise ValueError('请输入有效的 IP 地址或主机名，不要包含协议、端口或路径')
            return value
    port: int = Field(default=3306, ge=1, le=65535)
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(max_length=200)
    database: str = Field(min_length=1, max_length=64, pattern=r'^[A-Za-z0-9_]+$')

@app.post('/api/connection')
def configure(data: Connection, authorization: str = Header(default='')):
    with database.LOCK:
        if database.factory:
            try:
                with database.factory() as db:
                    initialized = db.scalar(select(User.id).limit(1)) is not None
                    if initialized:
                        from app.security import identity, current_user, admin
                        admin(current_user(identity(authorization, db)))
            except SQLAlchemyError:
                pass  # A broken connection must remain recoverable from the local shell.
        try:
            database.connect(database.mysql_url(data.model_dump()))
        except Exception as exc:
            raise HTTPException(400, database.connection_message(exc))
        path = database.DATA_DIR / 'database.json'
        temporary = path.with_suffix('.tmp')
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w') as stream:
            json.dump(data.model_dump(), stream)
        temporary.replace(path)
        path.chmod(0o600)
    return {'ok': True}

for module in (accounts, lectures, scripture, backups):
    app.include_router(module.router)
