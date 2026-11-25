import secrets
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tappy.identity.provisioning import IdentitySummary
from tappy.merchants.receivers import held_issuing_receiver, masked_account
from tappy.merchants.service import accessible_merchant, scoped_ids
from tappy.platform.persistence import is_unique_violation
from tappy.sales.errors import InvalidConceptError, SaleNotFoundError
from tappy.sales.expiration import expire_due_attempts
from tappy.sales.idempotency import (
    IdempotencyClaim,
    IdempotentOperation,
    claim_or_replay,
    digest_of,
)
from tappy.sales.models import (
    CONCEPT_MAX_LENGTH,
    REFERENCE_CONSTRAINT,
    REFERENCE_LENGTH,
    AttemptMethod,
    AttemptStatus,
    ExceptionReason,
    PaymentAttempt,
    Sale,
    SaleStatus,
)
from tappy.sales.money import validated_amount

REFERENCE_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
REFERENCE_ATTEMPTS = 3


@dataclass(frozen=True)
class SaleRequest:
    actor: IdentitySummary
    merchant_id: uuid.UUID
    amount_cents: int
    concept: str | None
    idempotency_key: str


class NextAction(StrEnum):
    WAIT_FOR_QR = "wait_for_qr"
    SHOW_QR = "show_qr"
    WAIT_FOR_VERIFICATION = "wait_for_verification"
    VERIFY_BEFORE_RETRY = "verify_before_retry"
    NEW_ATTEMPT = "new_attempt"
    NONE = "none"


NEXT_ACTIONS = {
    AttemptStatus.CREATING: NextAction.WAIT_FOR_QR,
    AttemptStatus.PENDING: NextAction.SHOW_QR,
    AttemptStatus.RECONCILING: NextAction.WAIT_FOR_VERIFICATION,
    AttemptStatus.EXPIRED: NextAction.VERIFY_BEFORE_RETRY,
    AttemptStatus.FAILED: NextAction.NEW_ATTEMPT,
    AttemptStatus.PAID: NextAction.NONE,
}


@dataclass(frozen=True)
class AttemptView:
    id: str
    sale_id: str
    sale_reference: str
    method: AttemptMethod
    status: AttemptStatus
    simulated: bool
    provider_request_id: str | None
    qr_payload: str | None
    failure_code: str | None
    created_at: datetime
    expires_at: datetime | None
    next_action: NextAction
    verified_at: datetime | None
    previous_attempt_id: str | None
    late_payment_possible: bool


@dataclass(frozen=True)
class TransferView:
    provider_transaction_id: str
    amount_cents: int
    occurred_at: datetime
    received_at: datetime
    beneficiary_name: str
    masked_account: str


@dataclass(frozen=True)
class ExceptionView:
    reason: ExceptionReason
    expected_amount_cents: int | None
    received_amount_cents: int | None
    created_at: datetime
    resolved_at: datetime | None


@dataclass(frozen=True)
class SaleView:
    id: str
    merchant_id: str
    reference: str
    amount_cents: int
    currency: str
    concept: str | None
    status: SaleStatus
    beneficiary_name: str
    masked_account: str
    created_at: datetime
    attempts: list[AttemptView]
    confirmed_amount_cents: int
    transfers: list[TransferView]
    exceptions: list[ExceptionView]


@dataclass(frozen=True)
class SaleCreation:
    sale: SaleView
    replayed: bool


def clean_concept(concept: str | None) -> str | None:
    cleaned = " ".join((concept or "").split())
    if len(cleaned) > CONCEPT_MAX_LENGTH:
        raise InvalidConceptError(CONCEPT_MAX_LENGTH)
    return cleaned or None


def new_reference() -> str:
    return "".join(secrets.choice(REFERENCE_ALPHABET) for _ in range(REFERENCE_LENGTH))


def insert_with_fresh_reference(db: Session, sale: Sale) -> None:
    for attempt in range(1, REFERENCE_ATTEMPTS + 1):
        sale.reference = new_reference()
        try:
            with db.begin_nested():
                db.add(sale)
            return
        except IntegrityError as error:
            if (
                not is_unique_violation(error, REFERENCE_CONSTRAINT)
                or attempt == REFERENCE_ATTEMPTS
            ):
                raise


def describe_attempt(attempt: PaymentAttempt) -> AttemptView:
    return AttemptView(
        id=str(attempt.id),
        sale_id=str(attempt.sale_id),
        sale_reference=attempt.sale.reference,
        method=attempt.method,
        status=attempt.status,
        simulated=attempt.simulated,
        provider_request_id=attempt.provider_request_id,
        qr_payload=attempt.qr_payload,
        failure_code=attempt.failure_code,
        created_at=attempt.created_at,
        expires_at=attempt.expires_at,
        next_action=next_action(attempt),
        verified_at=attempt.verified_at,
        previous_attempt_id=(
            None if attempt.previous_attempt_id is None else str(attempt.previous_attempt_id)
        ),
        late_payment_possible=late_payment_possible(attempt),
    )


def next_action(attempt: PaymentAttempt) -> NextAction:
    if attempt.status is AttemptStatus.EXPIRED and attempt.verified_at is not None:
        return NextAction.NEW_ATTEMPT
    return NEXT_ACTIONS[attempt.status]


def late_payment_possible(attempt: PaymentAttempt) -> bool:
    previous = attempt.previous_attempt
    while previous is not None:
        if previous.provider_request_id is not None:
            return True
        previous = previous.previous_attempt
    return False


def describe_sale(sale: Sale) -> SaleView:
    return SaleView(
        id=str(sale.id),
        merchant_id=str(sale.merchant_id),
        reference=sale.reference,
        amount_cents=sale.amount_cents,
        currency=sale.currency,
        concept=sale.concept,
        status=sale.status,
        beneficiary_name=sale.beneficiary_name,
        masked_account=masked_account(sale.account_last4),
        created_at=sale.created_at,
        attempts=[describe_attempt(attempt) for attempt in sale.attempts],
        confirmed_amount_cents=sum(transfer.amount_cents for transfer in sale.transfers),
        transfers=[
            TransferView(
                transfer.provider_transaction_id,
                transfer.amount_cents,
                transfer.occurred_at,
                transfer.received_at,
                sale.beneficiary_name,
                masked_account(sale.account_last4),
            )
            for transfer in sale.transfers
        ],
        exceptions=[
            ExceptionView(
                exception.reason,
                exception.expected_amount_cents,
                exception.received_amount_cents,
                exception.created_at,
                exception.resolved_at,
            )
            for exception in sale.exceptions
        ],
    )


def creation_claim(request: SaleRequest, content: Mapping[str, object]) -> IdempotencyClaim:
    return IdempotencyClaim(
        uuid.UUID(request.actor.reference),
        IdempotentOperation.CREATE_SALE,
        request.idempotency_key,
        digest_of(content),
    )


def create_sale(db: Session, request: SaleRequest, maximum: int, now: datetime) -> SaleCreation:
    amount_cents = validated_amount(request.amount_cents, maximum)
    concept = clean_concept(request.concept)
    merchant = accessible_merchant(db, request.actor, request.merchant_id)
    content = {"merchant_id": str(merchant.id), "amount_cents": amount_cents, "concept": concept}
    sale_id = uuid.uuid4()
    replayed_id = claim_or_replay(db, creation_claim(request, content), sale_id, now)
    if replayed_id is not None:
        return SaleCreation(describe_sale(db.get_one(Sale, replayed_id)), replayed=True)
    receiver = held_issuing_receiver(db, merchant.id)
    sale = Sale(
        id=sale_id,
        merchant_id=merchant.id,
        created_by=uuid.UUID(request.actor.reference),
        amount_cents=amount_cents,
        concept=concept,
        status=SaleStatus.OPEN,
        receiving_account_id=receiver.id,
        receiver_account=receiver.provider_account_id,
        beneficiary_name=receiver.beneficiary_name,
        account_last4=receiver.account_last4,
        created_at=now,
    )
    insert_with_fresh_reference(db, sale)
    return SaleCreation(describe_sale(sale), replayed=False)


def held_sale(db: Session, sale_id: uuid.UUID) -> Sale:
    return db.scalars(
        select(Sale)
        .where(Sale.id == sale_id)
        .with_for_update(key_share=True)
        .execution_options(populate_existing=True)
    ).one()


def accessible_sale(db: Session, actor: IdentitySummary, sale_id: uuid.UUID) -> Sale:
    sale = db.scalar(
        select(Sale).where(Sale.id == sale_id, Sale.merchant_id.in_(scoped_ids(actor)))
    )
    if sale is None:
        raise SaleNotFoundError
    return sale


def read_sale(db: Session, actor: IdentitySummary, sale_id: uuid.UUID, now: datetime) -> SaleView:
    sale = accessible_sale(db, actor, sale_id)
    expire_due_attempts(db, now, sale.id)
    return describe_sale(sale)
