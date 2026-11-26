import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from tappy.sales.models import (
    JOB_CONSTRAINT,
    AttemptStatus,
    JobReason,
    JobStatus,
    PaymentAttempt,
    ReconciliationJob,
)
from tappy.sales.transitions import move


def expire_due_attempts(db: Session, now: datetime, sale_id: uuid.UUID | None = None) -> int:
    query = select(PaymentAttempt).where(
        PaymentAttempt.status == AttemptStatus.PENDING,
        PaymentAttempt.expires_at <= now,
    )
    if sale_id is not None:
        query = query.where(PaymentAttempt.sale_id == sale_id)
    due = db.scalars(
        query.with_for_update(skip_locked=True).execution_options(populate_existing=True)
    ).all()
    expired = 0
    for attempt in due:
        if move(attempt, AttemptStatus.EXPIRED, now):
            expired += 1
            enqueue_job(db, attempt.id, JobReason.EXPIRED, now)
    db.flush()
    return expired


def enqueue_job(db: Session, attempt_id: uuid.UUID, reason: JobReason, now: datetime) -> None:
    db.execute(
        insert(ReconciliationJob)
        .values(
            id=uuid.uuid4(),
            attempt_id=attempt_id,
            reason=reason,
            status=JobStatus.PENDING,
            run_at=now,
            created_at=now,
        )
        .on_conflict_do_nothing(constraint=JOB_CONSTRAINT)
    )
