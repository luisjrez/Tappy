import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tappy.payments.provider import PaymentEvidence
from tappy.platform.persistence import is_unique_violation
from tappy.sales.models import (
    CURRENCY,
    EXCEPTION_CONSTRAINT,
    TRANSFER_CONSTRAINT,
    AttemptStatus,
    ExceptionReason,
    PaymentAttempt,
    PaymentException,
    Sale,
    SaleStatus,
    Transfer,
)
from tappy.sales.service import held_sale


class EvidenceOutcome(StrEnum):
    APPLIED = "applied"
    DUPLICATE = "duplicate"
    REVIEW = "review"
    UNMATCHED = "unmatched"


PAYABLE_ATTEMPT_STATUSES = (
    AttemptStatus.CREATING,
    AttemptStatus.PENDING,
    AttemptStatus.RECONCILING,
    AttemptStatus.EXPIRED,
)


@dataclass(frozen=True)
class Incident:
    reason: ExceptionReason
    sale_id: uuid.UUID | None = None
    transfer_id: uuid.UUID | None = None
    expected_amount_cents: int | None = None


@dataclass(frozen=True)
class Application:
    evidence: PaymentEvidence
    event_id: uuid.UUID | None
    now: datetime


def evidenced_attempt(db: Session, evidence: PaymentEvidence) -> PaymentAttempt | None:
    if evidence.provider_request_id is None:
        return None
    attempt = db.scalar(
        select(PaymentAttempt)
        .where(
            PaymentAttempt.provider == evidence.provider,
            PaymentAttempt.provider_request_id == evidence.provider_request_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if attempt is None or evidence.attempt_id not in (None, attempt.id):
        return None
    return attempt


def recorded_transfer(db: Session, evidence: PaymentEvidence) -> Transfer | None:
    if evidence.provider_transaction_id is None:
        return None
    return db.scalar(
        select(Transfer).where(
            Transfer.provider == evidence.provider,
            Transfer.environment == evidence.environment,
            Transfer.provider_transaction_id == evidence.provider_transaction_id,
        )
    )


def same_transfer(existing: Transfer, attempt: PaymentAttempt, evidence: PaymentEvidence) -> bool:
    return (
        existing.attempt_id == attempt.id
        and existing.amount_cents == evidence.amount_cents
        and existing.receiver_account == evidence.receiver_account
    )


def flag(db: Session, application: Application, incident: Incident) -> EvidenceOutcome:
    values = {
        "id": uuid.uuid4(),
        "sale_id": incident.sale_id,
        "transfer_id": incident.transfer_id,
        "webhook_event_id": application.event_id,
        "reason": incident.reason,
        "expected_amount_cents": incident.expected_amount_cents,
        "received_amount_cents": application.evidence.amount_cents,
        "created_at": application.now,
    }
    db.execute(
        insert(PaymentException)
        .values(values)
        .on_conflict_do_nothing(constraint=EXCEPTION_CONSTRAINT)
    )
    return EvidenceOutcome.REVIEW


def doubt(evidence: PaymentEvidence, attempt: PaymentAttempt, sale: Sale) -> ExceptionReason | None:
    if evidence.receiver_account != attempt.receiver_account:
        return ExceptionReason.RECEIVER_MISMATCH
    if (
        evidence.provider_transaction_id is None
        or evidence.amount_cents is None
        or evidence.occurred_at is None
    ):
        return ExceptionReason.INCOMPLETE_EVIDENCE
    if attempt.status not in PAYABLE_ATTEMPT_STATUSES or sale.status is not SaleStatus.OPEN:
        return ExceptionReason.SALE_NOT_OPEN
    return None


def record_reception(
    db: Session, application: Application, attempt: PaymentAttempt, sale: Sale
) -> Transfer | None:
    evidence = application.evidence
    if (
        evidence.provider_transaction_id is None
        or evidence.amount_cents is None
        or evidence.occurred_at is None
    ):
        return None
    transfer = Transfer(
        sale_id=sale.id,
        attempt_id=attempt.id,
        provider=evidence.provider,
        environment=evidence.environment,
        provider_transaction_id=evidence.provider_transaction_id,
        amount_cents=evidence.amount_cents,
        currency=CURRENCY,
        receiver_account=attempt.receiver_account,
        occurred_at=evidence.occurred_at,
        received_at=application.now,
        webhook_event_id=application.event_id,
    )
    try:
        with db.begin_nested():
            db.add(transfer)
    except IntegrityError as error:
        if is_unique_violation(error, TRANSFER_CONSTRAINT):
            return None
        raise
    return transfer


def cover_sale(attempt: PaymentAttempt, sale: Sale, now: datetime) -> EvidenceOutcome:
    attempt.status = AttemptStatus.PAID
    attempt.updated_at = now
    sale.status = SaleStatus.PAID
    return EvidenceOutcome.APPLIED


def apply_evidence(
    db: Session, evidence: PaymentEvidence, event_id: uuid.UUID | None, now: datetime
) -> EvidenceOutcome:
    application = Application(evidence, event_id, now)
    attempt = evidenced_attempt(db, evidence)
    if attempt is None:
        return flag(db, application, Incident(ExceptionReason.UNASSOCIATED))
    existing = recorded_transfer(db, evidence)
    if existing is not None:
        if same_transfer(existing, attempt, evidence):
            return EvidenceOutcome.DUPLICATE
        incident = Incident(ExceptionReason.CONFLICTING_TRANSFER, attempt.sale_id, existing.id)
        return flag(db, application, incident)
    return receive_for_attempt(db, application, attempt)


def receive_for_attempt(
    db: Session, application: Application, attempt: PaymentAttempt
) -> EvidenceOutcome:
    sale = held_sale(db, attempt.sale_id)
    reason = doubt(application.evidence, attempt, sale)
    if reason is not None:
        return flag(db, application, Incident(reason, sale.id, None, sale.amount_cents))
    transfer = record_reception(db, application, attempt, sale)
    if transfer is None:
        return flag(db, application, Incident(ExceptionReason.CONFLICTING_TRANSFER, sale.id))
    if transfer.amount_cents != sale.amount_cents:
        sale.status = SaleStatus.REVIEW
        incident = Incident(
            ExceptionReason.AMOUNT_MISMATCH, sale.id, transfer.id, sale.amount_cents
        )
        return flag(db, application, incident)
    outcome = cover_sale(attempt, sale, application.now)
    db.flush()
    return outcome
