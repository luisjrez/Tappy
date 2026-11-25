from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016_payment_exceptions"
down_revision: str | None = "0015_evidence_deduplication"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REASONS = (
    "amount_mismatch",
    "receiver_mismatch",
    "unassociated",
    "conflicting_transfer",
    "incomplete_evidence",
    "sale_not_open",
)


def event_statuses(*statuses: str) -> None:
    op.drop_constraint("webhook_event_status", "webhook_events", type_="check")
    listed = ", ".join(f"'{status}'" for status in statuses)
    op.create_check_constraint("webhook_event_status", "webhook_events", f"status IN ({listed})")


def upgrade() -> None:
    op.create_table(
        "payment_exceptions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("sale_id", sa.Uuid(), nullable=True),
        sa.Column("transfer_id", sa.Uuid(), nullable=True),
        sa.Column("webhook_event_id", sa.Uuid(), nullable=True),
        sa.Column(
            "reason",
            sa.Enum(
                *REASONS,
                name="payment_exception_reason",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("provider_transaction_id", sa.String(length=64), nullable=True),
        sa.Column("expected_amount_cents", sa.Integer(), nullable=True),
        sa.Column("received_amount_cents", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["sale_id"], ["sales.id"]),
        sa.ForeignKeyConstraint(["transfer_id"], ["transactions.id"]),
        sa.ForeignKeyConstraint(["webhook_event_id"], ["webhook_events.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "webhook_event_id",
            "reason",
            "provider_transaction_id",
            name="uq_payment_exceptions_evidence_reason",
            postgresql_nulls_not_distinct=True,
        ),
    )
    op.create_index("ix_payment_exceptions_sale_id", "payment_exceptions", ["sale_id"])
    event_statuses("received", "applied", "unmatched", "duplicate", "review")


def downgrade() -> None:
    kept = op.get_bind().scalar(sa.text("SELECT count(*) FROM payment_exceptions"))
    if kept:
        raise RuntimeError("Cannot downgrade while payment exceptions exist")
    op.execute("UPDATE webhook_events SET status = 'unmatched' WHERE status = 'review'")
    event_statuses("received", "applied", "unmatched", "duplicate")
    op.drop_table("payment_exceptions")
