from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_identity_session_rotation"
down_revision: str | None = "0003_identity_access_sessions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DELETE FROM access_sessions")
    op.add_column("access_sessions", sa.Column("family_id", sa.Uuid(), nullable=False))
    op.add_column(
        "access_sessions", sa.Column("refresh_digest", sa.String(length=64), nullable=False)
    )
    op.add_column(
        "access_sessions",
        sa.Column("family_expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.add_column(
        "access_sessions", sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index("ix_access_sessions_family_id", "access_sessions", ["family_id"])
    op.create_unique_constraint(
        "access_sessions_refresh_digest_key", "access_sessions", ["refresh_digest"]
    )


def downgrade() -> None:
    op.drop_constraint("access_sessions_refresh_digest_key", "access_sessions", type_="unique")
    op.drop_index("ix_access_sessions_family_id", table_name="access_sessions")
    op.drop_column("access_sessions", "rotated_at")
    op.drop_column("access_sessions", "family_expires_at")
    op.drop_column("access_sessions", "refresh_digest")
    op.drop_column("access_sessions", "family_id")
