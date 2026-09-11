import hashlib
import secrets
from datetime import timedelta
from fastapi import Depends, Header, HTTPException
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from sqlalchemy import delete, select
from app.database import get_db
from app.models import Session, User, now

hasher = PasswordHasher()

def password_hash(password):
    if not 6 <= len(password) <= 128:
        raise HTTPException(422, '密码需为 6 至 128 个字符')
    return hasher.hash(password)

def verify(password, encoded):
    try:
        return hasher.verify(encoded, password)
    except (VerificationError, InvalidHashError):
        return False

def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()

def revoke(db, user_id):
    db.execute(delete(Session).where(Session.user_id == user_id))

def issue(db, user):
    token = secrets.token_urlsafe(32)
    db.add(Session(token_hash=digest(token), user_id=user.id, expires_at=now() + timedelta(hours=12)))
    return token

def identity(authorization: str = Header(default=''), db=Depends(get_db)):
    token = authorization.removeprefix('Bearer ')
    session = db.get(Session, digest(token)) if authorization.startswith('Bearer ') else None
    user = db.get(User, session.user_id) if session and session.expires_at > now() else None
    if not user or not user.active:
        raise HTTPException(401, '登录已失效，请重新登录')
    return user

def current_user(user=Depends(identity)):
    if user.must_change_password:
        raise HTTPException(403, '请先修改初始密码')
    return user

def admin(user=Depends(current_user)):
    if user.role != 'admin':
        raise HTTPException(403, '此操作仅管理员可用')
    return user

def public_user(user):
    return {key: getattr(user, key) for key in ('id', 'username', 'display_name', 'role', 'active', 'must_change_password')}
