# alembic/versions/XXXX_enable_uuid_extension.py
from alembic import op

# Alembic がマイグレーションの順序を特定するための宣言
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

def downgrade() -> None:
    op.execute('DROP EXTENSION IF EXISTS "uuid-ossp"')
