import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from tappy.identity.provisioning import IdentitySummary
from tappy.merchants.receivers import MASKED_DIGITS, held_issuing_receiver
from tappy.merchants.service import scoped_ids
from tappy.sales.errors import InvalidConceptError, SaleNotFoundError
from tappy.sales.models import CONCEPT_MAX_LENGTH, REFERENCE_LENGTH, Sale, SaleStatus
from tappy.sales.money import validated_amount

REFERENCE_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


@dataclass(frozen=True)
class SaleRequest:
    merchant_id: uuid.UUID
    amount_cents: int
    concept: str | None


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


def clean_concept(concept: str | None) -> str | None:
    cleaned = " ".join((concept or "").split())
    if len(cleaned) > CONCEPT_MAX_LENGTH:
        raise InvalidConceptError(CONCEPT_MAX_LENGTH)
    return cleaned or None


def new_reference() -> str:
    return "".join(secrets.choice(REFERENCE_ALPHABET) for _ in range(REFERENCE_LENGTH))


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
        masked_account="*" * MASKED_DIGITS + sale.account_last4,
        created_at=sale.created_at,
    )


def create_sale(
    db: Session, actor: IdentitySummary, request: SaleRequest, maximum: int, now: datetime
) -> SaleView:
    amount_cents = validated_amount(request.amount_cents, maximum)
    concept = clean_concept(request.concept)
    receiver = held_issuing_receiver(db, actor, request.merchant_id)
    sale = Sale(
        merchant_id=receiver.merchant_id,
        created_by=uuid.UUID(actor.reference),
        amount_cents=amount_cents,
        concept=concept,
        reference=new_reference(),
        status=SaleStatus.OPEN,
        receiving_account_id=receiver.id,
        beneficiary_name=receiver.beneficiary_name,
        account_last4=receiver.account_last4,
        created_at=now,
    )
    db.add(sale)
    db.flush()
    return describe_sale(sale)


def read_sale(db: Session, actor: IdentitySummary, sale_id: uuid.UUID) -> SaleView:
    sale = db.scalar(
        select(Sale).where(Sale.id == sale_id, Sale.merchant_id.in_(scoped_ids(actor)))
    )
    if sale is None:
        raise SaleNotFoundError
    return describe_sale(sale)
