from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018_job_leases"
down_revision: str | None = "0017_waiting_references"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEX = "ix_reconciliation_jobs_due"


def job_statuses(*statuses: str) -> None:
    op.drop_constraint("reconciliation_job_status", "reconciliation_jobs", type_="check")
    listed = ", ".join(f"'{status}'" for status in statuses)
    op.create_check_constraint(
        "reconciliation_job_status", "reconciliation_jobs", f"status IN ({listed})"
    )


def upgrade() -> None:
    op.add_column(
        "reconciliation_jobs",
        sa.Column("tries", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column("reconciliation_jobs", sa.Column("lease_owner", sa.Uuid(), nullable=True))
    op.add_column(
        "reconciliation_jobs",
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "reconciliation_jobs", sa.Column("last_problem", sa.String(length=32), nullable=True)
    )
    op.create_check_constraint("ck_reconciliation_jobs_tries", "reconciliation_jobs", "tries >= 0")
    job_statuses("pending", "done", "exhausted")
    op.create_index(
        INDEX,
        "reconciliation_jobs",
        ["run_at"],
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    exhausted = op.get_bind().scalar(
        sa.text("SELECT count(*) FROM reconciliation_jobs WHERE status = 'exhausted'")
    )
    if exhausted:
        raise RuntimeError("Cannot downgrade while exhausted reconciliation jobs exist")
    op.drop_index(INDEX, table_name="reconciliation_jobs")
    job_statuses("pending", "done")
    op.drop_constraint("ck_reconciliation_jobs_tries", "reconciliation_jobs", type_="check")
    op.drop_column("reconciliation_jobs", "last_problem")
    op.drop_column("reconciliation_jobs", "lease_until")
    op.drop_column("reconciliation_jobs", "lease_owner")
    op.drop_column("reconciliation_jobs", "tries")
