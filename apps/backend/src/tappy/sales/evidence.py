import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.sql import ColumnElement

from tappy.payments.provider import PaymentEvidence, ProviderName
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
from tappy.sales.transitions import PAYABLE_ATTEMPT_STATUSES, move


class EvidenceOutcome(StrEnum):
    APPLIED = "applied"
    DUPLICATE = "duplicate"
    REVIEW = "review"
    UNMATCHED = "unmatched"


@dataclass(frozen=True)
class Incident:
    reason: ExceptionReason
    sale_id: uuid.UUID | None = None
    transfer_id: uuid.UUID | None = None
    expected_amount_cents: int | None = None


@dataclass(frozen=True)
class VerifiedReception:
    transaction_id: str
    amount_cents: int
    occurred_at: datetime


@dataclass(frozen=True)
class Application:
    evidence: PaymentEvidence
    event_id: uuid.UUID | None
    now: datetime


def hold_reference(db: Session, provider: ProviderName, provider_request_id: str) -> None:
    key = func.hashtextextended(f"{provider}:{provider_request_id}", 0)
    db.execute(select(func.pg_advisory_xact_lock(key)))


def locked_attempt(db: Session, *criteria: ColumnElement[bool]) -> PaymentAttempt | None:
    return db.scalar(
        select(PaymentAttempt)
        .where(*criteria)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def awaiting_attempt(db: Session, evidence: PaymentEvidence) -> PaymentAttempt | None:
    if evidence.attempt_id is None:
        return None
    attempt = locked_attempt(
        db,
        PaymentAttempt.id == evidence.attempt_id,
        PaymentAttempt.provider == evidence.provider,
    )
    if attempt is None or attempt.provider_request_id not in (None, evidence.provider_request_id):
        return None
    attempt.provider_request_id = evidence.provider_request_id
    return attempt


def evidenced_attempt(db: Session, evidence: PaymentEvidence) -> PaymentAttempt | None:
    if evidence.provider_request_id is None:
        return None
    hold_reference(db, evidence.provider, evidence.provider_request_id)
    attempt = locked_attempt(
        db,
        PaymentAttempt.provider == evidence.provider,
        PaymentAttempt.provider_request_id == evidence.provider_request_id,
    )
    if attempt is None:
        return awaiting_attempt(db, evidence)
    if evidence.attempt_id not in (None, attempt.id):
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


def open_exception(db: Session, application: Application, incident: Incident) -> EvidenceOutcome:
    values = {
        "id": uuid.uuid4(),
        "sale_id": incident.sale_id,
        "transfer_id": incident.transfer_id,
        "webhook_event_id": application.event_id,
        "provider_transaction_id": application.evidence.provider_transaction_id,
        "provider_request_id": application.evidence.provider_request_id,
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


def verified_reception(evidence: PaymentEvidence) -> VerifiedReception | None:
    if (
        evidence.provider_transaction_id is None
        or evidence.amount_cents is None
        or evidence.occurred_at is None
    ):
        return None
    return VerifiedReception(
        evidence.provider_transaction_id, evidence.amount_cents, evidence.occurred_at
    )


def classify_doubt(
    evidence: PaymentEvidence, attempt: PaymentAttempt, sale: Sale
) -> ExceptionReason | None:
    if evidence.receiver_account != attempt.receiver_account:
        return ExceptionReason.RECEIVER_MISMATCH
    if verified_reception(evidence) is None:
        return ExceptionReason.INCOMPLETE_EVIDENCE
    if attempt.status not in PAYABLE_ATTEMPT_STATUSES or sale.status is not SaleStatus.OPEN:
        return ExceptionReason.SALE_NOT_OPEN
    return None


def record_reception(
    db: Session,
    application: Application,
    reception: VerifiedReception,
    attempt: PaymentAttempt,
) -> Transfer | None:
    transfer = Transfer(
        sale_id=attempt.sale_id,
        attempt_id=attempt.id,
        provider=application.evidence.provider,
        environment=application.evidence.environment,
        provider_transaction_id=reception.transaction_id,
        amount_cents=reception.amount_cents,
        currency=CURRENCY,
        receiver_account=attempt.receiver_account,
        occurred_at=reception.occurred_at,
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


def recorded_by_this_event(db: Session, existing: Transfer, event_id: uuid.UUID | None) -> bool:
    if event_id is None or existing.webhook_event_id != event_id:
        return False
    return (
        db.scalar(
            select(PaymentException.id).where(
                PaymentException.webhook_event_id == event_id,
                PaymentException.resolved_at.is_(None),
            )
        )
        is not None
    )


def cover_sale(attempt: PaymentAttempt, sale: Sale, now: datetime) -> EvidenceOutcome:
    move(attempt, AttemptStatus.PAID, now)
    sale.status = SaleStatus.PAID
    return EvidenceOutcome.APPLIED


def apply_evidence(
    db: Session, evidence: PaymentEvidence, event_id: uuid.UUID | None, now: datetime
) -> EvidenceOutcome:
    application = Application(evidence, event_id, now)
    attempt = evidenced_attempt(db, evidence)
    if attempt is None:
        return open_exception(db, application, Incident(ExceptionReason.UNASSOCIATED))
    existing = recorded_transfer(db, evidence)
    if existing is not None:
        if not same_transfer(existing, attempt, evidence):
            incident = Incident(
                ExceptionReason.CONFLICTING_TRANSFER,
                sale_id=attempt.sale_id,
                transfer_id=existing.id,
            )
            return open_exception(db, application, incident)
        if recorded_by_this_event(db, existing, event_id):
            return EvidenceOutcome.REVIEW
        return EvidenceOutcome.DUPLICATE
    return receive_for_attempt(db, application, attempt)


def receive_for_attempt(
    db: Session, application: Application, attempt: PaymentAttempt
) -> EvidenceOutcome:
    sale = held_sale(db, attempt.sale_id)
    reason = classify_doubt(application.evidence, attempt, sale)
    reception = verified_reception(application.evidence)
    if reason is not None or reception is None:
        incident = Incident(
            reason or ExceptionReason.INCOMPLETE_EVIDENCE,
            sale_id=sale.id,
            expected_amount_cents=sale.amount_cents,
        )
        return open_exception(db, application, incident)
    transfer = record_reception(db, application, reception, attempt)
    if transfer is None:
        incident = Incident(ExceptionReason.CONFLICTING_TRANSFER, sale_id=sale.id)
        return open_exception(db, application, incident)
    if transfer.amount_cents != sale.amount_cents:
        sale.status = SaleStatus.REVIEW
        incident = Incident(
            ExceptionReason.AMOUNT_MISMATCH,
            sale_id=sale.id,
            transfer_id=transfer.id,
            expected_amount_cents=sale.amount_cents,
        )
        return open_exception(db, application, incident)
    outcome = cover_sale(attempt, sale, application.now)
    db.flush()
    return outcome
