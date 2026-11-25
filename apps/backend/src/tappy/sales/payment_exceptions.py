from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from tappy.payments.events import WebhookEvent
from tappy.sales.models import ExceptionReason, PaymentException, Sale


@dataclass(frozen=True)
class OpenException:
    id: str
    reason: ExceptionReason
    sale_reference: str | None
    event_id: str | None
    expected_amount_cents: int | None
    received_amount_cents: int | None
    created_at: datetime


def open_exceptions(db: Session) -> list[OpenException]:
    rows = db.execute(
        select(PaymentException, Sale.reference, WebhookEvent.provider_event_id)
        .outerjoin(Sale, Sale.id == PaymentException.sale_id)
        .outerjoin(WebhookEvent, WebhookEvent.id == PaymentException.webhook_event_id)
        .where(PaymentException.resolved_at.is_(None))
        .order_by(PaymentException.created_at, PaymentException.id)
    ).all()
    return [
        OpenException(
            str(exception.id),
            exception.reason,
            reference,
            event_id,
            exception.expected_amount_cents,
            exception.received_amount_cents,
            exception.created_at,
        )
        for exception, reference, event_id in rows
    ]
