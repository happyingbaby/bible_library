import hashlib
import json
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import delete, select, func
from app.database import DATA_DIR, get_db
from app.models import Translation, Verse, Book, Lecture, Reference
from app.security import admin, current_user
from app.modules.references import ALIASES, BOOKS

router = APIRouter(prefix='/api')


@router.get('/verses/search')
def search_verses(q: str = Query(min_length=1, max_length=200),
                  offset: int = Query(default=0, ge=0),
                  limit: int = Query(default=100, ge=1, le=200),
                  user=Depends(current_user), db=Depends(get_db)):
    keyword = q.strip()
    if not keyword:
        raise HTTPException(422, '请输入检索关键词')
    # Literal substring matching: SQL wildcard characters are ordinary input.
    predicate = Verse.text.contains(keyword, autoescape=True)
    total = db.scalar(select(func.count(Verse.id)).where(predicate))
    rows = db.execute(select(Verse, Translation.name, Book.name)
        .join(Translation, Translation.id == Verse.translation_id)
        .join(Book, Book.code == Verse.book).where(predicate)
        .order_by(Book.position, Verse.chapter, Verse.verse, Verse.translation_id)
        .offset(offset).limit(limit))
    return dict(total=total, items=[dict(id=v.id, translation_id=v.translation_id,
        translation_name=translation_name, book=v.book, book_name=book_name,
        chapter=v.chapter, verse=v.verse, text=v.text)
        for v, translation_name, book_name in rows])


@router.get('/verses/lectures')
def verse_lectures(book: str, chapter: int = Query(ge=1, le=150),
                   verse: int = Query(ge=1, le=176),
                   user=Depends(current_user), db=Depends(get_db)):
    from app.modules.lectures import serialize
    book = ALIASES.get(book.lower(), book)
    if book not in BOOKS or chapter > BOOKS[book]['chapters']:
        raise HTTPException(422, '章节范围错误')
    payload = Reference.payload
    matching = select(Reference.lecture_id).where(
        payload['status'].as_string() == 'valid',
        payload['book'].as_string() == book,
        payload['chapter'].as_integer() == chapter,
        payload['start'].as_integer() <= verse,
        payload['end'].as_integer() >= verse)
    stmt = select(Lecture).where(Lecture.deleted == False, Lecture.id.in_(matching))
    if user.role != 'admin':
        stmt = stmt.where(Lecture.published == True)
    # IN avoids duplicates when a lecture cites the same verse repeatedly.
    return [serialize(item, True) for item in db.scalars(
        stmt.order_by(Lecture.updated_at.desc(), Lecture.id.desc()))]

class VerseInput(BaseModel):
    book: str
    chapter: int = Field(ge=1, le=150)
    verse: int = Field(ge=1, le=176)
    text: str = Field(min_length=1, max_length=10000)

class TranslationInput(BaseModel):
    code: str = Field(pattern=r'^[A-Za-z0-9_-]{1,80}$')
    name: str = Field(min_length=1, max_length=150)
    language: str = Field(min_length=1, max_length=30)
    source: str = Field(default='', max_length=2000)
    verses: list[VerseInput] = Field(min_length=1, max_length=50000)

class Confirmation(BaseModel):
    preview_id: str = Field(pattern=r'^[a-f0-9]{32}$')

@router.get('/books')
def books(user=Depends(current_user)):
    return list(BOOKS.values())

@router.get('/translations')
def translations(user=Depends(current_user), db=Depends(get_db)):
    return [{'id': t.id, 'code': t.code, 'name': t.name, 'language': t.language, 'source': t.source, 'revision': t.revision} for t in db.scalars(select(Translation).order_by(Translation.id))]

@router.get('/verses')
def verses(translation_id: int, book: str, chapter: int, start: int = Query(ge=1, le=176), end: int = Query(ge=1, le=176), user=Depends(current_user), db=Depends(get_db)):
    book = ALIASES.get(book.lower(), book)
    if book not in BOOKS or not 1 <= chapter <= BOOKS[book]['chapters'] or end < start:
        raise HTTPException(422, '章节范围错误')
    if not db.get(Translation, translation_id):
        raise HTTPException(404, '译本不存在')
    rows = db.scalars(select(Verse).where(Verse.translation_id == translation_id, Verse.book == book, Verse.chapter == chapter, Verse.verse.between(start, end)))
    texts = {v.verse: v.text for v in rows}
    return [{'verse': number, 'text': texts.get(number), 'missing': number not in texts} for number in range(start, end + 1)]

@router.post('/translations/preview')
def preview(data: TranslationInput, user=Depends(admin), db=Depends(get_db)):
    rows, seen, chapters = [], set(), {}
    for v in data.verses:
        book = ALIASES.get(v.book.lower())
        if not book or v.chapter > BOOKS[book]['chapters'] or not v.text.strip():
            raise HTTPException(422, f'无效经文：{v.book} {v.chapter}:{v.verse}')
        key = (book, v.chapter, v.verse)
        if key in seen:
            raise HTTPException(422, f'重复经节：{book} {v.chapter}:{v.verse}')
        seen.add(key)
        chapters.setdefault((book, v.chapter), set()).add(v.verse)
        rows.append({'book': book, 'chapter': v.chapter, 'verse': v.verse, 'text': v.text.strip()})
    warnings = []
    for (book, chapter), numbers in chapters.items():
        missing = sorted(set(range(1, max(numbers) + 1)) - numbers)
        if missing:
            warnings.append(f'{BOOKS[book]["name"]} {chapter} 章缺少经节：' + ', '.join(map(str, missing)))
    warnings.append('仅检查已提供章节中的编号间隙；不据此判定整本圣经完整，也不推断各译本的最后一节。')
    existing = db.scalar(select(Translation).where(Translation.code == data.code))
    old = {(v.book, v.chapter, v.verse): v.text for v in db.scalars(select(Verse).where(Verse.translation_id == existing.id))} if existing else {}
    new = {(v['book'], v['chapter'], v['verse']): v['text'] for v in rows}
    changes = []
    for key in sorted(old.keys() | new.keys()):
        if old.get(key) != new.get(key):
            changes.append({'book': key[0], 'chapter': key[1], 'verse': key[2], 'before': old.get(key), 'after': new.get(key), 'kind': 'added' if key not in old else 'removed' if key not in new else 'changed'})
    payload = data.model_dump()
    payload['verses'] = rows
    preview_id = uuid.uuid4().hex
    directory = DATA_DIR / 'scripture_pending'
    directory.mkdir(exist_ok=True)
    (directory / (preview_id + '.json')).write_text(json.dumps({'owner': user.id, 'revision': existing.revision if existing else 0, 'payload': payload}, ensure_ascii=False), encoding='utf-8')
    return {'preview_id': preview_id, 'warnings': warnings, 'existing': bool(existing), 'count': len(rows), 'summary': {kind: sum(c['kind'] == kind for c in changes) for kind in ('added', 'changed', 'removed')}, 'changes': changes}

@router.post('/translations/confirm')
def confirm(data: Confirmation, user=Depends(admin), db=Depends(get_db)):
    path = DATA_DIR / 'scripture_pending' / (data.preview_id + '.json')
    if not path.is_file():
        raise HTTPException(404, '预览不存在，请重新导入')
    preview = json.loads(path.read_text())
    if preview['owner'] != user.id:
        raise HTTPException(403, '不能确认其他用户的导入')
    payload = preview['payload']
    translation = db.scalar(select(Translation).where(Translation.code == payload['code']).with_for_update())
    if (translation.revision if translation else 0) != preview['revision']:
        raise HTTPException(409, '译本已更改，请重新预览差异')
    if translation:
        db.execute(delete(Verse).where(Verse.translation_id == translation.id))
        translation.revision += 1
        for key in ('name', 'language', 'source'):
            setattr(translation, key, payload[key])
    else:
        translation = Translation(**{k: payload[k] for k in ('code', 'name', 'language', 'source')})
        db.add(translation)
        db.flush()
    db.execute(Verse.__table__.insert(), [{'translation_id': translation.id, **v} for v in payload['verses']])
    db.commit()
    path.unlink(missing_ok=True)
    return {'ok': True}


class TranslationMetadata(BaseModel):
    code: str = Field(pattern=r'^[A-Za-z0-9_-]{1,80}$')
    name: str = Field(min_length=1, max_length=150)
    language: str = Field(min_length=1, max_length=30)
    source: str = Field(default='', max_length=2000)


class VerseEdit(BaseModel):
    text: str = Field(min_length=1, max_length=10000)
    revision: int = Field(ge=1)


@router.get('/bible/catalog')
def catalog(user=Depends(current_user), db=Depends(get_db)):
    from app.models import Testament, Book
    books = list(db.scalars(select(Book).order_by(Book.position)))
    return [dict(code=t.code, name=t.name, books=[dict(code=b.code, name=b.name,
        chapters=b.chapter_count, position=b.position) for b in books if b.testament_code == t.code])
        for t in db.scalars(select(Testament).order_by(Testament.position))]


@router.get('/bible/books/{book}/chapters')
def chapter_list(book: str, translation_id: int | None = None, user=Depends(current_user), db=Depends(get_db)):
    from app.models import Book, Chapter
    from sqlalchemy import func
    if not db.get(Book, book):
        raise HTTPException(404, '书卷不存在')
    if translation_id is not None and not db.get(Translation, translation_id):
        raise HTTPException(404, '译本不存在')
    counts = dict(db.execute(select(Verse.chapter, func.count(Verse.id)).where(
        Verse.book == book, Verse.translation_id == translation_id).group_by(Verse.chapter)).all())
    return [dict(number=c.number, reference_verse_count=c.reference_verse_count,
        source=c.source, stored_count=counts.get(c.number, 0))
        for c in db.scalars(select(Chapter).where(Chapter.book == book).order_by(Chapter.number))]


@router.get('/bible/translations/{translation_id}/{book}/{chapter}')
def chapter_content(translation_id: int, book: str, chapter: int, user=Depends(current_user), db=Depends(get_db)):
    from app.models import Chapter
    translation = db.get(Translation, translation_id)
    if not translation or not db.get(Chapter, (book, chapter)):
        raise HTTPException(404, '译本或章节不存在')
    return dict(revision=translation.revision, verses=[dict(verse=v.verse, text=v.text)
        for v in db.scalars(select(Verse).where(Verse.translation_id == translation_id,
            Verse.book == book, Verse.chapter == chapter).order_by(Verse.verse))])


@router.post('/translations')
def create_translation(data: TranslationMetadata, user=Depends(admin), db=Depends(get_db)):
    from sqlalchemy.exc import IntegrityError
    if not data.name.strip() or not data.language.strip():
        raise HTTPException(422, '译本名称和语言不能为空')
    if db.scalar(select(Translation).where(Translation.code == data.code)):
        raise HTTPException(409, '译本代码已存在')
    translation = Translation(**data.model_dump())
    db.add(translation)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, '译本代码已存在')
    return dict(id=translation.id)


def editable_translation(db, translation_id, book, chapter, verse, revision):
    from app.models import Chapter
    if not 1 <= verse <= 176 or not db.get(Chapter, (book, chapter)):
        raise HTTPException(422, '章节或节号无效')
    translation = db.scalar(select(Translation).where(Translation.id == translation_id).with_for_update())
    if not translation:
        raise HTTPException(404, '译本不存在')
    if translation.revision != revision:
        raise HTTPException(409, '译本已更改，请刷新章节后重新编辑；当前输入仍保留')
    return translation


@router.put('/bible/translations/{translation_id}/{book}/{chapter}/{verse}')
def save_verse(translation_id: int, book: str, chapter: int, verse: int, data: VerseEdit,
               user=Depends(admin), db=Depends(get_db)):
    if not data.text.strip():
        raise HTTPException(422, '经文正文不能为空')
    translation = editable_translation(db, translation_id, book, chapter, verse, data.revision)
    row = db.scalar(select(Verse).where(Verse.translation_id == translation_id, Verse.book == book,
        Verse.chapter == chapter, Verse.verse == verse))
    if row:
        row.text = data.text.strip()
    else:
        db.add(Verse(translation_id=translation_id, book=book, chapter=chapter, verse=verse, text=data.text.strip()))
    translation.revision += 1
    db.flush()
    return dict(revision=translation.revision)


@router.delete('/bible/translations/{translation_id}/{book}/{chapter}/{verse}')
def delete_verse(translation_id: int, book: str, chapter: int, verse: int, revision: int = Query(ge=1),
                 user=Depends(admin), db=Depends(get_db)):
    translation = editable_translation(db, translation_id, book, chapter, verse, revision)
    row = db.scalar(select(Verse).where(Verse.translation_id == translation_id, Verse.book == book,
        Verse.chapter == chapter, Verse.verse == verse))
    if not row:
        raise HTTPException(404, '该节经文尚未录入')
    db.delete(row)
    translation.revision += 1
    return dict(revision=translation.revision)
