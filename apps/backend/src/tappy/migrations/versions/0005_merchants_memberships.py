from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_merchants_memberships"
down_revision: str | None = "0004_identity_session_rotation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "merchants",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "memberships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("merchant_id", sa.Uuid(), nullable=False),
        sa.Column("identity_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["identity_id"], ["identities.id"]),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("merchant_id", "identity_id"),
    )
    op.create_index("ix_memberships_merchant_id", "memberships", ["merchant_id"])
    op.create_index("ix_memberships_identity_id", "memberships", ["identity_id"])


def downgrade() -> None:
    op.drop_index("ix_memberships_identity_id", table_name="memberships")
    op.drop_index("ix_memberships_merchant_id", table_name="memberships")
    op.drop_table("memberships")
    op.drop_table("merchants")
