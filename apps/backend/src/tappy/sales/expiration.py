import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from tappy.sales.models import AttemptStatus, PaymentAttempt
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
    db.flush()
    return expired
