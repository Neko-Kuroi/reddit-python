# alembic/versions/XXXX_create_subreddits.py
import sqlalchemy as sa
from alembic import op

# Alembic がマイグレーションの順序を特定するための宣言
revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "subreddits",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuid_generate_v4()"),
                  nullable=False),
        sa.Column("name", sa.String(21), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column("inserted_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id")
    )
    op.create_index("ix_subreddits_name", "subreddits", ["name"], unique=True)
    op.create_index("ix_subreddits_owner_id", "subreddits", ["owner_id"])

def downgrade() -> None:
    op.drop_index("ix_subreddits_owner_id", table_name="subreddits")
    op.drop_index("ix_subreddits_name", table_name="subreddits")
    op.drop_table("subreddits")
