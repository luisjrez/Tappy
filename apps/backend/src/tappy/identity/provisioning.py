from dataclasses import dataclass

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tappy.identity.models import Role, User, UserStatus
from tappy.identity.passwords import hash_password


class ProvisioningError(Exception):
    pass


class IdentityAlreadyExistsError(ProvisioningError):
    pass


@dataclass(frozen=True)
class IdentitySummary:
    reference: str
    email: str
    role: Role
    status: UserStatus

    @classmethod
    def of(cls, user: User) -> IdentitySummary:
        return cls(str(user.id), user.email, user.role, user.status)


def normalize_email(email: str) -> str:
    try:
        return validate_email(email.strip(), check_deliverability=False).normalized.lower()
    except EmailNotValidError as error:
        raise ProvisioningError(f"Invalid email: {error}") from None


def find_identity(session: Session, email: str) -> IdentitySummary | None:
    user = session.scalar(select(User).where(User.email == normalize_email(email)))
    return None if user is None else IdentitySummary.of(user)


def provision_admin(session: Session, email: str, password: str) -> IdentitySummary:
    normalized = normalize_email(email)
    if session.scalar(select(User.id).where(User.email == normalized)) is not None:
        raise IdentityAlreadyExistsError("An identity with this email already exists")
    user = User(
        email=normalized,
        password_hash=hash_password(password),
        role=Role.ADMIN,
        status=UserStatus.ACTIVE,
    )
    session.add(user)
    try:
        session.flush()
    except IntegrityError:
        raise IdentityAlreadyExistsError("An identity with this email already exists") from None
    return IdentitySummary.of(user)
