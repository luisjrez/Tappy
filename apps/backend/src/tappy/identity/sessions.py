import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from tappy.identity.errors import IdentityError, InvalidEmailError
from tappy.identity.models import AccessSession, Identity, IdentityStatus
from tappy.identity.passwords import UNKNOWN_IDENTITY_HASH, verify_password
from tappy.identity.provisioning import IdentitySummary, by_email
from tappy.platform.config import Settings


class InvalidCredentialsError(IdentityError):
    def __init__(self) -> None:
        super().__init__("Invalid email or password")


class InvalidAccessTokenError(IdentityError):
    def __init__(self) -> None:
        super().__init__("Invalid access token")


@dataclass(frozen=True)
class SessionPolicy:
    access_lifetime: timedelta
    max_lifetime: timedelta

    @classmethod
    def from_settings(cls, settings: Settings) -> SessionPolicy:
        return cls(
            access_lifetime=timedelta(seconds=settings.access_token_ttl_seconds),
            max_lifetime=timedelta(seconds=settings.session_max_lifetime_seconds),
        )


@dataclass(frozen=True)
class SessionFamily:
    identity_id: uuid.UUID
    family_id: uuid.UUID
    expires_at: datetime


@dataclass(frozen=True)
class IssuedSession:
    access_token: str
    refresh_token: str
    expires_at: datetime
    refresh_expires_at: datetime


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


def issue(
    db: Session, family: SessionFamily, now: datetime, policy: SessionPolicy
) -> IssuedSession:
    access_token = secrets.token_urlsafe(32)
    refresh_token = secrets.token_urlsafe(32)
    access = AccessSession(
        identity_id=family.identity_id,
        family_id=family.family_id,
        token_digest=digest(access_token),
        refresh_digest=digest(refresh_token),
        created_at=now,
        expires_at=min(now + policy.access_lifetime, family.expires_at),
        family_expires_at=family.expires_at,
    )
    db.add(access)
    db.flush()
    return IssuedSession(access_token, refresh_token, access.expires_at, family.expires_at)


def log_in(
    db: Session, email: str, password: str, now: datetime, policy: SessionPolicy
) -> IssuedSession:
    identity = find_active_identity(db, email, password)
    family = SessionFamily(identity.id, uuid.uuid4(), now + policy.max_lifetime)
    return issue(db, family, now, policy)


def revoke_family(db: Session, family_id: uuid.UUID, now: datetime) -> None:
    db.execute(
        update(AccessSession)
        .where(AccessSession.family_id == family_id, AccessSession.revoked_at.is_(None))
        .values(revoked_at=now)
    )


def renew(
    db: Session, refresh_token: str, now: datetime, policy: SessionPolicy
) -> IssuedSession | None:
    refresh_digest = digest(refresh_token)
    claimed = db.execute(
        update(AccessSession)
        .where(
            AccessSession.refresh_digest == refresh_digest,
            AccessSession.revoked_at.is_(None),
            AccessSession.rotated_at.is_(None),
            AccessSession.family_expires_at > now,
            AccessSession.identity_id.in_(
                select(Identity.id).where(Identity.status == IdentityStatus.ACTIVE)
            ),
        )
        .values(rotated_at=now)
        .returning(
            AccessSession.identity_id, AccessSession.family_id, AccessSession.family_expires_at
        )
    ).one_or_none()
    if claimed is None:
        presented = db.scalar(
            select(AccessSession.family_id).where(AccessSession.refresh_digest == refresh_digest)
        )
        if presented is not None:
            revoke_family(db, presented, now)
        return None
    family = SessionFamily(claimed.identity_id, claimed.family_id, claimed.family_expires_at)
    return issue(db, family, now, policy)


def is_usable(identity: Identity, access: AccessSession, now: datetime) -> bool:
    return (
        access.revoked_at is None
        and access.rotated_at is None
        and access.expires_at > now
        and identity.status is IdentityStatus.ACTIVE
    )


def find_access(db: Session, token: str, now: datetime) -> tuple[Identity, AccessSession]:
    row = db.execute(
        select(Identity, AccessSession)
        .join(AccessSession, AccessSession.identity_id == Identity.id)
        .where(AccessSession.token_digest == digest(token))
    ).one_or_none()
    if row is None or not is_usable(row.Identity, row.AccessSession, now):
        raise InvalidAccessTokenError
    return row.Identity, row.AccessSession


def resolve_identity(db: Session, token: str, now: datetime) -> IdentitySummary:
    identity, _ = find_access(db, token, now)
    return IdentitySummary.of(identity)


def log_out(db: Session, token: str, now: datetime) -> None:
    _, access = find_access(db, token, now)
    revoke_family(db, access.family_id, now)


def revoke_identity_sessions(db: Session, identity_id: uuid.UUID, now: datetime) -> None:
    db.execute(
        update(AccessSession)
        .where(AccessSession.identity_id == identity_id, AccessSession.revoked_at.is_(None))
        .values(revoked_at=now)
    )
