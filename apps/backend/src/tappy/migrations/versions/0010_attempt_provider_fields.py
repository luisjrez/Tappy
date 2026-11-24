from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_attempt_provider_fields"
down_revision: str | None = "0009_payment_attempts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def freeze_terms(columns: str) -> str:
    old = ", ".join(f"OLD.{column}" for column in columns.split(", "))
    new = ", ".join(f"NEW.{column}" for column in columns.split(", "))
    return f"""
CREATE OR REPLACE FUNCTION sales_freeze_terms() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF ({new}) IS DISTINCT FROM ({old}) THEN
        RAISE EXCEPTION 'issued sale terms are immutable';
    END IF;
    RETURN NEW;
END;
$$
"""


TERMS = (
    "merchant_id, created_by, amount_cents, currency, concept, reference, "
    "receiving_account_id, beneficiary_name, account_last4, created_at"
)


def upgrade() -> None:
    op.add_column("sales", sa.Column("receiver_account", sa.String(length=64), nullable=True))
    op.execute(
        "UPDATE sales SET receiver_account = receiving_accounts.provider_account_id "
        "FROM receiving_accounts WHERE receiving_accounts.id = sales.receiving_account_id"
    )
    op.alter_column("sales", "receiver_account", nullable=False)
    op.execute(freeze_terms(f"{TERMS}, receiver_account"))
    provider = sa.Enum(
        "simulated", name="payment_provider", native_enum=False, create_constraint=True, length=16
    )
    op.add_column(
        "payment_attempts",
        sa.Column("provider", provider, nullable=False, server_default="simulated"),
    )
    op.add_column(
        "payment_attempts",
        sa.Column("simulated", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "payment_attempts", sa.Column("receiver_account", sa.String(length=64), nullable=True)
    )
    op.execute(
        "UPDATE payment_attempts SET receiver_account = sales.receiver_account "
        "FROM sales WHERE sales.id = payment_attempts.sale_id"
    )
    op.alter_column("payment_attempts", "receiver_account", nullable=False)
    op.alter_column("payment_attempts", "provider", server_default=None)
    op.alter_column("payment_attempts", "simulated", server_default=None)
    op.add_column(
        "payment_attempts", sa.Column("provider_request_id", sa.String(length=64), nullable=True)
    )
    op.add_column("payment_attempts", sa.Column("qr_payload", sa.Text(), nullable=True))
    op.create_unique_constraint(
        "uq_payment_attempts_provider_request",
        "payment_attempts",
        ["provider", "provider_request_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_payment_attempts_provider_request", "payment_attempts", type_="unique")
    for name in ("qr_payload", "provider_request_id", "receiver_account", "simulated", "provider"):
        op.drop_column("payment_attempts", name)
    op.execute(freeze_terms(TERMS))
    op.drop_column("sales", "receiver_account")
