from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select, update, delete
from app.database import get_db
from app.models import Annotation, Lecture, now
from app.security import current_user
from app.modules.lectures import visible
from app.modules.paragraphs import paragraphs

router = APIRouter(prefix='/api/annotations')


class Content(BaseModel):
    model_config = ConfigDict(extra='forbid')
    content: str = Field(min_length=1, max_length=10000)

    @field_validator('content')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('批注不能为空')
        return value.strip()


class Create(Content):
    lecture_id: int
    lecture_revision: int = Field(ge=1)
    paragraph_index: int = Field(ge=0)


class Edit(Content):
    revision: int = Field(ge=1)


def serialize(note, lecture, blocks):
    accessible = lecture is not None
    matches = [i for i, p in enumerate(blocks) if p['key'] == note.paragraph_key and p['quote'] == note.quote]
    target = matches[0] if len(matches) == 1 and note.paragraph_count == 1 else None
    if accessible and lecture.revision == note.lecture_revision and note.paragraph_index in matches:
        target = note.paragraph_index
    return dict(id=note.id, lecture_id=note.lecture_id,
        lecture_title=lecture.title if accessible else '讲义暂不可访问',
        lecture_revision=lecture.revision if accessible else None,
        content=note.content, quote=note.quote if accessible else '',
        paragraph_index=target, available=accessible, revision=note.revision,
        created_at=note.created_at, updated_at=note.updated_at)


def context(lecture, user):
    if not lecture or lecture.deleted or (user.role != 'admin' and not lecture.published):
        return None, []
    return lecture, paragraphs(lecture.markdown)


@router.get('')
def listing(lecture_id: int | None = None, offset: int = Query(0, ge=0),
            limit: int = Query(100, ge=1, le=200), user=Depends(current_user), db=Depends(get_db)):
    stmt = select(Annotation).where(Annotation.user_id == user.id)
    if lecture_id is not None:
        stmt = stmt.where(Annotation.lecture_id == lecture_id)
    notes = db.scalars(stmt.order_by(Annotation.updated_at.desc(), Annotation.id.desc()).offset(offset).limit(limit)).all()
    contexts = {lid: context(db.get(Lecture, lid), user) for lid in {n.lecture_id for n in notes}}
    return [serialize(n, *contexts[n.lecture_id]) for n in notes]


@router.post('')
def create(data: Create, user=Depends(current_user), db=Depends(get_db)):
    lecture = visible(db, data.lecture_id, user)
    if lecture.deleted or lecture.revision != data.lecture_revision:
        raise HTTPException(409, '讲义已更新，请重新打开后添加批注')
    blocks = paragraphs(lecture.markdown)
    if data.paragraph_index >= len(blocks):
        raise HTTPException(422, '段落不存在')
    block = blocks[data.paragraph_index]
    note = Annotation(user_id=user.id, **data.model_dump(), paragraph_key=block['key'], quote=block['quote'],
        paragraph_count=sum(p['quote'] == block['quote'] for p in blocks))
    db.add(note)
    db.flush()
    return serialize(note, lecture, blocks)


def owned(db, note_id, user):
    note = db.scalar(select(Annotation).where(Annotation.id == note_id, Annotation.user_id == user.id))
    if note is None:
        raise HTTPException(404, '批注不存在')
    return note


@router.get('/{note_id}')
def detail(note_id: int, user=Depends(current_user), db=Depends(get_db)):
    note = owned(db, note_id, user)
    return serialize(note, *context(db.get(Lecture, note.lecture_id), user))


@router.put('/{note_id}')
def edit(note_id: int, data: Edit, user=Depends(current_user), db=Depends(get_db)):
    note = owned(db, note_id, user)
    result = db.execute(update(Annotation).where(Annotation.id == note.id,
        Annotation.user_id == user.id, Annotation.revision == data.revision)
        .values(content=data.content, revision=data.revision + 1, updated_at=now()))
    if result.rowcount != 1:
        raise HTTPException(409, '批注已更新，请刷新后再编辑')
    db.flush()
    db.refresh(note)
    return serialize(note, *context(db.get(Lecture, note.lecture_id), user))


@router.delete('/{note_id}')
def remove(note_id: int, revision: int = Query(ge=1), user=Depends(current_user), db=Depends(get_db)):
    owned(db, note_id, user)
    result = db.execute(delete(Annotation).where(Annotation.id == note_id,
        Annotation.user_id == user.id, Annotation.revision == revision))
    if result.rowcount != 1:
        raise HTTPException(409, '批注已更新，请刷新后再删除')
    return {'ok': True}
