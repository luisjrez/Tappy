from dataclasses import dataclass

from email_validator import EmailNotValidError, validate_email
from psycopg.errors import UniqueViolation
from sqlalchemy import ColumnElement, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tappy.identity.errors import (
    IdentityAlreadyExistsError,
    IdentityNotFoundError,
    InvalidEmailError,
)
from tappy.identity.models import Identity, IdentityStatus, Role
from tappy.identity.passwords import DEFAULT_POLICY, PasswordPolicy


@dataclass(frozen=True)
class IdentitySummary:
    reference: str
    email: str
    role: Role
    status: IdentityStatus

    @classmethod
    def of(cls, identity: Identity) -> IdentitySummary:
        return cls(str(identity.id), identity.email, identity.role, identity.status)


def normalize_email(email: str) -> str:
    try:
        return validate_email(email.strip(), check_deliverability=False).normalized.lower()
    except EmailNotValidError as error:
        raise InvalidEmailError(f"Invalid email: {error}") from None


def by_email(email: str) -> ColumnElement[bool]:
    return func.lower(Identity.email) == normalize_email(email)


def find_identity(session: Session, email: str) -> IdentitySummary:
    identity = session.scalar(select(Identity).where(by_email(email)))
    if identity is None:
        raise IdentityNotFoundError
    return IdentitySummary.of(identity)


def provision_admin(
    session: Session, email: str, password: str, policy: PasswordPolicy = DEFAULT_POLICY
) -> IdentitySummary:
    return provision_identity(session, email, password, Role.ADMIN, policy)


def provision_identity(
    session: Session,
    email: str,
    password: str,
    role: Role,
    policy: PasswordPolicy = DEFAULT_POLICY,
) -> IdentitySummary:
    normalized_email = normalize_email(email)
    if session.scalar(select(Identity.id).where(by_email(normalized_email))) is not None:
        raise IdentityAlreadyExistsError
    identity = Identity(
        email=normalized_email,
        password_hash=policy.hash(password),
        role=role,
        status=IdentityStatus.ACTIVE,
    )
    session.add(identity)
    try:
        session.flush()
    except IntegrityError as error:
        if isinstance(error.orig, UniqueViolation):
            raise IdentityAlreadyExistsError from None
        raise
    return IdentitySummary.of(identity)
