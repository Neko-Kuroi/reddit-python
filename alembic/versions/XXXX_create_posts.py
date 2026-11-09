# alembic/versions/XXXX_create_posts.py
import sqlalchemy as sa
from alembic import op

# Alembic がマイグレーションの順序を特定するための宣言
revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "posts",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuid_generate_v4()"),
                  nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("type", sa.String(10), nullable=False),       # "text" | "link"
        sa.Column("body", sa.Text(), nullable=True),            # type=text のみ
        sa.Column("url", sa.String(2048), nullable=True),       # type=link のみ
        sa.Column("score", sa.Integer(), server_default="0", nullable=False),
        sa.Column("hot_score", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("author_id", sa.UUID(), nullable=False),
        sa.Column("subreddit_id", sa.UUID(), nullable=False),
        sa.Column("inserted_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["subreddit_id"], ["subreddits.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id")
    )
    op.create_index("ix_posts_author_id", "posts", ["author_id"])
    op.create_index("ix_posts_subreddit_id", "posts", ["subreddit_id"])
    # Hot Feed 用の複合インデックス
    op.create_index("ix_posts_subreddit_hot",
                    "posts", ["subreddit_id", "hot_score"])
    # New Feed 用の複合インデックス
    op.create_index("ix_posts_subreddit_new",
                    "posts", ["subreddit_id", "inserted_at"])
    # ホーム Feed 用
    op.create_index("ix_posts_hot_score", "posts", ["hot_score"])

def downgrade() -> None:
    op.drop_index("ix_posts_hot_score", table_name="posts")
    op.drop_index("ix_posts_subreddit_new", table_name="posts")
    op.drop_index("ix_posts_subreddit_hot", table_name="posts")
    op.drop_index("ix_posts_subreddit_id", table_name="posts")
    op.drop_index("ix_posts_author_id", table_name="posts")
    op.drop_table("posts")
