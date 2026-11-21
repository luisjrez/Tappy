from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_receiving_accounts"
down_revision: str | None = "0005_merchants_memberships"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "receiving_accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("merchant_id", sa.Uuid(), nullable=False),
        sa.Column("provider_account_id", sa.String(length=64), nullable=False),
        sa.Column("beneficiary_name", sa.String(length=120), nullable=False),
        sa.Column("account_last4", sa.String(length=4), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("merchant_id"),
        sa.UniqueConstraint("provider_account_id"),
    )


def downgrade() -> None:
    op.drop_table("receiving_accounts")
