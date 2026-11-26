from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.orm import InstrumentedAttribute, Session

from tappy.payments.events import EventStatus, WebhookEvent
from tappy.sales.models import (
    AttemptStatus,
    JobStatus,
    PaymentAttempt,
    PaymentException,
    ReconciliationJob,
)


@dataclass(frozen=True)
class Lag:
    count: int
    oldest: datetime | None


@dataclass(frozen=True)
class Backlog:
    received_events: Lag
    due_jobs: Lag
    leased_jobs: int
    expired_leases: int
    exhausted_jobs: int
    stalled_creations: Lag
    open_exceptions: int


def lag(
    db: Session, column: InstrumentedAttribute[datetime], *conditions: ColumnElement[bool]
) -> Lag:
    count, oldest = db.execute(select(func.count(), func.min(column)).where(*conditions)).one()
    return Lag(count, oldest)


def count(db: Session, *conditions: ColumnElement[bool]) -> int:
    return db.scalar(select(func.count()).where(*conditions)) or 0


def backlog(db: Session, now: datetime, creation_cutoff: datetime) -> Backlog:
    pending = ReconciliationJob.status == JobStatus.PENDING
    leased = ReconciliationJob.lease_until.is_not(None)
    return Backlog(
        received_events=lag(
            db, WebhookEvent.received_at, WebhookEvent.status == EventStatus.RECEIVED
        ),
        due_jobs=lag(
            db,
            ReconciliationJob.run_at,
            pending,
            ReconciliationJob.run_at <= now,
            or_(ReconciliationJob.lease_until.is_(None), ReconciliationJob.lease_until <= now),
        ),
        leased_jobs=count(db, pending, leased),
        expired_leases=count(db, pending, leased, ReconciliationJob.lease_until <= now),
        exhausted_jobs=count(db, ReconciliationJob.status == JobStatus.EXHAUSTED),
        stalled_creations=lag(
            db,
            PaymentAttempt.updated_at,
            PaymentAttempt.status == AttemptStatus.CREATING,
            PaymentAttempt.updated_at < creation_cutoff,
        ),
        open_exceptions=count(db, PaymentException.resolved_at.is_(None)),
    )
