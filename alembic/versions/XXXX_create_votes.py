# alembic/versions/XXXX_create_votes.py
import sqlalchemy as sa
from alembic import op

# Alembic がマイグレーションの順序を特定するための宣言
revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "votes",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuid_generate_v4()"),
                  nullable=False),
        sa.Column("value", sa.Integer(), nullable=False),          # +1 | -1
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("target_type", sa.String(10), nullable=False),   # "post" | "comment"
        sa.Column("target_id", sa.UUID(), nullable=False),
        sa.Column("inserted_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id")
    )
    # 1人1票の制約
    op.create_index("ix_votes_unique",
                    "votes", ["user_id", "target_type", "target_id"], unique=True)
    op.create_index("ix_votes_target",
                    "votes", ["target_type", "target_id"])

def downgrade() -> None:
    op.drop_index("ix_votes_target", table_name="votes")
    op.drop_index("ix_votes_unique", table_name="votes")
    op.drop_table("votes")
