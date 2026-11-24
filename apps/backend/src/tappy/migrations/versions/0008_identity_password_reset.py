from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_identity_password_reset"
down_revision: str | None = "0007_identity_password_recovery"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "password_reset_requests",
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "password_reset_requests",
        sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("password_reset_requests", "invalidated_at")
    op.drop_column("password_reset_requests", "consumed_at")
