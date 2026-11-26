from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_pey_provider"
down_revision: str | None = "0010_attempt_provider_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("payment_provider", "payment_attempts", type_="check")
    op.create_check_constraint(
        "payment_provider", "payment_attempts", "provider IN ('simulated', 'pey')"
    )
    op.add_column(
        "payment_attempts", sa.Column("failure_code", sa.String(length=32), nullable=True)
    )


def downgrade() -> None:
    pey_attempts = op.get_bind().scalar(
        sa.text("SELECT count(*) FROM payment_attempts WHERE provider = 'pey'")
    )
    if pey_attempts:
        raise RuntimeError("Cannot downgrade while pey payment attempts exist")
    op.drop_column("payment_attempts", "failure_code")
    op.drop_constraint("payment_provider", "payment_attempts", type_="check")
    op.create_check_constraint("payment_provider", "payment_attempts", "provider IN ('simulated')")
