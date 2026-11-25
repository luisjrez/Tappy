from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015_evidence_deduplication"
down_revision: str | None = "0014_transactions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UNSPECIFIED = "unspecified"


def add_environment(table: str) -> None:
    op.add_column(
        table,
        sa.Column("environment", sa.String(length=32), nullable=False, server_default=UNSPECIFIED),
    )
    op.alter_column(table, "environment", server_default=None)


def replace_unique(table: str, name: str, columns: list[str]) -> None:
    op.drop_constraint(name, table, type_="unique")
    op.create_unique_constraint(name, table, columns)


def event_statuses(*statuses: str) -> None:
    op.drop_constraint("webhook_event_status", "webhook_events", type_="check")
    listed = ", ".join(f"'{status}'" for status in statuses)
    op.create_check_constraint("webhook_event_status", "webhook_events", f"status IN ({listed})")


def upgrade() -> None:
    add_environment("webhook_events")
    add_environment("transactions")
    replace_unique(
        "webhook_events",
        "uq_webhook_events_provider_event",
        ["provider", "environment", "provider_event_id"],
    )
    replace_unique(
        "transactions",
        "uq_transactions_provider_transaction",
        ["provider", "environment", "provider_transaction_id"],
    )
    event_statuses("received", "applied", "unmatched", "duplicate")
    op.create_table(
        "webhook_event_conflicts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("payload", sa.LargeBinary(), nullable=False),
        sa.Column("payload_digest", sa.String(length=64), nullable=False),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["webhook_events.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "event_id", "payload_digest", name="uq_webhook_event_conflicts_variant"
        ),
    )


def downgrade() -> None:
    kept = op.get_bind().scalar(sa.text("SELECT count(*) FROM webhook_event_conflicts"))
    if kept:
        raise RuntimeError("Cannot downgrade while conflicting webhook variants exist")
    op.drop_table("webhook_event_conflicts")
    op.execute("UPDATE webhook_events SET status = 'unmatched' WHERE status = 'duplicate'")
    event_statuses("received", "applied", "unmatched")
    replace_unique(
        "transactions",
        "uq_transactions_provider_transaction",
        ["provider", "provider_transaction_id"],
    )
    replace_unique(
        "webhook_events", "uq_webhook_events_provider_event", ["provider", "provider_event_id"]
    )
    op.drop_column("transactions", "environment")
    op.drop_column("webhook_events", "environment")
