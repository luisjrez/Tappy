import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import Row, func, select
from sqlalchemy.orm import Session

from tappy.identity.provisioning import IdentitySummary
from tappy.merchants.service import accessible_merchant
from tappy.sales.models import CURRENCY, PaymentException, Sale, SaleStatus, Transfer
from tappy.sales.periods import BusinessPeriod, PeriodKind
from tappy.sales.received import covers_its_sale, transfer_date, transfer_paid_between

type TransferRow = Row[uuid.UUID, int, SaleStatus, bool, bool, datetime]


@dataclass(frozen=True)
class DayTotalsView:
    date: date
    received_amount_cents: int
    transfer_count: int
    covered_sale_count: int


@dataclass(frozen=True)
class PeriodSummaryView:
    merchant_id: str
    period: PeriodKind
    start: date
    end: date
    timezone: str
    received_amount_cents: int
    currency: str
    transfer_count: int
    covered_sale_count: int
    review_sale_count: int
    open_exception_count: int
    reception_dated_transfer_count: int
    days: list[DayTotalsView]


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


def day_totals(day: date, rows: list[TransferRow]) -> DayTotalsView:
    return DayTotalsView(
        date=day,
        received_amount_cents=sum(row.amount_cents for row in rows),
        transfer_count=len(rows),
        covered_sale_count=len({row.sale_id for row in rows if row.covers}),
    )


def period_summary(
    db: Session, actor: IdentitySummary, merchant_id: uuid.UUID, period: BusinessPeriod
) -> PeriodSummaryView:
    merchant = accessible_merchant(db, actor, merchant_id)
    start, end = period.bounds
    transfers = db.execute(
        select(
            Transfer.sale_id.label("sale_id"),
            Transfer.amount_cents.label("amount_cents"),
            Sale.status.label("sale_status"),
            covers_its_sale().label("covers"),
            Transfer.occurred_at.is_(None).label("reception_dated"),
            transfer_date().label("dated_at"),
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
    by_day: dict[date, list[TransferRow]] = defaultdict(list)
    for row in transfers:
        by_day[period.local_date(row.dated_at)].append(row)
    whole = day_totals(period.first, list(transfers))
    return PeriodSummaryView(
        merchant_id=str(merchant.id),
        period=period.kind,
        start=period.first,
        end=period.last,
        timezone=period.zone.key,
        received_amount_cents=whole.received_amount_cents,
        currency=CURRENCY,
        transfer_count=whole.transfer_count,
        covered_sale_count=whole.covered_sale_count,
        review_sale_count=len(
            {row.sale_id for row in transfers if row.sale_status is SaleStatus.REVIEW}
        ),
        open_exception_count=open_exceptions or 0,
        reception_dated_transfer_count=sum(1 for row in transfers if row.reception_dated),
        days=[day_totals(day, by_day[day]) for day in period.days],
    )


def daily_summary(
    db: Session, actor: IdentitySummary, merchant_id: uuid.UUID, period: BusinessPeriod
) -> DailySummaryView:
    summary = period_summary(db, actor, merchant_id, period)
    return DailySummaryView(
        merchant_id=summary.merchant_id,
        date=summary.start,
        timezone=summary.timezone,
        received_amount_cents=summary.received_amount_cents,
        currency=summary.currency,
        transfer_count=summary.transfer_count,
        covered_sale_count=summary.covered_sale_count,
        review_sale_count=summary.review_sale_count,
        open_exception_count=summary.open_exception_count,
    )
