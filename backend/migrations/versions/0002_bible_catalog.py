"""Persist the canonical Bible directory while preserving existing verse text."""
from alembic import op
import sqlalchemy as sa

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None

BOOKS = [{'code': 'Gen', 'name': '创世记', 'chapter_count': 50, 'position': 1, 'testament_code': 'OT'}, {'code': 'Exod', 'name': '出埃及记', 'chapter_count': 40, 'position': 2, 'testament_code': 'OT'}, {'code': 'Lev', 'name': '利未记', 'chapter_count': 27, 'position': 3, 'testament_code': 'OT'}, {'code': 'Num', 'name': '民数记', 'chapter_count': 36, 'position': 4, 'testament_code': 'OT'}, {'code': 'Deut', 'name': '申命记', 'chapter_count': 34, 'position': 5, 'testament_code': 'OT'}, {'code': 'Josh', 'name': '约书亚记', 'chapter_count': 24, 'position': 6, 'testament_code': 'OT'}, {'code': 'Judg', 'name': '士师记', 'chapter_count': 21, 'position': 7, 'testament_code': 'OT'}, {'code': 'Ruth', 'name': '路得记', 'chapter_count': 4, 'position': 8, 'testament_code': 'OT'}, {'code': '1Sam', 'name': '撒母耳记上', 'chapter_count': 31, 'position': 9, 'testament_code': 'OT'}, {'code': '2Sam', 'name': '撒母耳记下', 'chapter_count': 24, 'position': 10, 'testament_code': 'OT'}, {'code': '1Kgs', 'name': '列王纪上', 'chapter_count': 22, 'position': 11, 'testament_code': 'OT'}, {'code': '2Kgs', 'name': '列王纪下', 'chapter_count': 25, 'position': 12, 'testament_code': 'OT'}, {'code': '1Chr', 'name': '历代志上', 'chapter_count': 29, 'position': 13, 'testament_code': 'OT'}, {'code': '2Chr', 'name': '历代志下', 'chapter_count': 36, 'position': 14, 'testament_code': 'OT'}, {'code': 'Ezra', 'name': '以斯拉记', 'chapter_count': 10, 'position': 15, 'testament_code': 'OT'}, {'code': 'Neh', 'name': '尼希米记', 'chapter_count': 13, 'position': 16, 'testament_code': 'OT'}, {'code': 'Esth', 'name': '以斯帖记', 'chapter_count': 10, 'position': 17, 'testament_code': 'OT'}, {'code': 'Job', 'name': '约伯记', 'chapter_count': 42, 'position': 18, 'testament_code': 'OT'}, {'code': 'Ps', 'name': '诗篇', 'chapter_count': 150, 'position': 19, 'testament_code': 'OT'}, {'code': 'Prov', 'name': '箴言', 'chapter_count': 31, 'position': 20, 'testament_code': 'OT'}, {'code': 'Eccl', 'name': '传道书', 'chapter_count': 12, 'position': 21, 'testament_code': 'OT'}, {'code': 'Song', 'name': '雅歌', 'chapter_count': 8, 'position': 22, 'testament_code': 'OT'}, {'code': 'Isa', 'name': '以赛亚书', 'chapter_count': 66, 'position': 23, 'testament_code': 'OT'}, {'code': 'Jer', 'name': '耶利米书', 'chapter_count': 52, 'position': 24, 'testament_code': 'OT'}, {'code': 'Lam', 'name': '耶利米哀歌', 'chapter_count': 5, 'position': 25, 'testament_code': 'OT'}, {'code': 'Ezek', 'name': '以西结书', 'chapter_count': 48, 'position': 26, 'testament_code': 'OT'}, {'code': 'Dan', 'name': '但以理书', 'chapter_count': 12, 'position': 27, 'testament_code': 'OT'}, {'code': 'Hos', 'name': '何西阿书', 'chapter_count': 14, 'position': 28, 'testament_code': 'OT'}, {'code': 'Joel', 'name': '约珥书', 'chapter_count': 3, 'position': 29, 'testament_code': 'OT'}, {'code': 'Amos', 'name': '阿摩司书', 'chapter_count': 9, 'position': 30, 'testament_code': 'OT'}, {'code': 'Obad', 'name': '俄巴底亚书', 'chapter_count': 1, 'position': 31, 'testament_code': 'OT'}, {'code': 'Jonah', 'name': '约拿书', 'chapter_count': 4, 'position': 32, 'testament_code': 'OT'}, {'code': 'Mic', 'name': '弥迦书', 'chapter_count': 7, 'position': 33, 'testament_code': 'OT'}, {'code': 'Nah', 'name': '那鸿书', 'chapter_count': 3, 'position': 34, 'testament_code': 'OT'}, {'code': 'Hab', 'name': '哈巴谷书', 'chapter_count': 3, 'position': 35, 'testament_code': 'OT'}, {'code': 'Zeph', 'name': '西番雅书', 'chapter_count': 3, 'position': 36, 'testament_code': 'OT'}, {'code': 'Hag', 'name': '哈该书', 'chapter_count': 2, 'position': 37, 'testament_code': 'OT'}, {'code': 'Zech', 'name': '撒迦利亚书', 'chapter_count': 14, 'position': 38, 'testament_code': 'OT'}, {'code': 'Mal', 'name': '玛拉基书', 'chapter_count': 4, 'position': 39, 'testament_code': 'OT'}, {'code': 'Matt', 'name': '马太福音', 'chapter_count': 28, 'position': 40, 'testament_code': 'NT'}, {'code': 'Mark', 'name': '马可福音', 'chapter_count': 16, 'position': 41, 'testament_code': 'NT'}, {'code': 'Luke', 'name': '路加福音', 'chapter_count': 24, 'position': 42, 'testament_code': 'NT'}, {'code': 'John', 'name': '约翰福音', 'chapter_count': 21, 'position': 43, 'testament_code': 'NT'}, {'code': 'Acts', 'name': '使徒行传', 'chapter_count': 28, 'position': 44, 'testament_code': 'NT'}, {'code': 'Rom', 'name': '罗马书', 'chapter_count': 16, 'position': 45, 'testament_code': 'NT'}, {'code': '1Cor', 'name': '哥林多前书', 'chapter_count': 16, 'position': 46, 'testament_code': 'NT'}, {'code': '2Cor', 'name': '哥林多后书', 'chapter_count': 13, 'position': 47, 'testament_code': 'NT'}, {'code': 'Gal', 'name': '加拉太书', 'chapter_count': 6, 'position': 48, 'testament_code': 'NT'}, {'code': 'Eph', 'name': '以弗所书', 'chapter_count': 6, 'position': 49, 'testament_code': 'NT'}, {'code': 'Phil', 'name': '腓立比书', 'chapter_count': 4, 'position': 50, 'testament_code': 'NT'}, {'code': 'Col', 'name': '歌罗西书', 'chapter_count': 4, 'position': 51, 'testament_code': 'NT'}, {'code': '1Thess', 'name': '帖撒罗尼迦前书', 'chapter_count': 5, 'position': 52, 'testament_code': 'NT'}, {'code': '2Thess', 'name': '帖撒罗尼迦后书', 'chapter_count': 3, 'position': 53, 'testament_code': 'NT'}, {'code': '1Tim', 'name': '提摩太前书', 'chapter_count': 6, 'position': 54, 'testament_code': 'NT'}, {'code': '2Tim', 'name': '提摩太后书', 'chapter_count': 4, 'position': 55, 'testament_code': 'NT'}, {'code': 'Titus', 'name': '提多书', 'chapter_count': 3, 'position': 56, 'testament_code': 'NT'}, {'code': 'Phlm', 'name': '腓利门书', 'chapter_count': 1, 'position': 57, 'testament_code': 'NT'}, {'code': 'Heb', 'name': '希伯来书', 'chapter_count': 13, 'position': 58, 'testament_code': 'NT'}, {'code': 'Jas', 'name': '雅各书', 'chapter_count': 5, 'position': 59, 'testament_code': 'NT'}, {'code': '1Pet', 'name': '彼得前书', 'chapter_count': 5, 'position': 60, 'testament_code': 'NT'}, {'code': '2Pet', 'name': '彼得后书', 'chapter_count': 3, 'position': 61, 'testament_code': 'NT'}, {'code': '1John', 'name': '约翰一书', 'chapter_count': 5, 'position': 62, 'testament_code': 'NT'}, {'code': '2John', 'name': '约翰二书', 'chapter_count': 1, 'position': 63, 'testament_code': 'NT'}, {'code': '3John', 'name': '约翰三书', 'chapter_count': 1, 'position': 64, 'testament_code': 'NT'}, {'code': 'Jude', 'name': '犹大书', 'chapter_count': 1, 'position': 65, 'testament_code': 'NT'}, {'code': 'Rev', 'name': '启示录', 'chapter_count': 22, 'position': 66, 'testament_code': 'NT'}]

def upgrade():
    bind = op.get_bind()
    metadata = sa.MetaData()
    testaments = sa.Table('bible_testaments', metadata,
        sa.Column('code', sa.String(2), primary_key=True),
        sa.Column('name', sa.String(20), nullable=False),
        sa.Column('position', sa.Integer, nullable=False, unique=True))
    books = sa.Table('bible_books', metadata,
        sa.Column('code', sa.String(12), primary_key=True),
        sa.Column('testament_code', sa.String(2), sa.ForeignKey('bible_testaments.code'), nullable=False),
        sa.Column('name', sa.String(50), nullable=False),
        sa.Column('position', sa.Integer, nullable=False, unique=True),
        sa.Column('chapter_count', sa.Integer, nullable=False))
    chapters = sa.Table('bible_chapters', metadata,
        sa.Column('book', sa.String(12), sa.ForeignKey('bible_books.code'), primary_key=True),
        sa.Column('number', sa.Integer, primary_key=True),
        sa.Column('reference_verse_count', sa.Integer, nullable=True),
        sa.Column('source', sa.String(255), nullable=False))
    # 0001 historically creates current Base.metadata; checkfirst supports both
    # fresh installs and upgrades without rewriting the old migration.
    metadata.create_all(bind, checkfirst=True)
    op.bulk_insert(testaments, [dict(code='OT', name='旧约', position=1), dict(code='NT', name='新约', position=2)])
    op.bulk_insert(books, BOOKS)
    op.bulk_insert(chapters, [dict(book=b['code'], number=n,
        reference_verse_count=31 if b['code']=='Gen' and n==1 else None,
        source='https://live.lxfyt.cn/shengjing/genesis_1_1.html' if b['code']=='Gen' and n==1 else '')
        for b in BOOKS for n in range(1, b['chapter_count']+1)])
    if not any(f['name']=='fk_verses_chapter' for f in sa.inspect(bind).get_foreign_keys('verses')):
        with op.batch_alter_table('verses') as batch:
            batch.create_foreign_key('fk_verses_chapter', 'bible_chapters', ['book', 'chapter'], ['book', 'number'])


def downgrade():
    with op.batch_alter_table('verses') as batch:
        batch.drop_constraint('fk_verses_chapter', type_='foreignkey')
    op.drop_table('bible_chapters')
    op.drop_table('bible_books')
    op.drop_table('bible_testaments')
