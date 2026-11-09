# alembic/versions/XXXX_create_reports.py
import sqlalchemy as sa
from alembic import op

# Alembic がマイグレーションの順序を特定するための宣言
revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "reports",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuid_generate_v4()"),
                  nullable=False),
        sa.Column("reason", sa.String(50), nullable=False),
        sa.Column("reporter_id", sa.UUID(), nullable=False),
        sa.Column("target_type", sa.String(10), nullable=False),  # "post" | "comment"
        sa.Column("target_id", sa.UUID(), nullable=False),
        sa.Column("inserted_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["reporter_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id")
    )
    op.create_index("ix_reports_target",
                    "reports", ["target_type", "target_id"])
    op.create_index("ix_reports_reporter_id",
                    "reports", ["reporter_id"])

def downgrade() -> None:
    op.drop_index("ix_reports_reporter_id", table_name="reports")
    op.drop_index("ix_reports_target", table_name="reports")
    op.drop_table("reports")
