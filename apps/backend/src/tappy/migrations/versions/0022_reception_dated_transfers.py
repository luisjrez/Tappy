from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022_reception_dated_transfers"
down_revision: str | None = "0021_double_reception"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "transactions", "occurred_at", existing_type=sa.DateTime(timezone=True), nullable=True
    )


def downgrade() -> None:
    undated = op.get_bind().scalar(
        sa.text("SELECT count(*) FROM transactions WHERE occurred_at IS NULL")
    )
    if undated:
        raise RuntimeError("Cannot downgrade while transfers without a bank time exist")
    op.alter_column(
        "transactions", "occurred_at", existing_type=sa.DateTime(timezone=True), nullable=False
    )
