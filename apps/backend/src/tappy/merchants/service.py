import uuid
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from psycopg.errors import UniqueViolation
from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tappy.identity.models import Identity, IdentityStatus, Role
from tappy.identity.operators import list_operators, operator_by_reference
from tappy.identity.provisioning import IdentitySummary
from tappy.merchants.errors import (
    InvalidMerchantNameError,
    MerchantNotFoundError,
    OperatorNotAssignableError,
)
from tappy.merchants.models import Membership, Merchant


@dataclass(frozen=True)
class MemberView:
    reference: str
    email: str


@dataclass(frozen=True)
class MerchantView:
    id: str
    name: str
    members: tuple[MemberView, ...]


@dataclass(frozen=True)
class AssignmentResult:
    merchant: MerchantView
    created: bool


def clean_name(name: str) -> str:
    cleaned = " ".join(name.split())
    if not cleaned:
        raise InvalidMerchantNameError
    return cleaned


def ordered_merchants() -> Select[Merchant]:
    return select(Merchant).order_by(Merchant.name, Merchant.id)


def scoped(actor: IdentitySummary) -> Select[Merchant]:
    if actor.role is Role.ADMIN:
        return ordered_merchants()
    memberships = select(Membership.merchant_id).where(
        Membership.identity_id == uuid.UUID(actor.reference)
    )
    return ordered_merchants().where(Merchant.id.in_(memberships))


def describe_all(db: Session, merchants: Sequence[Merchant]) -> list[MerchantView]:
    members: dict[uuid.UUID, list[MemberView]] = defaultdict(list)
    rows = db.execute(
        select(Membership.merchant_id, Identity.id, Identity.email)
        .join(Identity, Identity.id == Membership.identity_id)
        .where(Membership.merchant_id.in_([merchant.id for merchant in merchants]))
        .order_by(Membership.created_at, Identity.email)
    )
    for merchant_id, identity_id, email in rows:
        members[merchant_id].append(MemberView(str(identity_id), email))
    return [
        MerchantView(str(merchant.id), merchant.name, tuple(members[merchant.id]))
        for merchant in merchants
    ]


def describe(db: Session, merchant: Merchant) -> MerchantView:
    [view] = describe_all(db, [merchant])
    return view


def merchant_or_raise(db: Session, merchant_id: uuid.UUID) -> Merchant:
    merchant = db.get(Merchant, merchant_id)
    if merchant is None:
        raise MerchantNotFoundError
    return merchant


def accessible_merchant(db: Session, actor: IdentitySummary, merchant_id: uuid.UUID) -> Merchant:
    merchant = db.scalar(scoped(actor).where(Merchant.id == merchant_id))
    if merchant is None:
        raise MerchantNotFoundError
    return merchant


def create_merchant(db: Session, name: str, now: datetime) -> MerchantView:
    merchant = Merchant(name=clean_name(name), created_at=now)
    db.add(merchant)
    db.flush()
    return describe(db, merchant)


def list_merchants(db: Session, actor: IdentitySummary) -> list[MerchantView]:
    return describe_all(db, list(db.scalars(scoped(actor))))


def list_all_merchants(db: Session) -> list[MerchantView]:
    return describe_all(db, list(db.scalars(ordered_merchants())))


def read_merchant(db: Session, actor: IdentitySummary, merchant_id: uuid.UUID) -> MerchantView:
    return describe(db, accessible_merchant(db, actor, merchant_id))


def assignable_operators(db: Session) -> list[IdentitySummary]:
    return [operator for operator in list_operators(db) if operator.status is IdentityStatus.ACTIVE]


def assignable_operator(db: Session, operator_reference: uuid.UUID) -> Identity:
    operator = db.scalar(operator_by_reference(operator_reference).with_for_update(read=True))
    if operator is None or operator.status is not IdentityStatus.ACTIVE:
        raise OperatorNotAssignableError
    return operator


def assign_operator(
    db: Session, merchant_id: uuid.UUID, operator_reference: uuid.UUID, now: datetime
) -> AssignmentResult:
    merchant = merchant_or_raise(db, merchant_id)
    operator = assignable_operator(db, operator_reference)
    existing = db.scalar(
        select(Membership.id).where(
            Membership.merchant_id == merchant.id, Membership.identity_id == operator.id
        )
    )
    if existing is not None:
        return AssignmentResult(describe(db, merchant), created=False)
    try:
        with db.begin_nested():
            db.add(Membership(merchant_id=merchant.id, identity_id=operator.id, created_at=now))
    except IntegrityError as error:
        if not isinstance(error.orig, UniqueViolation):
            raise
        return AssignmentResult(describe(db, merchant), created=False)
    return AssignmentResult(describe(db, merchant), created=True)
