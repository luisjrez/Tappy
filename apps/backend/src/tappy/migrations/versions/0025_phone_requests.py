from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0025_phone_requests"
down_revision: str | None = "0024_operation_quotas"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("payment_attempts", sa.Column("payer_phone_suffix", sa.String(length=4)))
    op.add_column("payment_attempts", sa.Column("provider_folio", sa.String(length=32)))


def downgrade() -> None:
    op.drop_column("payment_attempts", "provider_folio")
    op.drop_column("payment_attempts", "payer_phone_suffix")
