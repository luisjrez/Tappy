from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022_reception_dated_transfers"
down_revision: str | None = "0021_double_reception"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

IMMUTABLE = """
CREATE OR REPLACE FUNCTION transactions_are_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'recorded transfers are immutable';
END;
$$
"""

BANK_TIME_ONCE = """
CREATE OR REPLACE FUNCTION transactions_are_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'UPDATE'
        AND OLD.occurred_at IS NULL
        AND NEW.occurred_at IS NOT NULL
        AND to_jsonb(NEW) - 'occurred_at' = to_jsonb(OLD) - 'occurred_at'
    THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'recorded transfers are immutable';
END;
$$
"""


def upgrade() -> None:
    op.alter_column(
        "transactions", "occurred_at", existing_type=sa.DateTime(timezone=True), nullable=True
    )
    op.execute(BANK_TIME_ONCE)


def downgrade() -> None:
    undated = op.get_bind().scalar(
        sa.text("SELECT count(*) FROM transactions WHERE occurred_at IS NULL")
    )
    if undated:
        raise RuntimeError("Cannot downgrade while transfers without a bank time exist")
    op.execute(IMMUTABLE)
    op.alter_column(
        "transactions", "occurred_at", existing_type=sa.DateTime(timezone=True), nullable=False
    )
