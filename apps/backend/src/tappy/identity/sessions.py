import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from tappy.identity.errors import IdentityError, InvalidEmailError
from tappy.identity.models import AccessSession, Identity, IdentityStatus
from tappy.identity.passwords import UNKNOWN_IDENTITY_HASH, verify_password
from tappy.identity.provisioning import IdentitySummary, by_email


class InvalidCredentialsError(IdentityError):
    def __init__(self) -> None:
        super().__init__("Invalid email or password")


class InvalidAccessTokenError(IdentityError):
    def __init__(self) -> None:
        super().__init__("Invalid access token")


@dataclass(frozen=True)
class IssuedSession:
    access_token: str
    expires_at: datetime


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def find_active_identity(db: Session, email: str, password: str) -> Identity:
    try:
        identity = db.scalar(select(Identity).where(by_email(email)))
    except InvalidEmailError:
        identity = None
    password_hash = UNKNOWN_IDENTITY_HASH if identity is None else identity.password_hash
    password_matches = verify_password(password_hash, password)
    if identity is None or not password_matches or identity.status is not IdentityStatus.ACTIVE:
        raise InvalidCredentialsError
    return identity


def log_in(
    db: Session, email: str, password: str, now: datetime, lifetime: timedelta
) -> IssuedSession:
    identity = find_active_identity(db, email, password)
    token = secrets.token_urlsafe(32)
    access = AccessSession(
        identity_id=identity.id,
        token_digest=digest(token),
        created_at=now,
        expires_at=now + lifetime,
    )
    db.add(access)
    db.flush()
    return IssuedSession(token, access.expires_at)


def is_usable(identity: Identity, access: AccessSession, now: datetime) -> bool:
    return (
        access.revoked_at is None
        and access.expires_at > now
        and identity.status is IdentityStatus.ACTIVE
    )


def resolve_identity(db: Session, token: str, now: datetime) -> IdentitySummary:
    row = db.execute(
        select(Identity, AccessSession)
        .join(AccessSession, AccessSession.identity_id == Identity.id)
        .where(AccessSession.token_digest == digest(token))
    ).one_or_none()
    if row is None or not is_usable(row.Identity, row.AccessSession, now):
        raise InvalidAccessTokenError
    return IdentitySummary.of(row.Identity)
