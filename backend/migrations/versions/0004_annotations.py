"""Personal paragraph annotations."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import LONGTEXT

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade():
    # 0001 creates current metadata on fresh databases.
    if 'annotations' in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table('annotations',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('user_id', sa.Integer, sa.ForeignKey('users.id'), nullable=False),
        sa.Column('lecture_id', sa.Integer, sa.ForeignKey('lectures.id'), nullable=False),
        sa.Column('paragraph_key', sa.String(64), nullable=False),
        sa.Column('paragraph_index', sa.Integer, nullable=False),
        sa.Column('paragraph_count', sa.Integer, nullable=False),
        sa.Column('lecture_revision', sa.Integer, nullable=False),
        sa.Column('quote', sa.Text().with_variant(LONGTEXT(), 'mysql'), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('revision', sa.Integer, nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False))
    op.create_index('ix_annotations_user_id', 'annotations', ['user_id'])
    op.create_index('ix_annotations_lecture_id', 'annotations', ['lecture_id'])


def downgrade():
    op.drop_table('annotations')
