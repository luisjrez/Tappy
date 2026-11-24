from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_attempt_provider_fields"
down_revision: str | None = "0009_payment_attempts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BACKFILLED = ("provider", "simulated", "receiver_account")


def upgrade() -> None:
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
        "payment_attempts",
        sa.Column("receiver_account", sa.String(length=64), nullable=False, server_default=""),
    )
    for name in BACKFILLED:
        op.alter_column("payment_attempts", name, server_default=None)
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
    for name in ("qr_payload", "provider_request_id", *BACKFILLED):
        op.drop_column("payment_attempts", name)
