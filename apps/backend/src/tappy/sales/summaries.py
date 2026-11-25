import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tappy.identity.provisioning import IdentitySummary
from tappy.merchants.service import accessible_merchant
from tappy.sales.models import CURRENCY, PaymentException, Sale, SaleStatus, Transfer
from tappy.sales.periods import BusinessDay
from tappy.sales.received import covers_its_sale, transfer_paid_between


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
    start, end = business_day.bounds
    transfers = db.execute(
        select(
            Transfer.sale_id.label("sale_id"),
            Transfer.amount_cents.label("amount_cents"),
            Sale.status.label("sale_status"),
            covers_its_sale().label("covers"),
        )
        .join(Sale, Sale.id == Transfer.sale_id)
        .where(Sale.merchant_id == merchant.id, transfer_paid_between(start, end))
    ).all()
    open_exceptions = db.scalar(
        select(func.count(PaymentException.id))
        .join(Sale, Sale.id == PaymentException.sale_id)
        .where(
            Sale.merchant_id == merchant.id,
            PaymentException.resolved_at.is_(None),
            PaymentException.created_at >= start,
            PaymentException.created_at < end,
        )
    )
    return DailySummaryView(
        merchant_id=str(merchant.id),
        date=business_day.day,
        timezone=business_day.zone.key,
        received_amount_cents=sum(row.amount_cents for row in transfers),
        currency=CURRENCY,
        transfer_count=len(transfers),
        covered_sale_count=len({row.sale_id for row in transfers if row.covers}),
        review_sale_count=len(
            {row.sale_id for row in transfers if row.sale_status is SaleStatus.REVIEW}
        ),
        open_exception_count=open_exceptions or 0,
    )
