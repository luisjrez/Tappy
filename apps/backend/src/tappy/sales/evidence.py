import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tappy.payments.provider import PaymentEvidence
from tappy.platform.persistence import is_unique_violation
from tappy.sales.models import (
    CURRENCY,
    TRANSFER_CONSTRAINT,
    AttemptStatus,
    PaymentAttempt,
    Sale,
    SaleStatus,
    Transfer,
)
from tappy.sales.service import held_sale

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


def matching_transaction(
    evidence: PaymentEvidence, attempt: PaymentAttempt, sale: Sale
) -> str | None:
    if (
        attempt.status in PAYABLE_ATTEMPT_STATUSES
        and sale.status is SaleStatus.OPEN
        and evidence.receiver_account == attempt.receiver_account
        and evidence.amount_cents == sale.amount_cents
        and evidence.occurred_at is not None
    ):
        return evidence.provider_transaction_id
    return None


def record_transfer(db: Session, transfer: Transfer) -> bool:
    try:
        with db.begin_nested():
            db.add(transfer)
    except IntegrityError as error:
        if is_unique_violation(error, TRANSFER_CONSTRAINT):
            return False
        raise
    return True


def apply_evidence(
    db: Session, evidence: PaymentEvidence, event_id: uuid.UUID | None, now: datetime
) -> bool:
    attempt = evidenced_attempt(db, evidence)
    if attempt is None:
        return False
    sale = held_sale(db, attempt.sale_id)
    transaction_id = matching_transaction(evidence, attempt, sale)
    if transaction_id is None or evidence.occurred_at is None:
        return False
    transfer = Transfer(
        sale_id=sale.id,
        attempt_id=attempt.id,
        provider=evidence.provider,
        provider_transaction_id=transaction_id,
        amount_cents=sale.amount_cents,
        currency=CURRENCY,
        receiver_account=attempt.receiver_account,
        occurred_at=evidence.occurred_at,
        received_at=now,
        webhook_event_id=event_id,
    )
    if not record_transfer(db, transfer):
        return False
    attempt.status = AttemptStatus.PAID
    attempt.updated_at = now
    sale.status = SaleStatus.PAID
    db.flush()
    return True
