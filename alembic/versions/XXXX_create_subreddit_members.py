# alembic/versions/XXXX_create_subreddit_members.py
import sqlalchemy as sa
from alembic import op

# Alembic がマイグレーションの順序を特定するための宣言
revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "subreddit_members",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuid_generate_v4()"),
                  nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("subreddit_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(20), server_default="member", nullable=False),
        sa.Column("inserted_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subreddit_id"], ["subreddits.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id")
    )
    # 1人1回のみ Join 可能
    op.create_index("ix_subreddit_members_unique",
                    "subreddit_members", ["user_id", "subreddit_id"], unique=True)
    op.create_index("ix_subreddit_members_user_id",
                    "subreddit_members", ["user_id"])
    op.create_index("ix_subreddit_members_subreddit_id",
                    "subreddit_members", ["subreddit_id"])

def downgrade() -> None:
    op.drop_index("ix_subreddit_members_subreddit_id", table_name="subreddit_members")
    op.drop_index("ix_subreddit_members_user_id", table_name="subreddit_members")
    op.drop_index("ix_subreddit_members_unique", table_name="subreddit_members")
    op.drop_table("subreddit_members")
