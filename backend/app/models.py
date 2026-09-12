from datetime import date, datetime, timezone
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, ForeignKeyConstraint, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class Guard(Base):
    __tablename__ = 'guards'
    id: Mapped[int] = mapped_column(primary_key=True)


class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True)
    display_name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default='reader')
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Session(Base):
    __tablename__ = 'sessions'
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    expires_at: Mapped[datetime] = mapped_column(DateTime)


class Lecture(Base):
    __tablename__ = 'lectures'
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    author: Mapped[str] = mapped_column(String(100), default='')
    sermon_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    category: Mapped[str] = mapped_column(String(100), default='')
    tags: Mapped[list] = mapped_column(JSON, default=list)
    markdown: Mapped[str] = mapped_column(Text().with_variant(LONGTEXT(), 'mysql'))
    published: Mapped[bool] = mapped_column(Boolean, default=False)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    updated_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    original_file: Mapped[str | None] = mapped_column(String(255), nullable=True)
    import_report: Mapped[list] = mapped_column(JSON, default=list)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class History(Base):
    __tablename__ = 'histories'
    id: Mapped[int] = mapped_column(primary_key=True)
    lecture_id: Mapped[int] = mapped_column(ForeignKey('lectures.id'))
    title: Mapped[str] = mapped_column(String(255))
    author: Mapped[str] = mapped_column(String(100), default='')
    sermon_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    markdown: Mapped[str] = mapped_column(Text().with_variant(LONGTEXT(), 'mysql'))
    category: Mapped[str] = mapped_column(String(100))
    tags: Mapped[list] = mapped_column(JSON)
    revision: Mapped[int] = mapped_column(Integer)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Reference(Base):
    __tablename__ = 'references'
    id: Mapped[int] = mapped_column(primary_key=True)
    lecture_id: Mapped[int] = mapped_column(ForeignKey('lectures.id'))
    ordinal: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict] = mapped_column(JSON)


class Translation(Base):
    __tablename__ = 'translations'
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(150))
    language: Mapped[str] = mapped_column(String(30))
    source: Mapped[str] = mapped_column(Text, default='')
    revision: Mapped[int] = mapped_column(Integer, default=1)


class Testament(Base):
    __tablename__ = 'bible_testaments'
    code: Mapped[str] = mapped_column(String(2), primary_key=True)
    name: Mapped[str] = mapped_column(String(20))
    position: Mapped[int] = mapped_column(Integer, unique=True)


class Book(Base):
    __tablename__ = 'bible_books'
    code: Mapped[str] = mapped_column(String(12), primary_key=True)
    testament_code: Mapped[str] = mapped_column(ForeignKey('bible_testaments.code'))
    name: Mapped[str] = mapped_column(String(50))
    position: Mapped[int] = mapped_column(Integer, unique=True)
    chapter_count: Mapped[int] = mapped_column(Integer)


class Chapter(Base):
    __tablename__ = 'bible_chapters'
    book: Mapped[str] = mapped_column(ForeignKey('bible_books.code'), primary_key=True)
    number: Mapped[int] = mapped_column(Integer, primary_key=True)
    reference_verse_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(String(255), default='')


class Verse(Base):
    __tablename__ = 'verses'
    __table_args__ = (UniqueConstraint('translation_id', 'book', 'chapter', 'verse'),
                      ForeignKeyConstraint(['book', 'chapter'], ['bible_chapters.book', 'bible_chapters.number'], name='fk_verses_chapter'))
    id: Mapped[int] = mapped_column(primary_key=True)
    translation_id: Mapped[int] = mapped_column(ForeignKey('translations.id'))
    book: Mapped[str] = mapped_column(String(12))
    chapter: Mapped[int] = mapped_column(Integer)
    verse: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
