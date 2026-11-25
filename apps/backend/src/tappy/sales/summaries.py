import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tappy.identity.provisioning import IdentitySummary
from tappy.merchants.service import accessible_merchant
from tappy.sales.models import (
    CURRENCY,
    PaymentAttempt,
    PaymentException,
    Sale,
    SaleStatus,
    Transfer,
)
from tappy.sales.periods import BusinessDay, day_bounds
from tappy.sales.received import covering, paid_between


@dataclass(frozen=True)
class DailySummaryView:
    merchant_id: str
    date: date
    timezone: str
    received_amount_cents: int
    currency: str
    transfer_count: int
    covered_sale_count: int
    review_sale_count: int
    open_exception_count: int


def daily_summary(
    db: Session, actor: IdentitySummary, merchant_id: uuid.UUID, business_day: BusinessDay
) -> DailySummaryView:
    merchant = accessible_merchant(db, actor, merchant_id)
    start, end = day_bounds(business_day.day, business_day.zone)
    rows = db.execute(
        select(Transfer.sale_id, Transfer.amount_cents, Sale.status, covering())
        .join(Sale, Sale.id == Transfer.sale_id)
        .join(PaymentAttempt, PaymentAttempt.id == Transfer.attempt_id)
        .where(Sale.merchant_id == merchant.id, paid_between(start, end))
    ).all()
    sales = {sale_id for sale_id, _, _, _ in rows}
    open_exceptions = db.scalar(
        select(func.count(PaymentException.id)).where(
            PaymentException.sale_id.in_(sales), PaymentException.resolved_at.is_(None)
        )
    )
    return DailySummaryView(
        merchant_id=str(merchant.id),
        date=business_day.day,
        timezone=business_day.zone.key,
        received_amount_cents=sum(amount for _, amount, _, _ in rows),
        currency=CURRENCY,
        transfer_count=len(rows),
        covered_sale_count=len({sale_id for sale_id, _, _, covers in rows if covers}),
        review_sale_count=len(
            {sale_id for sale_id, _, status, _ in rows if status is SaleStatus.REVIEW}
        ),
        open_exception_count=open_exceptions or 0,
    )
