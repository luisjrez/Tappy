import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from tappy.identity.provisioning import IdentitySummary
from tappy.merchants.models import ReceivingAccount
from tappy.merchants.receivers import held_issuing_receiver
from tappy.payments.provider import IssuedQr, QrOrder, QrProvider
from tappy.platform.clock import Clock
from tappy.platform.database import Database
from tappy.sales.errors import ActiveAttemptError, ReceiverChangedError, SaleNotOpenError
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


def ensure_same_receiver(sale: Sale, receiver: ReceivingAccount) -> None:
    if (receiver.beneficiary_name, receiver.account_last4) != (
        sale.beneficiary_name,
        sale.account_last4,
    ):
        raise ReceiverChangedError


def reserve_attempt(
    db: Session, request: AttemptRequest, provider: QrProvider, now: datetime
) -> AttemptReservation:
    sale = accessible_sale(db, request.actor, request.sale_id)
    attempt_id = uuid.uuid4()
    replayed_id = claim_or_replay(db, reservation_claim(request, sale), attempt_id, now)
    if replayed_id is not None:
        replayed = db.get_one(PaymentAttempt, replayed_id)
        return AttemptReservation(describe_attempt(replayed), replayed=True)
    held = held_open_sale(db, sale.id)
    receiver = held_issuing_receiver(db, held.merchant_id)
    ensure_same_receiver(held, receiver)
    ensure_no_active_attempt(db, held.id)
    attempt = PaymentAttempt(
        id=attempt_id,
        sale_id=held.id,
        created_by=uuid.UUID(request.actor.reference),
        method=request.method,
        status=AttemptStatus.CREATING,
        provider=provider.name,
        simulated=provider.simulated,
        receiver_account=receiver.provider_account_id,
        created_at=now,
        updated_at=now,
    )
    db.add(attempt)
    db.flush()
    return AttemptReservation(describe_attempt(attempt), replayed=False)


def pending_qr_order(db: Session, attempt_id: uuid.UUID) -> QrOrder | None:
    attempt = db.get_one(PaymentAttempt, attempt_id)
    if attempt.method is not AttemptMethod.QR or attempt.status is not AttemptStatus.CREATING:
        return None
    sale = db.get_one(Sale, attempt.sale_id)
    return QrOrder(attempt.id, sale.amount_cents, sale.concept, attempt.receiver_account)


def record_issued_qr(
    db: Session, attempt_id: uuid.UUID, issued: IssuedQr, now: datetime
) -> AttemptView:
    attempt = db.scalars(
        select(PaymentAttempt)
        .where(PaymentAttempt.id == attempt_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).one()
    if attempt.status is AttemptStatus.CREATING:
        attempt.provider_request_id = issued.provider_request_id
        attempt.qr_payload = issued.payload
        attempt.status = AttemptStatus.PENDING
        attempt.updated_at = now
        db.flush()
    return describe_attempt(attempt)


def request_attempt(
    database: Database, request: AttemptRequest, provider: QrProvider, clock: Clock
) -> AttemptReservation:
    with database.transaction() as db:
        reservation = reserve_attempt(db, request, provider, clock.now())
        order = (
            None
            if reservation.replayed
            else pending_qr_order(db, uuid.UUID(reservation.attempt.id))
        )
    if order is None:
        return reservation
    issued = provider.create_qr(order)
    with database.transaction() as db:
        return AttemptReservation(
            record_issued_qr(db, order.attempt_id, issued, clock.now()), replayed=False
        )
