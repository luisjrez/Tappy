from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_identity_access_sessions"
down_revision: str | None = "0002_identity_identities"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "access_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("identity_id", sa.Uuid(), nullable=False),
        sa.Column("token_digest", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["identity_id"], ["identities.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_digest"),
    )
    op.create_index(
        "ix_access_sessions_identity_id", "access_sessions", ["identity_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_access_sessions_identity_id", table_name="access_sessions")
    op.drop_table("access_sessions")
