import base64
import binascii
import json
import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Select, func, select, tuple_
from sqlalchemy.orm import Session

from tappy.identity.provisioning import IdentitySummary
from tappy.merchants.receivers import masked_account
from tappy.merchants.service import accessible_merchant
from tappy.sales.models import AttemptStatus, PaymentAttempt, Sale, SaleStatus, Transfer
from tappy.sales.service import scoped_sales


class InvalidCursorError(Exception):
    def __init__(self) -> None:
        super().__init__("Invalid cursor")


@dataclass(frozen=True)
class SaleCursor:
    created_at: datetime
    sale_id: uuid.UUID

    def encode(self) -> str:
        raw = json.dumps([self.created_at.isoformat(), str(self.sale_id)]).encode()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    @classmethod
    def decode(cls, token: str) -> SaleCursor:
        try:
            raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
            created_at, sale_id = json.loads(raw)
            cursor = cls(datetime.fromisoformat(created_at), uuid.UUID(sale_id))
        except binascii.Error, ValueError, TypeError:
            raise InvalidCursorError from None
        if cursor.created_at.tzinfo is None:
            raise InvalidCursorError
        return cursor


@dataclass(frozen=True)
class HistoryQuery:
    merchant_id: uuid.UUID | None
    status: SaleStatus | None
    created_from: datetime | None
    created_to: datetime | None
    limit: int
    cursor: str | None


@dataclass(frozen=True)
class SaleRow:
    id: str
    merchant_id: str
    reference: str
    amount_cents: int
    currency: str
    concept: str | None
    status: SaleStatus
    covered: bool
    confirmed_amount_cents: int
    attempt_count: int
    beneficiary_name: str
    masked_account: str
    created_at: datetime


@dataclass(frozen=True)
class HistoryPage:
    items: list[SaleRow]
    next_cursor: str | None


def filtered_sales(db: Session, actor: IdentitySummary, query: HistoryQuery) -> Select[Sale]:
    sales = scoped_sales(actor)
    if query.merchant_id is not None:
        sales = sales.where(
            Sale.merchant_id == accessible_merchant(db, actor, query.merchant_id).id
        )
    if query.status is not None:
        sales = sales.where(Sale.status == query.status)
    if query.created_from is not None:
        sales = sales.where(Sale.created_at >= query.created_from)
    if query.created_to is not None:
        sales = sales.where(Sale.created_at < query.created_to)
    if query.cursor is not None:
        cursor = SaleCursor.decode(query.cursor)
        sales = sales.where(tuple_(Sale.created_at, Sale.id) < (cursor.created_at, cursor.sale_id))
    return sales


def sale_history(db: Session, actor: IdentitySummary, query: HistoryQuery) -> HistoryPage:
    confirmed = (
        select(func.coalesce(func.sum(Transfer.amount_cents), 0))
        .where(Transfer.sale_id == Sale.id)
        .scalar_subquery()
    )
    covered = (
        select(Transfer.id)
        .join(PaymentAttempt, PaymentAttempt.id == Transfer.attempt_id)
        .where(
            Transfer.sale_id == Sale.id,
            Transfer.amount_cents == Sale.amount_cents,
            PaymentAttempt.status == AttemptStatus.PAID,
        )
        .exists()
    )
    attempts = (
        select(func.count(PaymentAttempt.id)).where(PaymentAttempt.sale_id == Sale.id)
    ).scalar_subquery()
    rows = db.execute(
        filtered_sales(db, actor, query)
        .add_columns(confirmed, covered, attempts)
        .order_by(Sale.created_at.desc(), Sale.id.desc())
        .limit(query.limit + 1)
    ).all()
    items = [
        SaleRow(
            id=str(sale.id),
            merchant_id=str(sale.merchant_id),
            reference=sale.reference,
            amount_cents=sale.amount_cents,
            currency=sale.currency,
            concept=sale.concept,
            status=sale.status,
            covered=is_covered,
            confirmed_amount_cents=confirmed_amount,
            attempt_count=attempt_count,
            beneficiary_name=sale.beneficiary_name,
            masked_account=masked_account(sale.account_last4),
            created_at=sale.created_at,
        )
        for sale, confirmed_amount, is_covered, attempt_count in rows[: query.limit]
    ]
    last = rows[query.limit - 1][0] if len(rows) > query.limit else None
    next_cursor = None if last is None else SaleCursor(last.created_at, last.id).encode()
    return HistoryPage(items, next_cursor)
