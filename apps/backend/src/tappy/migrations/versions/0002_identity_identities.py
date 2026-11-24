from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_identity_identities"
down_revision: str | None = "0001_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def frozen_enum(name: str, *values: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True, length=16)


def upgrade() -> None:
    op.create_table(
        "identities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", frozen_enum("identity_role", "admin", "operator"), nullable=False),
        sa.Column("status", frozen_enum("identity_status", "active", "inactive"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_identities_email_lower", "identities", [sa.text("lower(email)")], unique=True
    )


def downgrade() -> None:
    op.drop_index("uq_identities_email_lower", table_name="identities")
    op.drop_table("identities")
