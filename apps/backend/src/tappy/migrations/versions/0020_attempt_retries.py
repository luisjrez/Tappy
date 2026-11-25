from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0020_attempt_retries"
down_revision: str | None = "0019_attempt_expiration"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REASONS = (
    "timeout",
    "connection",
    "server_error",
    "invalid_response",
    "duplicate_provider_id",
    "interrupted_creation",
)


def job_reasons(*reasons: str) -> None:
    op.drop_constraint("reconciliation_job_reason", "reconciliation_jobs", type_="check")
    listed = ", ".join(f"'{reason}'" for reason in reasons)
    op.create_check_constraint(
        "reconciliation_job_reason", "reconciliation_jobs", f"reason IN ({listed})"
    )


def upgrade() -> None:
    op.add_column(
        "payment_attempts", sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("payment_attempts", sa.Column("previous_attempt_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_payment_attempts_previous_attempt_id_payment_attempts",
        "payment_attempts",
        "payment_attempts",
        ["previous_attempt_id"],
        ["id"],
    )
    op.create_unique_constraint(
        "uq_payment_attempts_previous_attempt", "payment_attempts", ["previous_attempt_id"]
    )
    job_reasons(*REASONS, "expired")


def downgrade() -> None:
    expired_jobs = op.get_bind().scalar(
        sa.text("SELECT count(*) FROM reconciliation_jobs WHERE reason = 'expired'")
    )
    if expired_jobs:
        raise RuntimeError("Cannot downgrade while expired-attempt verification jobs exist")
    job_reasons(*REASONS)
    op.drop_constraint("uq_payment_attempts_previous_attempt", "payment_attempts", type_="unique")
    op.drop_constraint(
        "fk_payment_attempts_previous_attempt_id_payment_attempts",
        "payment_attempts",
        type_="foreignkey",
    )
    op.drop_column("payment_attempts", "previous_attempt_id")
    op.drop_column("payment_attempts", "verified_at")
