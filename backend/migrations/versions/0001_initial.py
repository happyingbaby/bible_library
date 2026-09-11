"""Initial schema for the offline lecture library."""
from alembic import op
from app.models import Base, Guard
revision = '0001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    Base.metadata.create_all(op.get_bind())
    op.bulk_insert(Guard.__table__, [{'id': 1}])

def downgrade():
    Base.metadata.drop_all(op.get_bind())
