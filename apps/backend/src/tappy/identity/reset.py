import hashlib
from collections.abc import Callable
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from tappy.identity.errors import InvalidResetLinkError
from tappy.identity.models import Identity, IdentityStatus
from tappy.identity.passwords import hash_password
from tappy.identity.provisioning import IdentitySummary
from tappy.identity.recovery_models import PasswordResetRequest
from tappy.identity.sessions import revoke_identity_sessions

PasswordChangedNotice = Callable[[Session, Identity, datetime], None]


def pending_reset(db: Session, token: str, now: datetime) -> PasswordResetRequest:
    reset = db.scalar(
        select(PasswordResetRequest)
        .where(
            PasswordResetRequest.token_digest == hashlib.sha256(token.encode()).hexdigest(),
            PasswordResetRequest.consumed_at.is_(None),
            PasswordResetRequest.invalidated_at.is_(None),
            PasswordResetRequest.expires_at > now,
        )
        .with_for_update()
    )
    if reset is None:
        raise InvalidResetLinkError
    return reset


def active_owner(db: Session, reset: PasswordResetRequest) -> Identity:
    identity = db.scalar(
        select(Identity).where(Identity.id == reset.identity_id).with_for_update(key_share=True)
    )
    if identity is None or identity.status is not IdentityStatus.ACTIVE:
        raise InvalidResetLinkError
    return identity


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
    db: Session, token: str, new_password: str, now: datetime, notice: PasswordChangedNotice
) -> IdentitySummary:
    reset = pending_reset(db, token, now)
    identity = active_owner(db, reset)
    identity.password_hash = hash_password(new_password)
    reset.consumed_at = now
    invalidate_other_links(db, reset, now)
    revoke_identity_sessions(db, identity.id, now)
    notice(db, identity, now)
    db.flush()
    return IdentitySummary.of(identity)
