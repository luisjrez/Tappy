from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_sales"
down_revision: str | None = "0006_receiving_accounts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FREEZE_TERMS = """
CREATE FUNCTION sales_freeze_terms() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF (NEW.merchant_id, NEW.created_by, NEW.amount_cents, NEW.currency, NEW.concept,
        NEW.reference, NEW.receiving_account_id, NEW.beneficiary_name, NEW.account_last4,
        NEW.created_at)
       IS DISTINCT FROM
       (OLD.merchant_id, OLD.created_by, OLD.amount_cents, OLD.currency, OLD.concept,
        OLD.reference, OLD.receiving_account_id, OLD.beneficiary_name, OLD.account_last4,
        OLD.created_at)
    THEN
        RAISE EXCEPTION 'issued sale terms are immutable';
    END IF;
    RETURN NEW;
END;
$$
"""


def upgrade() -> None:
    op.create_table(
        "sales",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("merchant_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("concept", sa.String(length=40), nullable=True),
        sa.Column("reference", sa.String(length=10), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "open",
                "paid",
                "review",
                name="sale_status",
                native_enum=False,
                create_constraint=True,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("receiving_account_id", sa.Uuid(), nullable=False),
        sa.Column("beneficiary_name", sa.String(length=120), nullable=False),
        sa.Column("account_last4", sa.String(length=4), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount_cents > 0", name="ck_sales_amount_cents_positive"),
        sa.CheckConstraint("currency = 'MXN'", name="ck_sales_currency_mxn"),
        sa.ForeignKeyConstraint(["created_by"], ["identities.id"]),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"]),
        sa.ForeignKeyConstraint(["receiving_account_id"], ["receiving_accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("reference"),
    )
    op.create_index("ix_sales_merchant_id", "sales", ["merchant_id"])
    op.execute(FREEZE_TERMS)
    op.execute(
        "CREATE TRIGGER sales_freeze_terms BEFORE UPDATE ON sales "
        "FOR EACH ROW EXECUTE FUNCTION sales_freeze_terms()"
    )


def downgrade() -> None:
    op.drop_table("sales")
    op.execute("DROP FUNCTION sales_freeze_terms()")
