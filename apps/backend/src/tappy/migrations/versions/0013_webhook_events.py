from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013_webhook_events"
down_revision: str | None = "0012_reconciliation_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def frozen_enum(name: str, *values: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True, length=16)


def upgrade() -> None:
    op.create_table(
        "webhook_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider", frozen_enum("webhook_provider", "simulated", "pey"), nullable=False),
        sa.Column("provider_event_id", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.LargeBinary(), nullable=False),
        sa.Column("payload_digest", sa.String(length=64), nullable=False),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", frozen_enum("webhook_event_status", "received"), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider", "provider_event_id", name="uq_webhook_events_provider_event"
        ),
    )


def downgrade() -> None:
    existing_events = op.get_bind().scalar(sa.text("SELECT count(*) FROM webhook_events"))
    if existing_events:
        raise RuntimeError("Cannot downgrade while webhook events exist")
    op.drop_table("webhook_events")
