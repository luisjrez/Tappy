from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_reconciliation_jobs"
down_revision: str | None = "0011_pey_provider"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reconciliation_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.String(length=32), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "done",
                name="reconciliation_job_status",
                native_enum=False,
                create_constraint=True,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tries", sa.Integer(), nullable=False),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["attempt_id"], ["payment_attempts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("attempt_id", "reason", name="uq_reconciliation_jobs_attempt_reason"),
    )
    op.create_index("ix_reconciliation_jobs_attempt_id", "reconciliation_jobs", ["attempt_id"])


def downgrade() -> None:
    pending = op.get_bind().scalar(sa.text("SELECT count(*) FROM reconciliation_jobs"))
    if pending:
        raise RuntimeError("Cannot downgrade while reconciliation jobs exist")
    op.drop_table("reconciliation_jobs")
