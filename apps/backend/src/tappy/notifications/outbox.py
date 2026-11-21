import smtplib
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from cryptography.fernet import InvalidToken
from sqlalchemy import select
from sqlalchemy.orm import Session

from tappy.notifications.models import DeliveryStatus, OutboundEmail
from tappy.notifications.sealing import Sealer
from tappy.notifications.transport import Envelope, MailTransport
from tappy.platform.database import Database

BASE_RETRY_DELAY = timedelta(minutes=1)
BATCH_SIZE = 20


class DeliveryOutcome(StrEnum):
    SENT = "sent"
    RETRY = "retry"
    FAILED = "failed"


@dataclass(frozen=True)
class DeliveryReport:
    sent: int
    retried: int
    failed: int

    @classmethod
    def of(cls, outcomes: list[DeliveryOutcome]) -> DeliveryReport:
        return cls(
            sent=outcomes.count(DeliveryOutcome.SENT),
            retried=outcomes.count(DeliveryOutcome.RETRY),
            failed=outcomes.count(DeliveryOutcome.FAILED),
        )


@dataclass(frozen=True)
class DeliveryContext:
    database: Database
    transport: MailTransport
    sealer: Sealer
    max_attempts: int


@dataclass(frozen=True)
class ClaimedEmail:
    id: uuid.UUID
    envelope: Envelope | None
    exhausted: bool


def enqueue_email(db: Session, envelope: Envelope, sealer: Sealer, now: datetime) -> OutboundEmail:
    email = OutboundEmail(
        recipient=envelope.recipient,
        subject=envelope.subject,
        sealed_body=sealer.seal(envelope.body),
        status=DeliveryStatus.PENDING,
        attempts=0,
        next_attempt_at=now,
        created_at=now,
    )
    db.add(email)
    db.flush()
    return email


def retry_delay(attempts: int) -> timedelta:
    return BASE_RETRY_DELAY * (1 << (attempts - 1))


def claim_next(context: DeliveryContext, now: datetime) -> ClaimedEmail | None:
    with context.database.transaction() as db:
        email = db.scalar(
            select(OutboundEmail)
            .where(
                OutboundEmail.status == DeliveryStatus.PENDING,
                OutboundEmail.next_attempt_at <= now,
            )
            .order_by(OutboundEmail.next_attempt_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if email is None:
            return None
        if email.attempts >= context.max_attempts:
            finish(email, DeliveryStatus.FAILED, email.last_error or "MaxAttemptsExceeded")
            return ClaimedEmail(email.id, None, exhausted=True)
        email.attempts += 1
        email.next_attempt_at = now + retry_delay(email.attempts)
        try:
            body = context.sealer.open(email.sealed_body or "")
        except InvalidToken:
            finish(email, DeliveryStatus.FAILED, "InvalidToken")
            return ClaimedEmail(email.id, None, exhausted=True)
        envelope = Envelope(email.recipient, email.subject, body)
        return ClaimedEmail(email.id, envelope, email.attempts >= context.max_attempts)


def finish(email: OutboundEmail, status: DeliveryStatus, error: str | None) -> None:
    email.status = status
    email.last_error = error
    if status is not DeliveryStatus.PENDING:
        email.sealed_body = None


def record(
    context: DeliveryContext, claimed: ClaimedEmail, now: datetime, error: str | None
) -> DeliveryOutcome:
    with context.database.transaction() as db:
        email = db.get_one(OutboundEmail, claimed.id)
        if error is None:
            email.sent_at = now
            finish(email, DeliveryStatus.SENT, None)
            return DeliveryOutcome.SENT
        if claimed.exhausted:
            finish(email, DeliveryStatus.FAILED, error)
            return DeliveryOutcome.FAILED
        finish(email, DeliveryStatus.PENDING, error)
        return DeliveryOutcome.RETRY


def deliver_one(context: DeliveryContext, claimed: ClaimedEmail, now: datetime) -> DeliveryOutcome:
    if claimed.envelope is None:
        return DeliveryOutcome.FAILED
    try:
        context.transport.send(claimed.envelope)
    except (smtplib.SMTPException, OSError) as error:
        return record(context, claimed, now, type(error).__name__)
    return record(context, claimed, now, None)


def deliver_due(context: DeliveryContext, now: datetime) -> DeliveryReport:
    outcomes: list[DeliveryOutcome] = []
    for _ in range(BATCH_SIZE):
        claimed = claim_next(context, now)
        if claimed is None:
            break
        outcomes.append(deliver_one(context, claimed, now))
    return DeliveryReport.of(outcomes)
