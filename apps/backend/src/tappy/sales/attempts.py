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
    IssuedPhoneRequest,
    IssuedQr,
    PhoneOrder,
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
from tappy.platform.quotas import QuotaOperation, QuotaPolicy, merchant_scope, reserve_quota
from tappy.sales.errors import (
    ActiveAttemptError,
    ReceiverChangedError,
    SaleNotOpenError,
    UnverifiedAttemptError,
)
from tappy.sales.evidence import hold_reference
from tappy.sales.expiration import enqueue_job
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
Issued = IssuedQr | IssuedPhoneRequest


@dataclass(frozen=True)
class AttemptRequest:
    actor: IdentitySummary
    sale_id: uuid.UUID
    method: AttemptMethod
    idempotency_key: str
    quota: QuotaPolicy
    phone_number: str | None = None
    phone_fingerprint: str | None = None


class AttemptOutcome(StrEnum):
    CREATED = "created"
    REPLAYED = "replayed"
    UNCERTAIN = "uncertain"


@dataclass(frozen=True)
class AttemptReservation:
    attempt: AttemptView
    outcome: AttemptOutcome


@dataclass(frozen=True)
class OpenReconciliation:
    attempt: AttemptView
    reason: JobReason
    status: JobStatus
    run_at: datetime
    tries: int
    lease_until: datetime | None
    last_problem: str | None


def reservation_claim(request: AttemptRequest, sale: Sale) -> IdempotencyClaim:
    content = {"sale_id": str(sale.id), "method": request.method.value}
    if request.phone_fingerprint is not None:
        content["phone"] = request.phone_fingerprint
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


def attempt_to_retry(db: Session, sale_id: uuid.UUID) -> PaymentAttempt | None:
    active = db.scalar(
        select(PaymentAttempt.id).where(
            PaymentAttempt.sale_id == sale_id,
            PaymentAttempt.status.in_(ACTIVE_ATTEMPT_STATUSES),
        )
    )
    if active is not None:
        raise ActiveAttemptError
    latest = db.scalar(
        select(PaymentAttempt)
        .where(PaymentAttempt.sale_id == sale_id)
        .order_by(PaymentAttempt.created_at.desc(), PaymentAttempt.id.desc())
        .limit(1)
    )
    if latest is not None and latest.status is AttemptStatus.EXPIRED and latest.verified_at is None:
        raise UnverifiedAttemptError
    return latest


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
    previous = attempt_to_retry(db, held.id)
    reserve_quota(
        db, QuotaOperation.ATTEMPT_CREATION, merchant_scope(held.merchant_id), request.quota, now
    )
    attempt = PaymentAttempt(
        id=attempt_id,
        sale_id=held.id,
        created_by=uuid.UUID(request.actor.reference),
        method=request.method,
        status=AttemptStatus.CREATING,
        provider=provider.name,
        simulated=provider.simulated,
        receiver_account=held.receiver_account,
        previous_attempt_id=None if previous is None else previous.id,
        payer_phone_suffix=None if request.phone_number is None else request.phone_number[-4:],
        created_at=now,
        updated_at=now,
    )
    db.add(attempt)
    db.flush()
    return AttemptReservation(describe_attempt(attempt), AttemptOutcome.CREATED)


def pending_order(
    db: Session, attempt_id: uuid.UUID, phone_number: str | None
) -> QrOrder | PhoneOrder | None:
    attempt = db.get_one(PaymentAttempt, attempt_id)
    if attempt.status is not AttemptStatus.CREATING:
        return None
    sale = db.get_one(Sale, attempt.sale_id)
    if attempt.method is AttemptMethod.PHONE:
        if phone_number is None:
            raise ValueError("A phone request needs the payer's phone number")
        return PhoneOrder(
            attempt.id,
            sale.reference,
            sale.amount_cents,
            sale.concept,
            attempt.receiver_account,
            phone_number,
        )
    if attempt.method is not AttemptMethod.QR:
        return None
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


def record_rejected(db: Session, attempt_id: uuid.UUID, code: str, now: datetime) -> None:
    attempt = held_attempt(db, attempt_id)
    if move(attempt, AttemptStatus.FAILED, now):
        attempt.failure_code = code
        db.flush()


def conflicting_request(issued: Issued, attempt: PaymentAttempt) -> ProviderUnavailableError:
    logger.warning(
        "Provider id %s conflicts with attempt %s or with another attempt; attempt kept",
        issued.provider_request_id,
        attempt.id,
    )
    return ProviderUnavailableError(UncertainReason.DUPLICATE_PROVIDER_ID)


def attach_issued(
    db: Session,
    attempt: PaymentAttempt,
    issued: Issued,
    now: datetime,
    expires_at: datetime | None,
) -> None:
    try:
        with db.begin_nested():
            attempt.provider_request_id = issued.provider_request_id
            if isinstance(issued, IssuedQr):
                attempt.qr_payload = issued.payload
            else:
                attempt.provider_folio = issued.folio
            attempt.expires_at = expires_at
            attempt.updated_at = now
            if attempt.status is AttemptStatus.CREATING:
                move(attempt, AttemptStatus.PENDING, now)
            else:
                logger.warning(
                    "Provider id %s arrived after attempt %s was moved to %s; kept as evidence",
                    issued.provider_request_id,
                    attempt.id,
                    attempt.status,
                )
    except IntegrityError as error:
        if is_unique_violation(error, PROVIDER_REQUEST_CONSTRAINT):
            raise conflicting_request(issued, attempt) from None
        raise


def record_issued(
    db: Session,
    attempt_id: uuid.UUID,
    issued: Issued,
    now: datetime,
    expires_at: datetime | None = None,
) -> AttemptView:
    hold_reference(db, attempt_provider(db, attempt_id), issued.provider_request_id)
    attempt = held_attempt(db, attempt_id)
    if attempt.provider_request_id not in (None, issued.provider_request_id):
        raise conflicting_request(issued, attempt)
    if attempt.qr_payload is not None or attempt.provider_folio is not None:
        return describe_attempt(attempt)
    attach_issued(db, attempt, issued, now, expires_at)
    apply_waiting_events(db, attempt, now)
    db.flush()
    return describe_attempt(attempt)


def issue(
    database: Database, provider: QrProvider, order: QrOrder | PhoneOrder, clock: Clock
) -> AttemptView:
    requested_at = clock.now()
    issued: Issued = (
        provider.request_phone_payment(order)
        if isinstance(order, PhoneOrder)
        else provider.create_qr(order)
    )
    expires_at = None if issued.valid_for is None else requested_at + issued.valid_for
    with database.transaction() as db:
        return record_issued(db, order.attempt_id, issued, clock.now(), expires_at)


def keep_for_reconciliation(
    db: Session, attempt: PaymentAttempt, reason: JobReason, now: datetime
) -> None:
    if move(attempt, AttemptStatus.RECONCILING, now):
        enqueue_job(db, attempt.id, reason, now)


def record_uncertain(
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
            else pending_order(db, uuid.UUID(reservation.attempt.id), request.phone_number)
        )
    if order is None:
        return reservation
    try:
        recorded = issue(database, provider, order, clock)
    except ProviderRejectedError as rejection:
        with database.transaction() as db:
            record_rejected(db, order.attempt_id, rejection.code, clock.now())
        raise
    except ProviderUnavailableError as uncertainty:
        with database.transaction() as db:
            recorded = record_uncertain(db, order.attempt_id, uncertainty.reason, clock.now())
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


def open_reconciliations(db: Session) -> list[OpenReconciliation]:
    rows = db.execute(
        select(ReconciliationJob, PaymentAttempt)
        .join(PaymentAttempt, PaymentAttempt.id == ReconciliationJob.attempt_id)
        .where(ReconciliationJob.status.in_([JobStatus.PENDING, JobStatus.EXHAUSTED]))
        .order_by(ReconciliationJob.run_at, ReconciliationJob.id)
    ).all()
    return [
        OpenReconciliation(
            describe_attempt(attempt),
            job.reason,
            job.status,
            job.run_at,
            job.tries,
            job.lease_until,
            job.last_problem,
        )
        for job, attempt in rows
    ]
