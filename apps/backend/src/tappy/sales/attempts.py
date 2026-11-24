import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from tappy.identity.provisioning import IdentitySummary
from tappy.merchants.receivers import held_issuing_receiver
from tappy.sales.errors import ActiveAttemptError, SaleNotOpenError
from tappy.sales.idempotency import (
    IdempotencyClaim,
    IdempotentOperation,
    claim_or_replay,
    digest_of,
)
from tappy.sales.models import (
    ACTIVE_ATTEMPT_STATUSES,
    AttemptMethod,
    AttemptStatus,
    PaymentAttempt,
    Sale,
    SaleStatus,
)
from tappy.sales.service import AttemptView, accessible_sale, describe_attempt


@dataclass(frozen=True)
class AttemptRequest:
    actor: IdentitySummary
    sale_id: uuid.UUID
    method: AttemptMethod
    idempotency_key: str


@dataclass(frozen=True)
class AttemptReservation:
    attempt: AttemptView
    replayed: bool


def reservation_claim(request: AttemptRequest, sale: Sale) -> IdempotencyClaim:
    content = {"sale_id": str(sale.id), "method": request.method.value}
    return IdempotencyClaim(
        uuid.UUID(request.actor.reference),
        IdempotentOperation.CREATE_ATTEMPT,
        request.idempotency_key,
        digest_of(content),
    )


def held_open_sale(db: Session, sale_id: uuid.UUID) -> Sale:
    sale = db.scalars(
        select(Sale)
        .where(Sale.id == sale_id)
        .with_for_update(key_share=True)
        .execution_options(populate_existing=True)
    ).one()
    if sale.status is not SaleStatus.OPEN:
        raise SaleNotOpenError
    return sale


def ensure_no_active_attempt(db: Session, sale_id: uuid.UUID) -> None:
    active = db.scalar(
        select(PaymentAttempt.id).where(
            PaymentAttempt.sale_id == sale_id,
            PaymentAttempt.status.in_(ACTIVE_ATTEMPT_STATUSES),
        )
    )
    if active is not None:
        raise ActiveAttemptError


def reserve_attempt(db: Session, request: AttemptRequest, now: datetime) -> AttemptReservation:
    sale = accessible_sale(db, request.actor, request.sale_id)
    attempt_id = uuid.uuid4()
    replayed_id = claim_or_replay(db, reservation_claim(request, sale), attempt_id, now)
    if replayed_id is not None:
        replayed = db.get_one(PaymentAttempt, replayed_id)
        return AttemptReservation(describe_attempt(replayed), replayed=True)
    held = held_open_sale(db, sale.id)
    held_issuing_receiver(db, held.merchant_id)
    ensure_no_active_attempt(db, held.id)
    attempt = PaymentAttempt(
        id=attempt_id,
        sale_id=held.id,
        created_by=uuid.UUID(request.actor.reference),
        method=request.method,
        status=AttemptStatus.CREATING,
        created_at=now,
        updated_at=now,
    )
    db.add(attempt)
    db.flush()
    return AttemptReservation(describe_attempt(attempt), replayed=False)
