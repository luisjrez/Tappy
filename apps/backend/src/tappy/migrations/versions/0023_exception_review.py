from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0023_exception_review"
down_revision: str | None = "0022_reception_dated_transfers"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REASONS = (
    "timeout",
    "connection",
    "server_error",
    "invalid_response",
    "duplicate_provider_id",
    "interrupted_creation",
    "expired",
)


def job_reasons(*reasons: str) -> None:
    op.drop_constraint("reconciliation_job_reason", "reconciliation_jobs", type_="check")
    listed = ", ".join(f"'{reason}'" for reason in reasons)
    op.create_check_constraint(
        "reconciliation_job_reason", "reconciliation_jobs", f"reason IN ({listed})"
    )


def upgrade() -> None:
    op.create_table(
        "exception_notes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("exception_id", sa.Uuid(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=False),
        sa.Column("text", sa.String(length=1000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["exception_id"], ["payment_exceptions.id"]),
        sa.ForeignKeyConstraint(["author_id"], ["identities.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_exception_notes_exception_id", "exception_notes", ["exception_id"])
    job_reasons(*REASONS, "review_requested")


def downgrade() -> None:
    kept = op.get_bind().scalar(
        sa.text(
            "SELECT (SELECT count(*) FROM exception_notes) + "
            "(SELECT count(*) FROM reconciliation_jobs WHERE reason = 'review_requested')"
        )
    )
    if kept:
        raise RuntimeError("Cannot downgrade while review notes or requested reviews exist")
    job_reasons(*REASONS)
    op.drop_index("ix_exception_notes_exception_id", table_name="exception_notes")
    op.drop_table("exception_notes")
