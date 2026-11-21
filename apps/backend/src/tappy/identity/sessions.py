import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from tappy.identity.errors import IdentityError, InvalidEmailError
from tappy.identity.models import AccessSession, Identity, IdentityStatus
from tappy.identity.passwords import hasher, verify_password
from tappy.identity.provisioning import IdentitySummary, by_email

TIMING_EQUALIZER_HASH = hasher.hash("timing equalizer for unknown identities")


class AuthenticationError(IdentityError):
    def __init__(self) -> None:
        super().__init__("Invalid email or password")


class UnauthorizedError(IdentityError):
    pass


@dataclass(frozen=True)
class IssuedSession:
    access_token: str
    expires_at: datetime


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def find_active_identity(session: Session, email: str, password: str) -> Identity:
    try:
        identity = session.scalar(select(Identity).where(by_email(email)))
    except InvalidEmailError:
        identity = None
    password_hash = TIMING_EQUALIZER_HASH if identity is None else identity.password_hash
    password_matches = verify_password(password_hash, password)
    if identity is None or not password_matches or identity.status is not IdentityStatus.ACTIVE:
        raise AuthenticationError
    return identity


def log_in(
    session: Session, email: str, password: str, now: datetime, lifetime: timedelta
) -> IssuedSession:
    identity = find_active_identity(session, email, password)
    token = secrets.token_urlsafe(32)
    access = AccessSession(
        identity_id=identity.id,
        token_digest=digest(token),
        created_at=now,
        expires_at=now + lifetime,
    )
    session.add(access)
    session.flush()
    return IssuedSession(token, access.expires_at)


def resolve_identity(session: Session, token: str, now: datetime) -> IdentitySummary:
    row = session.execute(
        select(Identity, AccessSession)
        .join(AccessSession, AccessSession.identity_id == Identity.id)
        .where(AccessSession.token_digest == digest(token))
    ).one_or_none()
    if row is None:
        raise UnauthorizedError("Invalid session")
    identity, access = row
    if (
        access.revoked_at is not None
        or access.expires_at <= now
        or identity.status is not IdentityStatus.ACTIVE
    ):
        raise UnauthorizedError("Invalid session")
    return IdentitySummary.of(identity)
