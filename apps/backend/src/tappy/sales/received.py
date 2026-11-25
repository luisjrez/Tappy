from datetime import datetime

from sqlalchemy import ColumnElement, Exists, ScalarSelect, and_, func, select

from tappy.sales.models import AttemptStatus, PaymentAttempt, Sale, Transfer


def received_for_sale() -> ScalarSelect[int]:
    return (
        select(func.coalesce(func.sum(Transfer.amount_cents), 0))
        .where(Transfer.sale_id == Sale.id)
        .scalar_subquery()
    )


def covering() -> ColumnElement[bool]:
    return and_(
        Transfer.amount_cents == Sale.amount_cents,
        PaymentAttempt.status == AttemptStatus.PAID,
    )


def sale_is_covered() -> Exists:
    return (
        select(Transfer.id)
        .join(PaymentAttempt, PaymentAttempt.id == Transfer.attempt_id)
        .where(Transfer.sale_id == Sale.id, covering())
        .exists()
    )


def paid_between(start: datetime, end: datetime) -> ColumnElement[bool]:
    return and_(Transfer.occurred_at >= start, Transfer.occurred_at < end)
