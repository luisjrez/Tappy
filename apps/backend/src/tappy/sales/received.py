from datetime import datetime

from sqlalchemy import ColumnElement, Exists, ScalarSelect, and_, func, select
from sqlalchemy.orm import aliased

from tappy.sales.models import AttemptStatus, PaymentAttempt, Sale, Transfer


def received_for_sale() -> ScalarSelect[int]:
    return (
        select(func.coalesce(func.sum(Transfer.amount_cents), 0))
        .where(Transfer.sale_id == Sale.id)
        .scalar_subquery()
    )


def covering(
    transfer: type[Transfer] = Transfer, attempt: type[PaymentAttempt] = PaymentAttempt
) -> ColumnElement[bool]:
    return and_(
        transfer.amount_cents == Sale.amount_cents,
        attempt.status == AttemptStatus.PAID,
    )


def sale_is_covered() -> Exists:
    return (
        select(Transfer.id)
        .join(PaymentAttempt, PaymentAttempt.id == Transfer.attempt_id)
        .where(Transfer.sale_id == Sale.id, covering())
        .exists()
    )


def covers_its_sale() -> ColumnElement[bool]:
    earlier = aliased(Transfer)
    attempt = aliased(PaymentAttempt)
    first = (
        select(earlier.id)
        .join(attempt, attempt.id == earlier.attempt_id)
        .where(earlier.sale_id == Transfer.sale_id, covering(earlier, attempt))
        .order_by(dated_at(earlier), earlier.received_at, earlier.id)
        .limit(1)
        .scalar_subquery()
    )
    return Transfer.id == first


def transfer_paid_between(start: datetime, end: datetime) -> ColumnElement[bool]:
    return and_(dated_at() >= start, dated_at() < end)


def dated_at(transfer: type[Transfer] = Transfer) -> ColumnElement[datetime]:
    return func.coalesce(transfer.occurred_at, transfer.received_at)
