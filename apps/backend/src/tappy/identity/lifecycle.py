from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from tappy.identity.errors import IdentityNotFoundError
from tappy.identity.models import Identity, IdentityStatus
from tappy.identity.provisioning import IdentitySummary, by_email
from tappy.identity.sessions import revoke_identity_sessions


def lock_identity(db: Session, email: str) -> Identity:
    identity = db.scalar(select(Identity).where(by_email(email)).with_for_update(key_share=True))
    if identity is None:
        raise IdentityNotFoundError
    return identity


def deactivate_identity(db: Session, email: str, now: datetime) -> IdentitySummary:
    return deactivate_and_revoke(db, lock_identity(db, email), now)


def deactivate_and_revoke(db: Session, identity: Identity, now: datetime) -> IdentitySummary:
    identity.status = IdentityStatus.INACTIVE
    revoke_identity_sessions(db, identity.id, now)
    db.flush()
    return IdentitySummary.of(identity)
