from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tappy.merchants.models import BENEFICIARY_NAME_MAX_LENGTH, PROVIDER_ACCOUNT_ID_MAX_LENGTH
from tappy.payments.provider import ENVIRONMENT_MAX_LENGTH, ProviderName
from tappy.platform.persistence import Base, enum_column

CONCEPT_MAX_LENGTH = 40
REFERENCE_LENGTH = 10
CURRENCY = "MXN"
REFERENCE_CONSTRAINT = "uq_sales_reference"
ACTIVE_ATTEMPT_INDEX = "uq_payment_attempts_active_sale"
PROVIDER_REQUEST_CONSTRAINT = "uq_payment_attempts_provider_request"
PROVIDER_REQUEST_ID_MAX_LENGTH = 64
FAILURE_CODE_MAX_LENGTH = 32
JOB_CONSTRAINT = "uq_reconciliation_jobs_attempt_reason"
JOB_REASON_MAX_LENGTH = 32
TRANSFER_CONSTRAINT = "uq_transactions_provider_transaction"
EXCEPTION_CONSTRAINT = "uq_payment_exceptions_evidence_reason"
WAITING_REFERENCE_INDEX = "ix_payment_exceptions_waiting_reference"
DUE_JOBS_INDEX = "ix_reconciliation_jobs_due"
DUE_EXPIRATION_INDEX = "ix_payment_attempts_due_expiration"
JOB_PROBLEM_MAX_LENGTH = 32


class SaleStatus(StrEnum):
    OPEN = "open"
    PAID = "paid"
    REVIEW = "review"


class AttemptMethod(StrEnum):
    QR = "qr"
    PHONE = "phone"
    LINK = "link"


class AttemptStatus(StrEnum):
    CREATING = "creating"
    PENDING = "pending"
    RECONCILING = "reconciling"
    EXPIRED = "expired"
    PAID = "paid"
    FAILED = "failed"


class NextAction(StrEnum):
    WAIT_FOR_QR = "wait_for_qr"
    SHOW_QR = "show_qr"
    WAIT_FOR_VERIFICATION = "wait_for_verification"
    VERIFY_BEFORE_RETRY = "verify_before_retry"
    NEW_ATTEMPT = "new_attempt"
    NONE = "none"


NEXT_ACTIONS = {
    AttemptStatus.CREATING: NextAction.WAIT_FOR_QR,
    AttemptStatus.PENDING: NextAction.SHOW_QR,
    AttemptStatus.RECONCILING: NextAction.WAIT_FOR_VERIFICATION,
    AttemptStatus.EXPIRED: NextAction.VERIFY_BEFORE_RETRY,
    AttemptStatus.FAILED: NextAction.NEW_ATTEMPT,
    AttemptStatus.PAID: NextAction.NONE,
}


ACTIVE_ATTEMPT_STATUSES = (AttemptStatus.CREATING, AttemptStatus.PENDING, AttemptStatus.RECONCILING)


class JobReason(StrEnum):
    TIMEOUT = "timeout"
    CONNECTION = "connection"
    SERVER_ERROR = "server_error"
    INVALID_RESPONSE = "invalid_response"
    DUPLICATE_PROVIDER_ID = "duplicate_provider_id"
    INTERRUPTED_CREATION = "interrupted_creation"


class JobStatus(StrEnum):
    PENDING = "pending"
    DONE = "done"
    EXHAUSTED = "exhausted"


class ExceptionReason(StrEnum):
    AMOUNT_MISMATCH = "amount_mismatch"
    RECEIVER_MISMATCH = "receiver_mismatch"
    UNASSOCIATED = "unassociated"
    CONFLICTING_TRANSFER = "conflicting_transfer"
    INCOMPLETE_EVIDENCE = "incomplete_evidence"
    SALE_NOT_OPEN = "sale_not_open"


class Sale(Base):
    __tablename__ = "sales"
    __table_args__ = (
        CheckConstraint("amount_cents > 0", name="ck_sales_amount_cents_positive"),
        CheckConstraint(f"currency = '{CURRENCY}'", name="ck_sales_currency_mxn"),
        UniqueConstraint("reference", name=REFERENCE_CONSTRAINT),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    merchant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("merchants.id"), index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("identities.id"))
    amount_cents: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default=CURRENCY)
    concept: Mapped[str | None] = mapped_column(String(CONCEPT_MAX_LENGTH))
    reference: Mapped[str] = mapped_column(String(REFERENCE_LENGTH))
    status: Mapped[SaleStatus] = mapped_column(
        enum_column(SaleStatus, "sale_status"), default=SaleStatus.OPEN
    )
    receiving_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("receiving_accounts.id"))
    receiver_account: Mapped[str] = mapped_column(String(PROVIDER_ACCOUNT_ID_MAX_LENGTH))
    beneficiary_name: Mapped[str] = mapped_column(String(BENEFICIARY_NAME_MAX_LENGTH))
    account_last4: Mapped[str] = mapped_column(String(4))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    exceptions: Mapped[list[PaymentException]] = relationship(
        order_by=lambda: [PaymentException.created_at, PaymentException.id], lazy="selectin"
    )
    transfers: Mapped[list[Transfer]] = relationship(
        order_by=lambda: [Transfer.received_at, Transfer.id], lazy="selectin"
    )
    attempts: Mapped[list[PaymentAttempt]] = relationship(
        back_populates="sale",
        order_by=lambda: [PaymentAttempt.created_at, PaymentAttempt.id],
        lazy="selectin",
    )


class PaymentAttempt(Base):
    __tablename__ = "payment_attempts"
    __table_args__ = (
        Index(
            ACTIVE_ATTEMPT_INDEX,
            "sale_id",
            unique=True,
            postgresql_where=text(
                "status IN (" + ", ".join(f"'{status}'" for status in ACTIVE_ATTEMPT_STATUSES) + ")"
            ),
        ),
        UniqueConstraint("provider", "provider_request_id", name=PROVIDER_REQUEST_CONSTRAINT),
        Index(
            DUE_EXPIRATION_INDEX,
            "expires_at",
            postgresql_where=text(f"status = '{AttemptStatus.PENDING}'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    sale_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sales.id"), index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("identities.id"))
    method: Mapped[AttemptMethod] = mapped_column(enum_column(AttemptMethod, "attempt_method"))
    status: Mapped[AttemptStatus] = mapped_column(enum_column(AttemptStatus, "attempt_status"))
    provider: Mapped[ProviderName] = mapped_column(enum_column(ProviderName, "payment_provider"))
    simulated: Mapped[bool]
    receiver_account: Mapped[str] = mapped_column(String(PROVIDER_ACCOUNT_ID_MAX_LENGTH))
    provider_request_id: Mapped[str | None] = mapped_column(String(PROVIDER_REQUEST_ID_MAX_LENGTH))
    qr_payload: Mapped[str | None] = mapped_column(Text)
    failure_code: Mapped[str | None] = mapped_column(String(FAILURE_CODE_MAX_LENGTH))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sale: Mapped[Sale] = relationship(back_populates="attempts")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer)

    __mapper_args__ = MappingProxyType({"version_id_col": version})


class ReconciliationJob(Base):
    __tablename__ = "reconciliation_jobs"
    __table_args__ = (
        UniqueConstraint("attempt_id", "reason", name=JOB_CONSTRAINT),
        CheckConstraint("tries >= 0", name="ck_reconciliation_jobs_tries"),
        Index(DUE_JOBS_INDEX, "run_at", postgresql_where=text(f"status = '{JobStatus.PENDING}'")),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    attempt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("payment_attempts.id"))
    reason: Mapped[JobReason] = mapped_column(
        enum_column(JobReason, "reconciliation_job_reason", length=JOB_REASON_MAX_LENGTH)
    )
    status: Mapped[JobStatus] = mapped_column(enum_column(JobStatus, "reconciliation_job_status"))
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    tries: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    lease_owner: Mapped[uuid.UUID | None]
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_problem: Mapped[str | None] = mapped_column(String(JOB_PROBLEM_MAX_LENGTH))


class Transfer(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint(
            "provider", "environment", "provider_transaction_id", name=TRANSFER_CONSTRAINT
        ),
        CheckConstraint("amount_cents > 0", name="ck_transactions_amount_cents_positive"),
        CheckConstraint(f"currency = '{CURRENCY}'", name="ck_transactions_currency_mxn"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    sale_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sales.id"), index=True)
    attempt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("payment_attempts.id"))
    provider: Mapped[ProviderName] = mapped_column(enum_column(ProviderName, "transfer_provider"))
    environment: Mapped[str] = mapped_column(String(ENVIRONMENT_MAX_LENGTH))
    provider_transaction_id: Mapped[str] = mapped_column(String(PROVIDER_REQUEST_ID_MAX_LENGTH))
    amount_cents: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))
    receiver_account: Mapped[str] = mapped_column(String(PROVIDER_ACCOUNT_ID_MAX_LENGTH))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    webhook_event_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("webhook_events.id"))


class PaymentException(Base):
    __tablename__ = "payment_exceptions"
    __table_args__ = (
        UniqueConstraint(
            "webhook_event_id",
            "reason",
            "provider_transaction_id",
            name=EXCEPTION_CONSTRAINT,
            postgresql_nulls_not_distinct=True,
        ),
        Index(
            WAITING_REFERENCE_INDEX,
            "provider_request_id",
            postgresql_where=text(
                f"resolved_at IS NULL AND reason = '{ExceptionReason.UNASSOCIATED}'"
            ),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    sale_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sales.id"), index=True)
    transfer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("transactions.id"))
    webhook_event_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("webhook_events.id"))
    reason: Mapped[ExceptionReason] = mapped_column(
        enum_column(ExceptionReason, "payment_exception_reason", length=32)
    )
    provider_transaction_id: Mapped[str | None] = mapped_column(
        String(PROVIDER_REQUEST_ID_MAX_LENGTH)
    )
    provider_request_id: Mapped[str | None] = mapped_column(String(PROVIDER_REQUEST_ID_MAX_LENGTH))
    expected_amount_cents: Mapped[int | None] = mapped_column(Integer)
    received_amount_cents: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
