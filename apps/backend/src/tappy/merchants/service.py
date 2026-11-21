import uuid
from dataclasses import dataclass
from datetime import datetime

from psycopg.errors import UniqueViolation
from sqlalchemy import ColumnElement, Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tappy.identity.models import Identity, IdentityStatus, Role
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


def visible_to(actor: IdentitySummary) -> ColumnElement[bool] | None:
    if actor.role is Role.ADMIN:
        return None
    return Merchant.id.in_(
        select(Membership.merchant_id).where(Membership.identity_id == uuid.UUID(actor.reference))
    )


def scoped(actor: IdentitySummary) -> Select[Merchant]:
    query = select(Merchant).order_by(Merchant.name, Merchant.id)
    scope = visible_to(actor)
    return query if scope is None else query.where(scope)


def describe(db: Session, merchant: Merchant) -> MerchantView:
    members = db.execute(
        select(Identity.id, Identity.email)
        .join(Membership, Membership.identity_id == Identity.id)
        .where(Membership.merchant_id == merchant.id)
        .order_by(Membership.created_at, Identity.email)
    ).all()
    return MerchantView(
        str(merchant.id),
        merchant.name,
        tuple(MemberView(str(member.id), member.email) for member in members),
    )


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


def rename_merchant(db: Session, merchant_id: uuid.UUID, name: str) -> MerchantView:
    merchant = db.get(Merchant, merchant_id)
    if merchant is None:
        raise MerchantNotFoundError
    merchant.name = clean_name(name)
    db.flush()
    return describe(db, merchant)


def list_merchants(db: Session, actor: IdentitySummary) -> list[MerchantView]:
    return [describe(db, merchant) for merchant in db.scalars(scoped(actor))]


def list_all_merchants(db: Session) -> list[MerchantView]:
    merchants = db.scalars(select(Merchant).order_by(Merchant.name, Merchant.id))
    return [describe(db, merchant) for merchant in merchants]


def read_merchant(db: Session, actor: IdentitySummary, merchant_id: uuid.UUID) -> MerchantView:
    return describe(db, accessible_merchant(db, actor, merchant_id))


def assign_operator(
    db: Session, merchant_id: uuid.UUID, operator_id: uuid.UUID, now: datetime
) -> AssignmentResult:
    merchant = db.get(Merchant, merchant_id)
    if merchant is None:
        raise MerchantNotFoundError
    operator = db.get(Identity, operator_id)
    if (
        operator is None
        or operator.role is not Role.OPERATOR
        or operator.status is not IdentityStatus.ACTIVE
    ):
        raise OperatorNotAssignableError
    existing = db.scalar(
        select(Membership.id).where(
            Membership.merchant_id == merchant_id, Membership.identity_id == operator_id
        )
    )
    if existing is not None:
        return AssignmentResult(describe(db, merchant), created=False)
    try:
        with db.begin_nested():
            db.add(Membership(merchant_id=merchant_id, identity_id=operator_id, created_at=now))
    except IntegrityError as error:
        if not isinstance(error.orig, UniqueViolation):
            raise
        return AssignmentResult(describe(db, merchant), created=False)
    return AssignmentResult(describe(db, merchant), created=True)
