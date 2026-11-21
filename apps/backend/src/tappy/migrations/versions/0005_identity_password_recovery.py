from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_identity_password_recovery"
down_revision: str | None = "0004_identity_session_rotation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "password_reset_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("identity_id", sa.Uuid(), nullable=False),
        sa.Column("token_digest", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["identity_id"], ["identities.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_digest"),
    )
    op.create_index(
        "ix_password_reset_requests_identity_id", "password_reset_requests", ["identity_id"]
    )
    op.create_table(
        "recovery_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("subject_digest", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_recovery_attempts_subject_digest", "recovery_attempts", ["subject_digest"])
    op.create_index("ix_recovery_attempts_created_at", "recovery_attempts", ["created_at"])
    op.create_table(
        "recovery_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("sealed_email", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_recovery_jobs_created_at", "recovery_jobs", ["created_at"])
    op.create_table(
        "outbound_emails",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("recipient", sa.String(length=254), nullable=False),
        sa.Column("subject", sa.String(length=200), nullable=False),
        sa.Column("sealed_body", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "sent",
                "failed",
                name="delivery_status",
                native_enum=False,
                create_constraint=True,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_error", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_outbound_emails_due", "outbound_emails", ["status", "next_attempt_at"])


def downgrade() -> None:
    op.drop_index("ix_outbound_emails_due", table_name="outbound_emails")
    op.drop_table("outbound_emails")
    op.drop_index("ix_recovery_jobs_created_at", table_name="recovery_jobs")
    op.drop_table("recovery_jobs")
    op.drop_index("ix_recovery_attempts_created_at", table_name="recovery_attempts")
    op.drop_index("ix_recovery_attempts_subject_digest", table_name="recovery_attempts")
    op.drop_table("recovery_attempts")
    op.drop_index("ix_password_reset_requests_identity_id", table_name="password_reset_requests")
    op.drop_table("password_reset_requests")
