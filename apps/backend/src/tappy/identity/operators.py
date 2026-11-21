import uuid
from datetime import datetime

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from tappy.identity.errors import IdentityNotFoundError
from tappy.identity.lifecycle import deactivate_and_revoke
from tappy.identity.models import Identity, Role
from tappy.identity.provisioning import IdentitySummary, provision_identity


def create_operator(db: Session, email: str, initial_password: str) -> IdentitySummary:
    return provision_identity(db, email, initial_password, Role.OPERATOR)


def list_operators(db: Session) -> list[IdentitySummary]:
    operators = db.scalars(
        select(Identity).where(Identity.role == Role.OPERATOR).order_by(Identity.email)
    )
    return [IdentitySummary.of(operator) for operator in operators]


def operator_by_reference(reference: uuid.UUID) -> Select[Identity]:
    return select(Identity).where(Identity.id == reference, Identity.role == Role.OPERATOR)


def find_operator(db: Session, reference: uuid.UUID) -> IdentitySummary:
    operator = db.scalar(operator_by_reference(reference))
    if operator is None:
        raise IdentityNotFoundError
    return IdentitySummary.of(operator)


def deactivate_operator(db: Session, reference: uuid.UUID, now: datetime) -> IdentitySummary:
    operator = db.scalar(operator_by_reference(reference).with_for_update(key_share=True))
    if operator is None:
        raise IdentityNotFoundError
    return deactivate_and_revoke(db, operator, now)
