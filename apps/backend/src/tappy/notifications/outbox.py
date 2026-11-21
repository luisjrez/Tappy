import smtplib
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from tappy.notifications.models import DeliveryStatus, OutboundEmail
from tappy.notifications.sealing import Sealer
from tappy.notifications.transport import Envelope, MailTransport
from tappy.platform.database import Database

BASE_RETRY_DELAY = timedelta(minutes=1)
BATCH_SIZE = 20


@dataclass(frozen=True)
class DeliveryReport:
    sent: int
    retried: int
    failed: int


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


def claim_due(db: Session, now: datetime) -> list[OutboundEmail]:
    return list(
        db.scalars(
            select(OutboundEmail)
            .where(
                OutboundEmail.status == DeliveryStatus.PENDING,
                OutboundEmail.next_attempt_at <= now,
            )
            .order_by(OutboundEmail.next_attempt_at)
            .limit(BATCH_SIZE)
            .with_for_update(skip_locked=True)
        )
    )


def attempt(
    email: OutboundEmail, transport: MailTransport, sealer: Sealer, now: datetime, max_attempts: int
) -> DeliveryStatus | None:
    if email.sealed_body is None:
        email.status = DeliveryStatus.FAILED
        return DeliveryStatus.FAILED
    email.attempts += 1
    try:
        transport.send(Envelope(email.recipient, email.subject, sealer.open(email.sealed_body)))
    except (smtplib.SMTPException, OSError) as error:
        email.last_error = type(error).__name__
        if email.attempts >= max_attempts:
            email.status = DeliveryStatus.FAILED
            email.sealed_body = None
            return DeliveryStatus.FAILED
        email.next_attempt_at = now + retry_delay(email.attempts)
        return None
    email.status = DeliveryStatus.SENT
    email.sent_at = now
    email.sealed_body = None
    email.last_error = None
    return DeliveryStatus.SENT


def deliver_due(
    database: Database, transport: MailTransport, sealer: Sealer, now: datetime, max_attempts: int
) -> DeliveryReport:
    outcomes: list[DeliveryStatus | None] = []
    with database.transaction() as db:
        for email in claim_due(db, now):
            outcomes.append(attempt(email, transport, sealer, now, max_attempts))
    return DeliveryReport(
        sent=outcomes.count(DeliveryStatus.SENT),
        retried=outcomes.count(None),
        failed=outcomes.count(DeliveryStatus.FAILED),
    )
