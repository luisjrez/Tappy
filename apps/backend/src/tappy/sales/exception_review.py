import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.orm import Session

from tappy.identity.models import Identity
from tappy.identity.provisioning import IdentitySummary
from tappy.payments.events import WebhookEvent
from tappy.sales.errors import ExceptionNotFoundError, InvalidNoteError, NothingToReconcileError
from tappy.sales.expiration import enqueue_job
from tappy.sales.models import (
    NOTE_MAX_LENGTH,
    ExceptionNote,
    ExceptionReason,
    JobReason,
    JobStatus,
    PaymentAttempt,
    PaymentException,
    ReconciliationJob,
    Sale,
    Transfer,
)


class RequestOutcome(StrEnum):
    CREATED = "created"
    ALREADY_PENDING = "already_pending"
    REARMED = "rearmed"


@dataclass(frozen=True)
class NoteView:
    author: str
    text: str
    created_at: datetime


@dataclass(frozen=True)
class ReviewJobView:
    status: JobStatus
    run_at: datetime
    tries: int
    last_problem: str | None


@dataclass(frozen=True)
class RequestedReconciliation:
    outcome: RequestOutcome
    job: ReviewJobView


@dataclass(frozen=True)
class ExceptionDetail:
    id: str
    reason: ExceptionReason
    sale_id: str | None
    sale_reference: str | None
    event_id: str | None
    provider_transaction_id: str | None
    expected_amount_cents: int | None
    received_amount_cents: int | None
    created_at: datetime
    resolved_at: datetime | None
    notes: list[NoteView]
    reconciliation: ReviewJobView | None


def held_exception(db: Session, exception_id: uuid.UUID) -> PaymentException:
    exception = db.scalar(
        select(PaymentException).where(PaymentException.id == exception_id).with_for_update()
    )
    if exception is None:
        raise ExceptionNotFoundError
    return exception


def clean_note(text: str) -> str:
    cleaned = text.strip()
    if not cleaned or len(cleaned) > NOTE_MAX_LENGTH:
        raise InvalidNoteError(NOTE_MAX_LENGTH)
    return cleaned


def write_note(
    db: Session, author: IdentitySummary, exception_id: uuid.UUID, text: str, now: datetime
) -> NoteView:
    note = ExceptionNote(
        exception_id=exception_id,
        author_id=uuid.UUID(author.reference),
        text=text,
        created_at=now,
    )
    db.add(note)
    db.flush()
    return NoteView(author.email, note.text, note.created_at)


def add_note(
    db: Session, author: IdentitySummary, exception_id: uuid.UUID, text: str, now: datetime
) -> NoteView:
    cleaned = clean_note(text)
    exception = held_exception(db, exception_id)
    return write_note(db, author, exception.id, cleaned, now)


def attempt_to_review(db: Session, exception: PaymentException) -> uuid.UUID:
    if exception.transfer_id is not None:
        return db.get_one(Transfer, exception.transfer_id).attempt_id
    attempt_id = db.scalar(
        select(PaymentAttempt.id)
        .where(
            PaymentAttempt.sale_id == exception.sale_id,
            PaymentAttempt.provider_request_id.is_not(None),
        )
        .order_by(PaymentAttempt.created_at.desc(), PaymentAttempt.id.desc())
        .limit(1)
    )
    if attempt_id is None:
        raise NothingToReconcileError
    return attempt_id


def review_job(db: Session, attempt_id: uuid.UUID) -> ReconciliationJob | None:
    return db.scalar(
        select(ReconciliationJob)
        .where(
            ReconciliationJob.attempt_id == attempt_id,
            ReconciliationJob.reason == JobReason.REVIEW_REQUESTED,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def rearm(job: ReconciliationJob, now: datetime) -> RequestOutcome:
    if job.status is JobStatus.PENDING:
        return RequestOutcome.ALREADY_PENDING
    job.status = JobStatus.PENDING
    job.run_at = now
    job.tries = 0
    job.lease_owner = None
    job.lease_until = None
    job.last_problem = None
    return RequestOutcome.REARMED


def request_reconciliation(
    db: Session, author: IdentitySummary, exception_id: uuid.UUID, now: datetime
) -> RequestedReconciliation:
    exception = held_exception(db, exception_id)
    attempt_id = attempt_to_review(db, exception)
    existing = review_job(db, attempt_id)
    if existing is None:
        enqueue_job(db, attempt_id, JobReason.REVIEW_REQUESTED, now)
        outcome = RequestOutcome.CREATED
    else:
        outcome = rearm(existing, now)
    job = review_job(db, attempt_id)
    if job is None:
        raise RuntimeError("The requested reconciliation job was not stored")
    write_note(db, author, exception.id, f"Reconciliation requested ({outcome})", now)
    return RequestedReconciliation(outcome, describe_job(job))


def describe_job(job: ReconciliationJob) -> ReviewJobView:
    return ReviewJobView(job.status, job.run_at, job.tries, job.last_problem)


def read_exception(db: Session, exception_id: uuid.UUID) -> ExceptionDetail:
    row = db.execute(
        select(PaymentException, Sale.reference, WebhookEvent.provider_event_id)
        .outerjoin(Sale, Sale.id == PaymentException.sale_id)
        .outerjoin(WebhookEvent, WebhookEvent.id == PaymentException.webhook_event_id)
        .where(PaymentException.id == exception_id)
    ).one_or_none()
    if row is None:
        raise ExceptionNotFoundError
    exception, reference, event_id = row
    notes = db.execute(
        select(ExceptionNote, Identity.email)
        .join(Identity, Identity.id == ExceptionNote.author_id)
        .where(ExceptionNote.exception_id == exception.id)
        .order_by(ExceptionNote.created_at, ExceptionNote.id)
    ).all()
    return ExceptionDetail(
        id=str(exception.id),
        reason=exception.reason,
        sale_id=None if exception.sale_id is None else str(exception.sale_id),
        sale_reference=reference,
        event_id=event_id,
        provider_transaction_id=exception.provider_transaction_id,
        expected_amount_cents=exception.expected_amount_cents,
        received_amount_cents=exception.received_amount_cents,
        created_at=exception.created_at,
        resolved_at=exception.resolved_at,
        notes=[NoteView(email, note.text, note.created_at) for note, email in notes],
        reconciliation=requested_review(db, exception),
    )


def requested_review(db: Session, exception: PaymentException) -> ReviewJobView | None:
    try:
        attempt_id = attempt_to_review(db, exception)
    except NothingToReconcileError:
        return None
    job = db.scalar(
        select(ReconciliationJob).where(
            ReconciliationJob.attempt_id == attempt_id,
            ReconciliationJob.reason == JobReason.REVIEW_REQUESTED,
        )
    )
    return None if job is None else describe_job(job)
