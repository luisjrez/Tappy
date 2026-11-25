import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from tappy.payments.provider import PaymentEvidence
from tappy.sales.models import (
    CURRENCY,
    AttemptStatus,
    PaymentAttempt,
    Sale,
    SaleStatus,
    Transfer,
)

PAYABLE_ATTEMPT_STATUSES = (
    AttemptStatus.CREATING,
    AttemptStatus.PENDING,
    AttemptStatus.RECONCILING,
    AttemptStatus.EXPIRED,
)


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


def held_sale(db: Session, sale_id: uuid.UUID) -> Sale:
    return db.scalars(
        select(Sale)
        .where(Sale.id == sale_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).one()


def matches(evidence: PaymentEvidence, attempt: PaymentAttempt, sale: Sale) -> bool:
    return (
        evidence.provider_transaction_id is not None
        and attempt.status in PAYABLE_ATTEMPT_STATUSES
        and sale.status is SaleStatus.OPEN
        and evidence.receiver_account == attempt.receiver_account
        and evidence.amount_cents == sale.amount_cents
    )


def apply_evidence(
    db: Session, evidence: PaymentEvidence, event_id: uuid.UUID | None, now: datetime
) -> bool:
    attempt = evidenced_attempt(db, evidence)
    if attempt is None:
        return False
    sale = held_sale(db, attempt.sale_id)
    if not matches(evidence, attempt, sale) or evidence.provider_transaction_id is None:
        return False
    db.add(
        Transfer(
            sale_id=sale.id,
            attempt_id=attempt.id,
            provider=evidence.provider,
            provider_transaction_id=evidence.provider_transaction_id,
            amount_cents=sale.amount_cents,
            currency=CURRENCY,
            receiver_account=attempt.receiver_account,
            occurred_at=evidence.occurred_at,
            received_at=now,
            webhook_event_id=event_id,
        )
    )
    attempt.status = AttemptStatus.PAID
    attempt.updated_at = now
    sale.status = SaleStatus.PAID
    db.flush()
    return True
