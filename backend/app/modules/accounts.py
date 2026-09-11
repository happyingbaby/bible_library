import time
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from app.database import get_db
from app.models import Guard, User
from app.security import admin, current_user, identity, issue, password_hash, public_user, revoke, verify

router = APIRouter(prefix='/api')
attempts = []

class Credentials(BaseModel):
    username: str = Field(min_length=1, max_length=80, pattern=r'^[A-Za-z0-9_.-]+$')
    password: str = Field(min_length=1, max_length=128)

class NewUser(Credentials):
    display_name: str = Field(min_length=1, max_length=100)
    role: Literal['admin', 'reader'] = 'reader'

class PasswordChange(BaseModel):
    old_password: str = Field(max_length=128)
    new_password: str = Field(max_length=128)

class Reset(BaseModel):
    password: str = Field(max_length=128)

class State(BaseModel):
    active: bool

@router.post('/setup')
def setup(data: NewUser, db=Depends(get_db)):
    db.execute(select(Guard).where(Guard.id == 1).with_for_update()).scalar_one()
    if db.scalar(select(User.id).limit(1)):
        raise HTTPException(409, '管理员已经初始化')
    user = User(username=data.username.lower(), display_name=data.display_name, password_hash=password_hash(data.password), role='admin', active=True, must_change_password=False)
    db.add(user)
    db.flush()
    return {'token': issue(db, user), 'user': public_user(user)}

@router.post('/login')
def login(data: Credentials, db=Depends(get_db)):
    now = time.monotonic()
    attempts[:] = [stamp for stamp in attempts if now - stamp < 60]
    if len(attempts) >= 15:
        raise HTTPException(429, '尝试次数过多，请稍后再试')
    user = db.scalar(select(User).where(User.username == data.username.lower()))
    if not user or not user.active or not verify(data.password, user.password_hash):
        attempts.append(now)
        raise HTTPException(401, '用户名或密码错误，或账户已停用')
    return {'token': issue(db, user), 'user': public_user(user)}

@router.get('/me')
def me(user=Depends(identity)):
    return public_user(user)

@router.post('/logout')
def logout(user=Depends(identity), db=Depends(get_db)):
    revoke(db, user.id)
    return {'ok': True}

@router.post('/password')
def change_password(data: PasswordChange, user=Depends(identity), db=Depends(get_db)):
    if not verify(data.old_password, user.password_hash):
        raise HTTPException(400, '当前密码不正确')
    if data.old_password == data.new_password:
        raise HTTPException(422, '新密码不能与当前密码相同')
    user.password_hash = password_hash(data.new_password)
    user.must_change_password = False
    revoke(db, user.id)
    return {'token': issue(db, user), 'user': public_user(user)}

@router.get('/users')
def users(user=Depends(admin), db=Depends(get_db)):
    return [public_user(u) for u in db.scalars(select(User).order_by(User.id))]

@router.post('/users')
def create_user(data: NewUser, user=Depends(admin), db=Depends(get_db)):
    if db.scalar(select(User).where(User.username == data.username.lower())):
        raise HTTPException(409, '用户名已存在')
    created = User(username=data.username.lower(), display_name=data.display_name, password_hash=password_hash(data.password), role=data.role, active=True, must_change_password=True)
    db.add(created)
    db.flush()
    return public_user(created)

@router.patch('/users/{user_id}')
def set_state(user_id: int, data: State, user=Depends(admin), db=Depends(get_db)):
    db.execute(select(Guard).where(Guard.id == 1).with_for_update()).scalar_one()
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(404, '用户不存在')
    active_admins = list(db.scalars(select(User).where(User.role == 'admin', User.active == True).with_for_update()))
    if not data.active and target.role == 'admin' and target.active and len(active_admins) <= 1:
        raise HTTPException(409, '不能停用最后一个启用的管理员')
    target.active = data.active
    if not data.active:
        revoke(db, target.id)
    return public_user(target)

@router.post('/users/{user_id}/reset-password')
def reset_password(user_id: int, data: Reset, user=Depends(admin), db=Depends(get_db)):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(404, '用户不存在')
    target.password_hash = password_hash(data.password)
    target.must_change_password = True
    revoke(db, target.id)
    return {'ok': True}
