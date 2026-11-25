from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021_double_reception"
down_revision: str | None = "0020_attempt_retries"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REASONS = (
    "amount_mismatch",
    "receiver_mismatch",
    "unassociated",
    "conflicting_transfer",
    "incomplete_evidence",
    "sale_not_open",
)


def exception_reasons(*reasons: str) -> None:
    op.drop_constraint("payment_exception_reason", "payment_exceptions", type_="check")
    listed = ", ".join(f"'{reason}'" for reason in reasons)
    op.create_check_constraint(
        "payment_exception_reason", "payment_exceptions", f"reason IN ({listed})"
    )


def upgrade() -> None:
    op.add_column(
        "payment_attempts", sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True)
    )
    exception_reasons(*REASONS, "double_reception")


def downgrade() -> None:
    doubles = op.get_bind().scalar(
        sa.text("SELECT count(*) FROM payment_exceptions WHERE reason = 'double_reception'")
    )
    if doubles:
        raise RuntimeError("Cannot downgrade while double reception exceptions exist")
    exception_reasons(*REASONS)
    op.drop_column("payment_attempts", "withdrawn_at")
