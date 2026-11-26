from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014_transactions"
down_revision: str | None = "0013_webhook_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FREEZE_TRANSFERS = """
CREATE FUNCTION transactions_are_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'recorded transfers are immutable';
END;
$$
"""


def upgrade() -> None:
    op.create_table(
        "transactions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("sale_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column(
            "provider",
            sa.Enum(
                "simulated",
                "pey",
                name="transfer_provider",
                native_enum=False,
                create_constraint=True,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("provider_transaction_id", sa.String(length=64), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("receiver_account", sa.String(length=64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("webhook_event_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint("amount_cents > 0", name="ck_transactions_amount_cents_positive"),
        sa.CheckConstraint("currency = 'MXN'", name="ck_transactions_currency_mxn"),
        sa.ForeignKeyConstraint(["attempt_id"], ["payment_attempts.id"]),
        sa.ForeignKeyConstraint(["sale_id"], ["sales.id"]),
        sa.ForeignKeyConstraint(["webhook_event_id"], ["webhook_events.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider", "provider_transaction_id", name="uq_transactions_provider_transaction"
        ),
    )
    op.create_index("ix_transactions_sale_id", "transactions", ["sale_id"])
    op.execute(FREEZE_TRANSFERS)
    op.execute(
        "CREATE TRIGGER transactions_are_immutable BEFORE UPDATE OR DELETE ON transactions "
        "FOR EACH ROW EXECUTE FUNCTION transactions_are_immutable()"
    )
    op.execute(
        "CREATE TRIGGER transactions_cannot_be_truncated BEFORE TRUNCATE ON transactions "
        "FOR EACH STATEMENT EXECUTE FUNCTION transactions_are_immutable()"
    )
    op.drop_constraint("webhook_event_status", "webhook_events", type_="check")
    op.create_check_constraint(
        "webhook_event_status", "webhook_events", "status IN ('received', 'applied', 'unmatched')"
    )


def downgrade() -> None:
    existing = op.get_bind().scalar(sa.text("SELECT count(*) FROM transactions"))
    if existing:
        raise RuntimeError("Cannot downgrade while recorded transfers exist")
    op.execute("UPDATE webhook_events SET status = 'received'")
    op.drop_constraint("webhook_event_status", "webhook_events", type_="check")
    op.create_check_constraint("webhook_event_status", "webhook_events", "status IN ('received')")
    op.drop_table("transactions")
    op.execute("DROP FUNCTION transactions_are_immutable()")
