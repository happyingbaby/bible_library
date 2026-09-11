import io
import json
import re
import shutil
import tempfile
import uuid
import zipfile
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, delete, select
from app.database import DATA_DIR, get_db
from app.models import Base, Guard, User, Session, Lecture, History, Reference, Translation, Verse, now
from app.security import admin

router = APIRouter(prefix='/api/backups')
TABLES = [User.__table__, Translation.__table__, Lecture.__table__, History.__table__, Reference.__table__, Verse.__table__]
MAX_BACKUP = 200 * 1024 * 1024

class Restore(BaseModel):
    preview_id: str = Field(pattern=r'^[a-f0-9]{32}$')


def snapshot(db):
    tables = {}
    for table in TABLES:
        tables[table.name] = [{key: value.isoformat() if isinstance(value, datetime) else value for key, value in dict(row).items()} for row in db.execute(select(table)).mappings()]
    payload = {'format': 'scripture-library', 'version': 1, 'created_at': now().isoformat(), 'tables': tables}
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('database.json', json.dumps(payload, ensure_ascii=False))
        for lecture in tables['lectures']:
            if lecture['original_file']:
                name = lecture['original_file']
                path = DATA_DIR / 'originals' / name
                if not path.is_file():
                    raise HTTPException(409, f'讲义 {lecture["id"]} 的原始文件缺失，无法生成完整备份')
                archive.write(path, 'originals/' + name)
    return stream.getvalue()


def validate(data):
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            infos = archive.infolist()
            names = [i.filename for i in infos]
            if len(names) != len(set(names)) or sum(i.file_size for i in infos) > MAX_BACKUP:
                raise ValueError('备份解压后过大或包含重复文件')
            if any(n != 'database.json' and not re.fullmatch(r'originals/[a-f0-9]{32}\.(docx|md)', n) for n in names):
                raise ValueError('备份包含不安全或未知路径')
            payload = json.loads(archive.read('database.json'))
            if payload.get('format') != 'scripture-library' or payload.get('version') != 1:
                raise ValueError('备份版本不兼容')
            rows = payload['tables']
            if set(rows) != {t.name for t in TABLES}:
                raise ValueError('备份表结构不完整')
            for table in TABLES:
                ids = set()
                for row in rows[table.name]:
                    if set(row) != {c.name for c in table.columns} or not isinstance(row['id'], int) or row['id'] in ids:
                        raise ValueError('备份记录结构或编号无效')
                    ids.add(row['id'])
                    for column in table.columns:
                        value = row[column.name]
                        if value is None and not column.nullable and not column.primary_key:
                            raise ValueError('必填字段为空')
                        if isinstance(column.type, DateTime) and value is not None:
                            datetime.fromisoformat(value)
            user_ids = {r['id'] for r in rows['users']}
            lecture_ids = {r['id'] for r in rows['lectures']}
            translation_ids = {r['id'] for r in rows['translations']}
            if not any(u['active'] is True and u['role'] == 'admin' and not u['must_change_password'] for u in rows['users']):
                raise ValueError('备份中缺少可登录的管理员')
            if any(u['role'] not in ('admin', 'reader') or not u['password_hash'].startswith('$argon2id$') for u in rows['users']):
                raise ValueError('账户信息无效')
            for row in rows['lectures']:
                if row['created_by'] not in user_ids or row['updated_by'] not in user_ids:
                    raise ValueError('讲义账户关联不完整')
                if row['original_file'] and 'originals/' + row['original_file'] not in names:
                    raise ValueError('原始文件缺失')
            for row in rows['histories']:
                if row['lecture_id'] not in lecture_ids or row['user_id'] not in user_ids:
                    raise ValueError('历史关联不完整')
            if any(r['lecture_id'] not in lecture_ids for r in rows['references']) or any(v['translation_id'] not in translation_ids for v in rows['verses']):
                raise ValueError('经文或引用关联不完整')
            return payload
    except (ValueError, KeyError, TypeError, AttributeError, zipfile.BadZipFile, RuntimeError) as exc:
        raise HTTPException(422, '无效备份：' + str(exc))

@router.get('')
def download(user=Depends(admin), db=Depends(get_db)):
    return Response(snapshot(db), media_type='application/zip', headers={'Content-Disposition': 'attachment; filename="scripture-backup.zip"'})

@router.post('/preview')
def preview(file: UploadFile = File(...), user=Depends(admin)):
    data = file.file.read(MAX_BACKUP + 1)
    if len(data) > MAX_BACKUP:
        raise HTTPException(413, '备份不能超过 200 MB')
    payload = validate(data)
    preview_id = uuid.uuid4().hex
    directory = DATA_DIR / 'restore_pending'
    directory.mkdir(exist_ok=True)
    (directory / (preview_id + '.zip')).write_bytes(data)
    (directory / (preview_id + '.json')).write_text(json.dumps({'owner': user.id}))
    return {'preview_id': preview_id, 'created_at': payload['created_at'], 'counts': {name: len(rows) for name, rows in payload['tables'].items()}, 'warning': '将替换当前资料和账户。系统会先自动备份当前资料；恢复后使用备份中的账户重新登录。'}

@router.post('/restore')
def restore(data: Restore, user=Depends(admin), db=Depends(get_db)):
    path = DATA_DIR / 'restore_pending' / (data.preview_id + '.zip')
    owner_path = path.with_suffix('.json')
    if not path.is_file() or not owner_path.is_file():
        raise HTTPException(404, '恢复预览已失效')
    if json.loads(owner_path.read_text())['owner'] != user.id:
        raise HTTPException(403, '不能确认其他用户的恢复')
    raw = path.read_bytes()
    payload = validate(raw)
    directory = DATA_DIR / 'backups'
    directory.mkdir(exist_ok=True)
    safety_path = directory / ('before-restore-' + now().strftime('%Y%m%d-%H%M%S-') + uuid.uuid4().hex[:8] + '.zip')
    safety_path.write_bytes(snapshot(db))
    # Immutable original names are copied before the DB transaction; never overwrite a
    # currently referenced file. On failure new files are removed, old state stays valid.
    created_files = []
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            for row in payload['tables']['lectures']:
                if row['original_file']:
                    previous = row['original_file']
                    name = uuid.uuid4().hex + Path(previous).suffix
                    destination = DATA_DIR / 'originals' / name
                    destination.write_bytes(archive.read('originals/' + previous))
                    created_files.append(destination)
                    row['original_file'] = name
        db.execute(delete(Session))
        for table in reversed(TABLES):
            db.execute(delete(table))
        for table in TABLES:
            records = payload['tables'][table.name]
            for record in records:
                for column in table.columns:
                    if isinstance(column.type, DateTime) and record[column.name] is not None:
                        record[column.name] = datetime.fromisoformat(record[column.name])
            if records:
                db.execute(table.insert(), records)
        db.commit()
    except Exception:
        db.rollback()
        for path_created in created_files:
            path_created.unlink(missing_ok=True)
        raise HTTPException(422, '恢复失败，当前数据库未更改，恢复前备份已保留')
    path.unlink(missing_ok=True)
    owner_path.unlink(missing_ok=True)
    # Clear import previews belonging to the previous account set.
    for folder in ('pending', 'scripture_pending', 'restore_pending'):
        shutil.rmtree(DATA_DIR / folder, ignore_errors=True)
    return {'ok': True, 'safety_backup': str(safety_path), 'message': '恢复完成，请使用备份中的账户重新登录'}
