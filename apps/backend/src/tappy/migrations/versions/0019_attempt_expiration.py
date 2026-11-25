from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019_attempt_expiration"
down_revision: str | None = "0018_job_leases"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEX = "ix_payment_attempts_due_expiration"


def upgrade() -> None:
    op.add_column(
        "payment_attempts", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index(
        INDEX,
        "payment_attempts",
        ["expires_at"],
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index(INDEX, table_name="payment_attempts")
    op.drop_column("payment_attempts", "expires_at")
