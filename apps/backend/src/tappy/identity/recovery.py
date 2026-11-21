import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tappy.identity.errors import InvalidEmailError
from tappy.identity.models import Identity, IdentityStatus
from tappy.identity.provisioning import by_email, normalize_email
from tappy.identity.recovery_models import PasswordResetRequest, RecoveryAttempt
from tappy.notifications.outbox import enqueue_email
from tappy.notifications.sealing import Sealer
from tappy.notifications.transport import Envelope
from tappy.platform.config import Settings

RESET_PATH = "/password-reset"
SUBJECT = "Restablece tu contraseña de Tappy"
RECOVERY_ACCEPTED = "If the account exists, a recovery email will be sent"


@dataclass(frozen=True)
class RecoveryService:
    policy: RecoveryPolicy
    sealer: Sealer

    @classmethod
    def from_settings(cls, settings: Settings) -> RecoveryService:
        return cls(RecoveryPolicy.from_settings(settings), Sealer.from_settings(settings))

    def request(self, db: Session, request: RecoveryRequest, now: datetime) -> None:
        request_password_reset(db, request, now, self.policy, self.sealer)


@dataclass(frozen=True)
class RecoveryRequest:
    email: str
    origin: str


@dataclass(frozen=True)
class RecoveryPolicy:
    public_base_url: str
    token_lifetime: timedelta
    limit_per_email: int
    limit_per_origin: int
    window: timedelta

    @classmethod
    def from_settings(cls, settings: Settings) -> RecoveryPolicy:
        return cls(
            public_base_url=settings.public_base_url,
            token_lifetime=timedelta(seconds=settings.password_reset_ttl_seconds),
            limit_per_email=settings.recovery_limit_per_email,
            limit_per_origin=settings.recovery_limit_per_origin,
            window=timedelta(seconds=settings.recovery_window_seconds),
        )


def subject_digest(kind: str, value: str) -> str:
    return hashlib.sha256(f"{kind}:{value}".encode()).hexdigest()


def within_limit(db: Session, digest: str, limit: int, now: datetime, window: timedelta) -> bool:
    db.add(RecoveryAttempt(subject_digest=digest, created_at=now))
    db.flush()
    attempts = db.scalar(
        select(func.count())
        .select_from(RecoveryAttempt)
        .where(RecoveryAttempt.subject_digest == digest, RecoveryAttempt.created_at > now - window)
    )
    return (attempts or 0) <= limit


def reset_link(policy: RecoveryPolicy, token: str) -> str:
    return f"{policy.public_base_url}{RESET_PATH}?token={token}"


def recovery_message(link: str, lifetime: timedelta) -> str:
    minutes = int(lifetime.total_seconds() // 60)
    return (
        "Recibimos una solicitud para restablecer tu contraseña de Tappy.\n\n"
        f"Abre este enlace en los próximos {minutes} minutos:\n{link}\n\n"
        "Si no la pediste, ignora este correo; tu contraseña no cambia."
    )


def request_password_reset(
    db: Session, request: RecoveryRequest, now: datetime, policy: RecoveryPolicy, sealer: Sealer
) -> None:
    token = secrets.token_urlsafe(32)
    token_digest = hashlib.sha256(token.encode()).hexdigest()
    try:
        normalized_email = normalize_email(request.email)
    except InvalidEmailError:
        return
    email_allowed = within_limit(
        db, subject_digest("email", normalized_email), policy.limit_per_email, now, policy.window
    )
    origin_allowed = within_limit(
        db, subject_digest("origin", request.origin), policy.limit_per_origin, now, policy.window
    )
    if not (email_allowed and origin_allowed):
        return
    identity = db.scalar(select(Identity).where(by_email(normalized_email)))
    if identity is None or identity.status is not IdentityStatus.ACTIVE:
        return
    db.add(
        PasswordResetRequest(
            identity_id=identity.id,
            token_digest=token_digest,
            created_at=now,
            expires_at=now + policy.token_lifetime,
        )
    )
    body = recovery_message(reset_link(policy, token), policy.token_lifetime)
    enqueue_email(db, Envelope(identity.email, SUBJECT, body), sealer, now)
