"""Add author and sermon date to lectures and their history."""
from alembic import op
import sqlalchemy as sa

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade():
    # 0001 historically creates current Base.metadata on fresh installs. Only add
    # fields that are absent so both fresh installs and existing databases work.
    inspector = sa.inspect(op.get_bind())
    for table_name in ('lectures', 'histories'):
        existing = {column['name'] for column in inspector.get_columns(table_name)}
        with op.batch_alter_table(table_name) as batch:
            if 'author' not in existing:
                batch.add_column(sa.Column('author', sa.String(100), nullable=False, server_default=''))
            if 'sermon_date' not in existing:
                batch.add_column(sa.Column('sermon_date', sa.Date(), nullable=True))


def downgrade():
    with op.batch_alter_table('histories') as batch:
        batch.drop_column('sermon_date')
        batch.drop_column('author')
    with op.batch_alter_table('lectures') as batch:
        batch.drop_column('sermon_date')
        batch.drop_column('author')
