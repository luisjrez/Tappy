from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from tappy.identity.errors import InvalidResetLinkError
from tappy.identity.models import Identity, IdentityStatus
from tappy.identity.passwords import PasswordPolicy
from tappy.identity.provisioning import IdentitySummary
from tappy.identity.recovery_models import PasswordResetRequest
from tappy.identity.sessions import revoke_identity_sessions
from tappy.identity.tokens import token_digest

PasswordChangedNotice = Callable[[Session, Identity, datetime], None]


@dataclass(frozen=True)
class PasswordChange:
    token: str
    new_password: str
    policy: PasswordPolicy


def lock_owner(db: Session, digest: str) -> Identity:
    identity = db.scalar(
        select(Identity)
        .join(PasswordResetRequest, PasswordResetRequest.identity_id == Identity.id)
        .where(PasswordResetRequest.token_digest == digest)
        .with_for_update(of=Identity, key_share=True)
    )
    if identity is None or identity.status is not IdentityStatus.ACTIVE:
        raise InvalidResetLinkError
    return identity


def pending_reset(db: Session, digest: str, now: datetime) -> PasswordResetRequest:
    reset = db.scalar(
        select(PasswordResetRequest)
        .where(
            PasswordResetRequest.token_digest == digest,
            PasswordResetRequest.consumed_at.is_(None),
            PasswordResetRequest.invalidated_at.is_(None),
            PasswordResetRequest.expires_at > now,
        )
        .with_for_update()
    )
    if reset is None:
        raise InvalidResetLinkError
    return reset


def invalidate_other_links(db: Session, reset: PasswordResetRequest, now: datetime) -> None:
    db.execute(
        update(PasswordResetRequest)
        .where(
            PasswordResetRequest.identity_id == reset.identity_id,
            PasswordResetRequest.id != reset.id,
            PasswordResetRequest.consumed_at.is_(None),
            PasswordResetRequest.invalidated_at.is_(None),
        )
        .values(invalidated_at=now)
    )


def confirm_password_reset(
    db: Session, change: PasswordChange, now: datetime, notice: PasswordChangedNotice
) -> IdentitySummary:
    digest = token_digest(change.token)
    identity = lock_owner(db, digest)
    reset = pending_reset(db, digest, now)
    identity.password_hash = change.policy.hash(change.new_password)
    reset.consumed_at = now
    invalidate_other_links(db, reset, now)
    revoke_identity_sessions(db, identity.id, now)
    notice(db, identity, now)
    db.flush()
    return IdentitySummary.of(identity)
