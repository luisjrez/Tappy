from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_payment_attempts"
down_revision: str | None = "0008_idempotency_requests"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def frozen_enum(name: str, *values: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True, length=16)


def upgrade() -> None:
    op.create_table(
        "payment_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("sale_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("method", frozen_enum("attempt_method", "qr", "phone", "link"), nullable=False),
        sa.Column(
            "status",
            frozen_enum(
                "attempt_status", "creating", "pending", "reconciling", "expired", "paid", "failed"
            ),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["identities.id"]),
        sa.ForeignKeyConstraint(["sale_id"], ["sales.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_payment_attempts_sale_id", "payment_attempts", ["sale_id"])
    op.create_index(
        "uq_payment_attempts_active_sale",
        "payment_attempts",
        ["sale_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('creating', 'pending', 'reconciling')"),
    )
    op.drop_constraint("idempotent_operation", "idempotency_requests", type_="check")
    op.create_check_constraint(
        "idempotent_operation",
        "idempotency_requests",
        "operation IN ('create_sale', 'create_attempt')",
    )


def downgrade() -> None:
    op.execute("DELETE FROM idempotency_requests WHERE operation = 'create_attempt'")
    op.drop_constraint("idempotent_operation", "idempotency_requests", type_="check")
    op.create_check_constraint(
        "idempotent_operation", "idempotency_requests", "operation IN ('create_sale')"
    )
    op.drop_table("payment_attempts")
