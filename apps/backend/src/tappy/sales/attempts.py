import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tappy.identity.provisioning import IdentitySummary
from tappy.merchants.models import ReceivingAccount
from tappy.merchants.receivers import held_issuing_receiver
from tappy.payments.provider import (
    IssuedQr,
    ProviderName,
    ProviderRejectedError,
    ProviderUnavailableError,
    QrOrder,
    QrProvider,
    UncertainReason,
)
from tappy.platform.clock import Clock
from tappy.platform.database import Database
from tappy.platform.persistence import is_unique_violation
from tappy.sales.errors import ActiveAttemptError, ReceiverChangedError, SaleNotOpenError
from tappy.sales.evidence import hold_reference
from tappy.sales.idempotency import (
    IdempotencyClaim,
    IdempotentOperation,
    claim_or_replay,
    digest_of,
)
from tappy.sales.models import (
    ACTIVE_ATTEMPT_STATUSES,
    PROVIDER_REQUEST_CONSTRAINT,
    AttemptMethod,
    AttemptStatus,
    JobReason,
    JobStatus,
    PaymentAttempt,
    ReconciliationJob,
    Sale,
    SaleStatus,
)
from tappy.sales.receptions import apply_waiting_events
from tappy.sales.service import AttemptView, accessible_sale, describe_attempt, held_sale
from tappy.sales.transitions import move

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AttemptRequest:
    actor: IdentitySummary
    sale_id: uuid.UUID
    method: AttemptMethod
    idempotency_key: str


class AttemptOutcome(StrEnum):
    CREATED = "created"
    REPLAYED = "replayed"
    UNCERTAIN = "uncertain"


@dataclass(frozen=True)
class AttemptReservation:
    attempt: AttemptView
    outcome: AttemptOutcome


@dataclass(frozen=True)
class PendingReconciliation:
    attempt: AttemptView
    reason: JobReason
    status: JobStatus
    run_at: datetime


def reservation_claim(request: AttemptRequest, sale: Sale) -> IdempotencyClaim:
    content = {"sale_id": str(sale.id), "method": request.method.value}
    return IdempotencyClaim(
        uuid.UUID(request.actor.reference),
        IdempotentOperation.CREATE_ATTEMPT,
        request.idempotency_key,
        digest_of(content),
    )


def held_open_sale(db: Session, sale_id: uuid.UUID) -> Sale:
    sale = held_sale(db, sale_id)
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
    if (receiver.provider_account_id, receiver.beneficiary_name, receiver.account_last4) != (
        sale.receiver_account,
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
        return AttemptReservation(describe_attempt(replayed), AttemptOutcome.REPLAYED)
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
        receiver_account=held.receiver_account,
        created_at=now,
        updated_at=now,
    )
    db.add(attempt)
    db.flush()
    return AttemptReservation(describe_attempt(attempt), AttemptOutcome.CREATED)


def pending_qr_order(db: Session, attempt_id: uuid.UUID) -> QrOrder | None:
    attempt = db.get_one(PaymentAttempt, attempt_id)
    if attempt.method is not AttemptMethod.QR or attempt.status is not AttemptStatus.CREATING:
        return None
    sale = db.get_one(Sale, attempt.sale_id)
    return QrOrder(
        attempt.id, sale.reference, sale.amount_cents, sale.concept, attempt.receiver_account
    )


def attempt_provider(db: Session, attempt_id: uuid.UUID) -> ProviderName:
    return db.scalars(select(PaymentAttempt.provider).where(PaymentAttempt.id == attempt_id)).one()


def held_attempt(db: Session, attempt_id: uuid.UUID) -> PaymentAttempt:
    return db.scalars(
        select(PaymentAttempt)
        .where(PaymentAttempt.id == attempt_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).one()


def record_rejected_qr(db: Session, attempt_id: uuid.UUID, code: str, now: datetime) -> None:
    attempt = held_attempt(db, attempt_id)
    if move(attempt, AttemptStatus.FAILED, now):
        attempt.failure_code = code
        db.flush()


def attach_issued_qr(db: Session, attempt: PaymentAttempt, issued: IssuedQr, now: datetime) -> None:
    try:
        with db.begin_nested():
            attempt.provider_request_id = issued.provider_request_id
            attempt.qr_payload = issued.payload
            attempt.updated_at = now
            if attempt.status is AttemptStatus.CREATING:
                move(attempt, AttemptStatus.PENDING, now)
            else:
                logger.warning(
                    "QR %s arrived after attempt %s was moved to %s; kept as evidence",
                    issued.provider_request_id,
                    attempt.id,
                    attempt.status,
                )
    except IntegrityError as error:
        if is_unique_violation(error, PROVIDER_REQUEST_CONSTRAINT):
            logger.warning(
                "QR provider id %s is already linked to another attempt; attempt %s kept",
                issued.provider_request_id,
                attempt.id,
            )
            raise ProviderUnavailableError(UncertainReason.DUPLICATE_PROVIDER_ID) from None
        raise


def record_issued_qr(
    db: Session, attempt_id: uuid.UUID, issued: IssuedQr, now: datetime
) -> AttemptView:
    hold_reference(db, attempt_provider(db, attempt_id), issued.provider_request_id)
    attempt = held_attempt(db, attempt_id)
    if attempt.provider_request_id not in (None, issued.provider_request_id):
        logger.warning(
            "QR %s differs from QR %s already linked to attempt %s; attempt kept",
            issued.provider_request_id,
            attempt.provider_request_id,
            attempt.id,
        )
        raise ProviderUnavailableError(UncertainReason.DUPLICATE_PROVIDER_ID)
    if attempt.qr_payload is not None:
        return describe_attempt(attempt)
    attach_issued_qr(db, attempt, issued, now)
    apply_waiting_events(db, attempt, now)
    db.flush()
    return describe_attempt(attempt)


def keep_for_reconciliation(
    db: Session, attempt: PaymentAttempt, reason: JobReason, now: datetime
) -> None:
    if not move(attempt, AttemptStatus.RECONCILING, now):
        return
    db.add(
        ReconciliationJob(
            attempt_id=attempt.id,
            reason=reason,
            status=JobStatus.PENDING,
            run_at=now,
            created_at=now,
        )
    )
    db.flush()


def record_uncertain_qr(
    db: Session, attempt_id: uuid.UUID, reason: UncertainReason, now: datetime
) -> AttemptView:
    attempt = held_attempt(db, attempt_id)
    keep_for_reconciliation(db, attempt, JobReason(reason.value), now)
    return describe_attempt(attempt)


def request_attempt(
    database: Database, request: AttemptRequest, provider: QrProvider, clock: Clock
) -> AttemptReservation:
    with database.transaction() as db:
        reservation = reserve_attempt(db, request, provider, clock.now())
        order = (
            None
            if reservation.outcome is AttemptOutcome.REPLAYED
            else pending_qr_order(db, uuid.UUID(reservation.attempt.id))
        )
    if order is None:
        return reservation
    try:
        issued = provider.create_qr(order)
        with database.transaction() as db:
            recorded = record_issued_qr(db, order.attempt_id, issued, clock.now())
    except ProviderRejectedError as rejection:
        with database.transaction() as db:
            record_rejected_qr(db, order.attempt_id, rejection.code, clock.now())
        raise
    except ProviderUnavailableError as uncertainty:
        with database.transaction() as db:
            recorded = record_uncertain_qr(db, order.attempt_id, uncertainty.reason, clock.now())
    return settled_reservation(recorded)


def settled_reservation(attempt: AttemptView) -> AttemptReservation:
    if attempt.status is AttemptStatus.RECONCILING:
        return AttemptReservation(attempt, AttemptOutcome.UNCERTAIN)
    return AttemptReservation(attempt, AttemptOutcome.CREATED)


def recover_interrupted(db: Session, cutoff: datetime, now: datetime) -> int:
    interrupted = db.scalars(
        select(PaymentAttempt)
        .where(
            PaymentAttempt.status == AttemptStatus.CREATING,
            PaymentAttempt.updated_at < cutoff,
        )
        .with_for_update(skip_locked=True)
    ).all()
    for attempt in interrupted:
        keep_for_reconciliation(db, attempt, JobReason.INTERRUPTED_CREATION, now)
    return len(interrupted)


def pending_reconciliations(db: Session) -> list[PendingReconciliation]:
    rows = db.execute(
        select(ReconciliationJob, PaymentAttempt)
        .join(PaymentAttempt, PaymentAttempt.id == ReconciliationJob.attempt_id)
        .where(ReconciliationJob.status == JobStatus.PENDING)
        .order_by(ReconciliationJob.run_at, ReconciliationJob.id)
    ).tuples()
    return [
        PendingReconciliation(describe_attempt(attempt), job.reason, job.status, job.run_at)
        for job, attempt in rows
    ]
