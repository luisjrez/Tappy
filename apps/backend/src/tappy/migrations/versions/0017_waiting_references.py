from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017_waiting_references"
down_revision: str | None = "0016_payment_exceptions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEX = "ix_payment_exceptions_waiting_reference"


def upgrade() -> None:
    op.add_column(
        "payment_exceptions",
        sa.Column("provider_request_id", sa.String(length=64), nullable=True),
    )
    op.execute(
        "UPDATE payment_exceptions AS e "
        "SET provider_request_id = convert_from(w.payload, 'UTF8')::jsonb ->> 'codiQrId' "
        "FROM webhook_events AS w "
        "WHERE e.webhook_event_id = w.id AND w.provider = 'pey' AND e.reason = 'unassociated' "
        "AND e.resolved_at IS NULL "
        "AND jsonb_typeof(convert_from(w.payload, 'UTF8')::jsonb -> 'codiQrId') = 'string' "
        "AND length(convert_from(w.payload, 'UTF8')::jsonb ->> 'codiQrId') BETWEEN 1 AND 64"
    )
    op.create_index(
        INDEX,
        "payment_exceptions",
        ["provider_request_id"],
        postgresql_where=sa.text("resolved_at IS NULL AND reason = 'unassociated'"),
    )


def downgrade() -> None:
    op.drop_index(INDEX, table_name="payment_exceptions")
    op.drop_column("payment_exceptions", "provider_request_id")
