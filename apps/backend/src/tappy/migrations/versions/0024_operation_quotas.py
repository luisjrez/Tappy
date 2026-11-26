from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0024_operation_quotas"
down_revision: str | None = "0023_exception_review"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "operation_quotas",
        sa.Column("scope", sa.String(length=64), nullable=False),
        sa.Column(
            "operation",
            sa.Enum(
                "sale_creation",
                "attempt_creation",
                "sale_read",
                name="quota_operation",
                native_enum=False,
                create_constraint=True,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used", sa.Integer(), nullable=False),
        sa.CheckConstraint("used > 0", name="operation_quota_used"),
        sa.PrimaryKeyConstraint("scope", "operation", "window_start"),
    )


def downgrade() -> None:
    op.drop_table("operation_quotas")
