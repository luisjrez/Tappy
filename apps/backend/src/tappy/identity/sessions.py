import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import ColumnElement, func, select, update
from sqlalchemy.orm import Session

from tappy.identity.errors import IdentityError, InvalidEmailError
from tappy.identity.models import AccessSession, Identity, IdentityStatus, Role
from tappy.identity.passwords import UNKNOWN_IDENTITY_HASH, verify_password
from tappy.identity.provisioning import IdentitySummary, by_email
from tappy.platform.config import Settings
from tappy.platform.database import Database

ADVISORY_KEY_MASK = (1 << 63) - 1


class InvalidCredentialsError(IdentityError):
    def __init__(self) -> None:
        super().__init__("Invalid email or password")


class InvalidAccessTokenError(IdentityError):
    def __init__(self) -> None:
        super().__init__("Invalid access token")


class RoleNotAllowedError(IdentityError):
    def __init__(self) -> None:
        super().__init__("Role not allowed")


class InvalidRefreshTokenError(IdentityError):
    def __init__(self) -> None:
        super().__init__("Invalid refresh token")


class RefreshTokenReuseError(InvalidRefreshTokenError):
    def __init__(self, family_id: uuid.UUID) -> None:
        super().__init__()
        self.family_id = family_id


@dataclass(frozen=True)
class SessionPolicy:
    access_lifetime: timedelta
    max_lifetime: timedelta
    reuse_grace: timedelta = timedelta(seconds=10)

    @classmethod
    def from_settings(cls, settings: Settings) -> SessionPolicy:
        return cls(
            access_lifetime=timedelta(seconds=settings.access_token_ttl_seconds),
            max_lifetime=timedelta(seconds=settings.session_max_lifetime_seconds),
        )


@dataclass(frozen=True)
class LoginCredentials:
    email: str
    password: str


@dataclass(frozen=True)
class SessionTokens:
    access_token: str
    refresh_token: str


@dataclass(frozen=True)
class ResumedSession:
    identity: IdentitySummary
    tokens: SessionTokens


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

    @property
    def tokens(self) -> SessionTokens:
        return SessionTokens(self.access_token, self.refresh_token)


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def find_active_identity(
    db: Session, credentials: LoginCredentials, required_role: Role | None = None
) -> Identity:
    try:
        identity = db.scalar(select(Identity).where(by_email(credentials.email)))
    except InvalidEmailError:
        identity = None
    password_hash = UNKNOWN_IDENTITY_HASH if identity is None else identity.password_hash
    password_matches = verify_password(password_hash, credentials.password)
    if identity is None or not password_matches or identity.status is not IdentityStatus.ACTIVE:
        raise InvalidCredentialsError
    if required_role is not None and identity.role is not required_role:
        raise InvalidCredentialsError
    return identity


def issue_session(
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
    db: Session,
    credentials: LoginCredentials,
    now: datetime,
    policy: SessionPolicy,
    required_role: Role | None = None,
) -> IssuedSession:
    identity = find_active_identity(db, credentials, required_role)
    family = SessionFamily(identity.id, uuid.uuid4(), now + policy.max_lifetime)
    return issue_session(db, family, now, policy)


def revoke_sessions(db: Session, scope: ColumnElement[bool], now: datetime) -> None:
    db.execute(
        update(AccessSession)
        .where(scope, AccessSession.revoked_at.is_(None))
        .values(revoked_at=now)
    )


def lock_family(db: Session, family_id: uuid.UUID) -> None:
    db.execute(select(func.pg_advisory_xact_lock(family_id.int & ADVISORY_KEY_MASK)))


def revoke_family(db: Session, family_id: uuid.UUID, now: datetime) -> None:
    lock_family(db, family_id)
    revoke_sessions(db, AccessSession.family_id == family_id, now)


def revoke_identity_sessions(db: Session, identity_id: uuid.UUID, now: datetime) -> None:
    revoke_sessions(db, AccessSession.identity_id == identity_id, now)


def renew(db: Session, refresh_token: str, now: datetime, policy: SessionPolicy) -> IssuedSession:
    refresh_digest = digest(refresh_token)
    presented = db.execute(
        select(AccessSession.family_id, AccessSession.rotated_at).where(
            AccessSession.refresh_digest == refresh_digest
        )
    ).one_or_none()
    if presented is None:
        raise InvalidRefreshTokenError
    if presented.rotated_at is not None and presented.rotated_at <= now - policy.reuse_grace:
        raise RefreshTokenReuseError(presented.family_id)
    lock_family(db, presented.family_id)
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
        raise InvalidRefreshTokenError
    family = SessionFamily(claimed.identity_id, claimed.family_id, claimed.family_expires_at)
    return issue_session(db, family, now, policy)


def is_current(identity: Identity, access: AccessSession) -> bool:
    return (
        access.revoked_at is None
        and access.rotated_at is None
        and identity.status is IdentityStatus.ACTIVE
    )


def find_access(
    db: Session, token: str, now: datetime, *, allow_expired: bool = False
) -> tuple[Identity, AccessSession]:
    row = db.execute(
        select(Identity, AccessSession)
        .join(AccessSession, AccessSession.identity_id == Identity.id)
        .where(AccessSession.token_digest == digest(token))
    ).one_or_none()
    if row is None or not is_current(row.Identity, row.AccessSession):
        raise InvalidAccessTokenError
    if not allow_expired and row.AccessSession.expires_at <= now:
        raise InvalidAccessTokenError
    return row.Identity, row.AccessSession


def resolve_identity(db: Session, token: str, now: datetime) -> IdentitySummary:
    identity, _ = find_access(db, token, now)
    return IdentitySummary.of(identity)


def log_out(db: Session, token: str, now: datetime) -> None:
    _, access = find_access(db, token, now, allow_expired=True)
    revoke_family(db, access.family_id, now)


def renew_session(
    database: Database, refresh_token: str, now: datetime, policy: SessionPolicy
) -> IssuedSession:
    try:
        with database.transaction() as db:
            return renew(db, refresh_token, now, policy)
    except RefreshTokenReuseError as reuse:
        with database.transaction() as db:
            revoke_family(db, reuse.family_id, now)
        raise


def current_summary(
    database: Database, access_token: str, now: datetime, required_role: Role | None
) -> IdentitySummary:
    with database.transaction() as db:
        identity, _ = find_access(db, access_token, now)
        if required_role is not None and identity.role is not required_role:
            raise RoleNotAllowedError
        return IdentitySummary.of(identity)


def resume_session(
    database: Database,
    tokens: SessionTokens,
    now: datetime,
    policy: SessionPolicy,
    required_role: Role | None = None,
) -> ResumedSession:
    try:
        return ResumedSession(
            current_summary(database, tokens.access_token, now, required_role), tokens
        )
    except InvalidAccessTokenError:
        renewed = renew_session(database, tokens.refresh_token, now, policy).tokens
    return ResumedSession(
        current_summary(database, renewed.access_token, now, required_role), renewed
    )
