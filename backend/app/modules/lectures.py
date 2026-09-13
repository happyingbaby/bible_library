import json
import re
import subprocess
import tempfile
import uuid
import zipfile
from datetime import date
from pathlib import Path
from xml.etree import ElementTree as ET
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, or_, select
from app.database import DATA_DIR, get_db
from app.models import History, Lecture, Reference, now
from app.security import admin, current_user
from app.modules.references import render

router = APIRouter(prefix='/api')
MAX_UPLOAD = 20 * 1024 * 1024

class Content(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    author: str = Field(default='', max_length=100)
    sermon_date: date | None = None
    markdown: str = Field(max_length=2_000_000)
    category: str = Field(default='', max_length=100)
    tags: list[str] = Field(default_factory=list, max_length=30)
    revision: int | None = None

class Preview(BaseModel):
    markdown: str = Field(max_length=2_000_000)

class Confirm(BaseModel):
    preview_id: str = Field(pattern=r'^[a-f0-9]{32}$')
    title: str = Field(min_length=1, max_length=255)
    author: str = Field(default='', max_length=100)
    sermon_date: date | None = None
    category: str = Field(default='', max_length=100)
    tags: list[str] = Field(default_factory=list, max_length=30)

class Publish(BaseModel):
    published: bool

class Trash(BaseModel):
    deleted: bool


def visible(db, lecture_id, user):
    lecture = db.get(Lecture, lecture_id)
    if not lecture or (user.role != 'admin' and (not lecture.published or lecture.deleted)):
        raise HTTPException(404, '讲义不存在或不可访问')
    return lecture


def serialize(lecture, detail=False):
    keys = ['id', 'title', 'author', 'sermon_date', 'category', 'tags', 'published', 'deleted', 'revision', 'created_by', 'updated_by', 'created_at', 'updated_at']
    result = {k: getattr(lecture, k) for k in keys}
    if detail:
        result.update(markdown=lecture.markdown, import_report=lecture.import_report, has_original=bool(lecture.original_file), original_extension=Path(lecture.original_file).suffix if lecture.original_file else '', **render(lecture.markdown))
    return result


def index(db, lecture):
    db.execute(delete(Reference).where(Reference.lecture_id == lecture.id))
    for ref in render(lecture.markdown)['references']:
        db.add(Reference(lecture_id=lecture.id, ordinal=ref['ordinal'], payload=ref))


def history(db, lecture, user):
    db.add(History(lecture_id=lecture.id, title=lecture.title, author=lecture.author, sermon_date=lecture.sermon_date, markdown=lecture.markdown, category=lecture.category, tags=lecture.tags, revision=lecture.revision, user_id=user.id))
    index(db, lecture)

@router.post('/render')
def preview_markdown(data: Preview, user=Depends(admin)):
    return render(data.markdown)

@router.get('/lectures')
def listing(q: str = '', trash: bool = False, user=Depends(current_user), db=Depends(get_db)):
    stmt = select(Lecture).where(Lecture.deleted == (trash if user.role == 'admin' else False))
    if user.role != 'admin':
        stmt = stmt.where(Lecture.published == True)
    if q:
        stmt = stmt.where(or_(Lecture.title.contains(q, autoescape=True), Lecture.author.contains(q, autoescape=True), Lecture.markdown.contains(q, autoescape=True), Lecture.category.contains(q, autoescape=True)))
    return [serialize(item) for item in db.scalars(stmt.order_by(Lecture.updated_at.desc()))]

@router.post('/lectures')
def create(data: Content, user=Depends(admin), db=Depends(get_db)):
    item = Lecture(**data.model_dump(exclude={'revision'}), created_by=user.id, updated_by=user.id, published=False, deleted=False, revision=1)
    db.add(item)
    db.flush()
    history(db, item, user)
    return serialize(item, True)

@router.get('/lectures/{lecture_id}')
def detail(lecture_id: int, user=Depends(current_user), db=Depends(get_db)):
    return serialize(visible(db, lecture_id, user), True)

@router.put('/lectures/{lecture_id}')
def save(lecture_id: int, data: Content, user=Depends(admin), db=Depends(get_db)):
    item = visible(db, lecture_id, user)
    if item.deleted:
        raise HTTPException(409, '请先从回收站恢复讲义')
    if data.revision != item.revision:
        raise HTTPException(409, '讲义已更新，请重新打开后再保存')
    for key, value in data.model_dump(exclude={'revision'}).items():
        setattr(item, key, value)
    item.revision += 1
    item.updated_by, item.updated_at = user.id, now()
    history(db, item, user)
    return serialize(item, True)

@router.patch('/lectures/{lecture_id}/publish')
def publish(lecture_id: int, data: Publish, user=Depends(admin), db=Depends(get_db)):
    item = visible(db, lecture_id, user)
    if item.deleted:
        raise HTTPException(409, '回收站中的讲义不能发布')
    item.published = data.published
    item.updated_by, item.updated_at = user.id, now()
    return serialize(item, True)

@router.patch('/lectures/{lecture_id}/trash')
def trash(lecture_id: int, data: Trash, user=Depends(admin), db=Depends(get_db)):
    item = visible(db, lecture_id, user)
    item.deleted = data.deleted
    if data.deleted:
        item.published = False
    item.updated_by, item.updated_at = user.id, now()
    return {'ok': True}

@router.get('/lectures/{lecture_id}/history')
def histories(lecture_id: int, user=Depends(admin), db=Depends(get_db)):
    visible(db, lecture_id, user)
    return [{'id': h.id, 'revision': h.revision, 'title': h.title, 'author': h.author, 'sermon_date': h.sermon_date, 'markdown': h.markdown, 'created_at': h.created_at} for h in db.scalars(select(History).where(History.lecture_id == lecture_id).order_by(History.revision.desc()))]

@router.post('/lectures/{lecture_id}/history/{history_id}/restore')
def restore_history(lecture_id: int, history_id: int, user=Depends(admin), db=Depends(get_db)):
    item = visible(db, lecture_id, user)
    previous = db.get(History, history_id)
    if item.deleted or not previous or previous.lecture_id != lecture_id:
        raise HTTPException(404, '版本不存在或讲义已删除')
    for field in ('title', 'author', 'sermon_date', 'markdown', 'category', 'tags'):
        setattr(item, field, getattr(previous, field))
    item.revision += 1
    item.updated_by, item.updated_at = user.id, now()
    history(db, item, user)
    return serialize(item, True)

@router.get('/lectures/{lecture_id}/export')
def export(lecture_id: int, user=Depends(admin), db=Depends(get_db)):
    item = visible(db, lecture_id, user)
    return Response(item.markdown, media_type='text/markdown; charset=utf-8', headers={'Content-Disposition': f'attachment; filename="lecture-{item.id}.md"'})

@router.get('/lectures/{lecture_id}/original')
def original(lecture_id: int, user=Depends(admin), db=Depends(get_db)):
    item = visible(db, lecture_id, user)
    if not item.original_file or not (DATA_DIR / 'originals' / item.original_file).is_file():
        raise HTTPException(404, '没有原始文件')
    return Response((DATA_DIR / 'originals' / item.original_file).read_bytes(), media_type='application/octet-stream', headers={'Content-Disposition': f'attachment; filename="original{Path(item.original_file).suffix}"'})


def convert_docx(path):
    warnings = []
    try:
        with zipfile.ZipFile(path) as archive:
            if sum(i.file_size for i in archive.infolist()) > 80 * 1024 * 1024:
                raise HTTPException(422, 'Word 解压后过大')
            xml = archive.read('word/document.xml')
            root = ET.fromstring(xml)
            names = {node.tag.split('}')[-1] for node in root.iter()}
            checks = {'tbl': '表格', 'drawing': '图片或图形', 'pict': '图片或文本框', 'footnoteReference': '脚注', 'endnoteReference': '尾注', 'object': '嵌入对象', 'oMath': '公式', 'txbxContent': '文本框', 'ins': '修订', 'del': '删除修订'}
            for tag, label in checks.items():
                if tag in names:
                    warnings.append(f'检测到{label}，超出首版完整性保证范围，请对照原始文件核对。')
            if any(any((node.text or '').strip() for node in ET.fromstring(archive.read(n)).iter() if node.tag.endswith('}t')) for n in archive.namelist() if re.match(r'word/(header|footer|comments)\d*\.xml', n)):
                warnings.append('检测到页眉、页脚或批注，请核对原始文件；它们可能未进入正文。')
            source_text = ''.join(node.text or '' for node in root.iter() if node.tag.endswith('}t'))
    except (zipfile.BadZipFile, KeyError, ET.ParseError):
        raise HTTPException(422, '不是有效的 Word .docx 文件')
    try:
        import pypandoc
        proc = subprocess.run([pypandoc.get_pandoc_path(), str(path), '-f', 'docx', '-t', 'gfm', '--wrap=none', '--track-changes=all'], capture_output=True, text=True, timeout=60)
        if proc.returncode:
            raise HTTPException(422, 'Word 转换失败，请检查原始文件')
        markdown = proc.stdout
        if proc.stderr:
            warnings.append('转换工具报告了格式兼容提示，请核对预览。')
    except (OSError, RuntimeError):
        raise HTTPException(503, '缺少 Pandoc，请安装后重试')
    except subprocess.TimeoutExpired:
        raise HTTPException(422, '转换超时，请拆分文档后重试')
    # Check text as an ordered subsequence: catches dropped text, tolerates Markdown punctuation.
    target = re.sub(r'\s+', '', markdown)
    cursor = iter(target)
    if not all(any(c == candidate for candidate in cursor) for c in re.sub(r'\s+', '', source_text)):
        warnings.append('正文完整性自动核对未通过，请对照原始 Word 检查后再确认导入。')
    if source_text.strip() and not markdown.strip():
        raise HTTPException(422, '转换结果为空，已中止导入')
    return markdown, warnings

@router.post('/imports/preview')
def import_preview(file: UploadFile = File(...), user=Depends(admin)):
    extension = Path(file.filename or '').suffix.lower()
    if extension not in ('.docx', '.md'):
        raise HTTPException(422, '仅支持 .docx 和 UTF-8 .md 文件')
    data = file.file.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, '文件不能超过 20 MB')
    preview_id = uuid.uuid4().hex
    pending = DATA_DIR / 'pending'
    pending.mkdir(exist_ok=True)
    path = pending / (preview_id + extension)
    path.write_bytes(data)
    try:
        if extension == '.docx':
            markdown, warnings = convert_docx(path)
        else:
            try:
                markdown = data.decode('utf-8-sig')
            except UnicodeDecodeError:
                raise HTTPException(422, 'Markdown 文件必须为 UTF-8 编码')
            warnings = []
        if len(markdown) > 2_000_000:
            raise HTTPException(422, '正文超过 200 万字符，请拆分导入')
        report = {'owner': user.id, 'markdown': markdown, 'warnings': warnings, 'filename': path.name, 'created_at': now().isoformat()}
        (pending / (preview_id + '.json')).write_text(json.dumps(report, ensure_ascii=False), encoding='utf-8')
        return {'preview_id': preview_id, 'title': Path(file.filename).stem, 'author': '', 'sermon_date': None, 'category': '', 'tags': '', 'markdown': markdown, 'warnings': warnings, **render(markdown)}
    except Exception:
        path.unlink(missing_ok=True)
        raise

@router.post('/imports/confirm')
def confirm_import(data: Confirm, user=Depends(admin), db=Depends(get_db)):
    pending = DATA_DIR / 'pending'
    report_path = pending / (data.preview_id + '.json')
    if not report_path.exists():
        raise HTTPException(404, '导入预览已失效，请重新选择文件')
    report = json.loads(report_path.read_text())
    if report['owner'] != user.id:
        raise HTTPException(403, '不能确认其他用户的导入')
    filename = report['filename']
    target = DATA_DIR / 'originals' / filename
    target.write_bytes((pending / filename).read_bytes())
    try:
        item = Lecture(title=data.title, author=data.author, sermon_date=data.sermon_date, markdown=report['markdown'], category=data.category, tags=data.tags, created_by=user.id, updated_by=user.id, original_file=filename, import_report=report['warnings'], revision=1, published=False, deleted=False)
        db.add(item)
        db.flush()
        history(db, item, user)
        db.commit()
    except Exception:
        target.unlink(missing_ok=True)
        raise
    report_path.unlink(missing_ok=True)
    (pending / filename).unlink(missing_ok=True)
    return serialize(item, True)
