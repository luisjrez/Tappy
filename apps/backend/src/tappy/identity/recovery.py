import hashlib
import hmac
import secrets
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timedelta

from cryptography.fernet import InvalidToken
from sqlalchemy import delete, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from tappy.identity.errors import InvalidEmailError
from tappy.identity.models import Identity, IdentityStatus
from tappy.identity.provisioning import by_email, normalize_email
from tappy.identity.recovery_models import PasswordResetRequest, RecoveryAttempt, RecoveryJob
from tappy.notifications.outbox import enqueue_email
from tappy.notifications.sealing import Sealer
from tappy.notifications.transport import Envelope
from tappy.platform.config import Settings
from tappy.platform.database import Database

RESET_PATH = "/password-reset"
SUBJECT = "Reset your Tappy password"
RECOVERY_ACCEPTED = "If the account exists, a recovery email may be sent"
MAXIMUM_EMAIL_LENGTH = 254
JOB_BATCH_SIZE = 50


@dataclass(frozen=True)
class RecoveryPolicy:
    public_base_url: str
    token_lifetime: timedelta
    limit_per_email: int
    limit_per_origin: int
    window: timedelta
    limit_key: bytes

    @classmethod
    def from_settings(cls, settings: Settings) -> RecoveryPolicy:
        secret = settings.secret_key.get_secret_value().encode()
        return cls(
            public_base_url=settings.public_base_url,
            token_lifetime=timedelta(seconds=settings.password_reset_ttl_seconds),
            limit_per_email=settings.recovery_limit_per_email,
            limit_per_origin=settings.recovery_limit_per_origin,
            window=timedelta(seconds=settings.recovery_window_seconds),
            limit_key=hmac.new(secret, b"tappy-recovery-limits-v1", hashlib.sha256).digest(),
        )

    def subject_digest(self, kind: str, value: str) -> str:
        return hmac.new(self.limit_key, f"{kind}:{value}".encode(), hashlib.sha256).hexdigest()


@dataclass(frozen=True)
class RecoverySubmission:
    email: str
    origin: str


@dataclass(frozen=True)
class RecoveryService:
    policy: RecoveryPolicy
    sealer: Sealer

    @classmethod
    def from_settings(cls, settings: Settings) -> RecoveryService:
        return cls(RecoveryPolicy.from_settings(settings), Sealer.from_settings(settings))

    def submit(self, db: Session, submission: RecoverySubmission, now: datetime) -> None:
        submit_recovery(db, submission, now, self.policy, self.sealer)

    def process_jobs(self, database: Database, now: datetime) -> int:
        return process_recovery_jobs(database, now, self.policy, self.sealer)


def within_limit(db: Session, digest: str, limit: int, since: datetime, now: datetime) -> bool:
    db.add(RecoveryAttempt(subject_digest=digest, created_at=now))
    db.flush()
    attempts = db.scalar(
        select(func.count())
        .select_from(RecoveryAttempt)
        .where(RecoveryAttempt.subject_digest == digest, RecoveryAttempt.created_at > since)
    )
    return (attempts or 0) <= limit


def submit_recovery(
    db: Session,
    submission: RecoverySubmission,
    now: datetime,
    policy: RecoveryPolicy,
    sealer: Sealer,
) -> None:
    if len(submission.email) > MAXIMUM_EMAIL_LENGTH:
        return
    try:
        email = normalize_email(submission.email)
    except InvalidEmailError:
        return
    since = now - policy.window
    email_digest = policy.subject_digest("email", email)
    origin_digest = policy.subject_digest("origin", submission.origin)
    email_allowed = within_limit(db, email_digest, policy.limit_per_email, since, now)
    origin_allowed = within_limit(db, origin_digest, policy.limit_per_origin, since, now)
    if email_allowed and origin_allowed:
        db.add(RecoveryJob(sealed_email=sealer.seal(email), created_at=now))


def reset_link(policy: RecoveryPolicy, token: str) -> str:
    return f"{policy.public_base_url}{RESET_PATH}#token={token}"


def recovery_message(link: str, lifetime: timedelta) -> str:
    minutes = int(lifetime.total_seconds() // 60)
    return (
        "We received a request to reset your Tappy password.\n\n"
        f"Open this link within the next {minutes} minutes:\n{link}\n\n"
        "If you did not ask for it, ignore this email; your password stays the same."
    )


def issue_reset(
    db: Session, identity: Identity, now: datetime, policy: RecoveryPolicy, sealer: Sealer
) -> None:
    token = secrets.token_urlsafe(32)
    db.add(
        PasswordResetRequest(
            identity_id=identity.id,
            token_digest=hashlib.sha256(token.encode()).hexdigest(),
            created_at=now,
            expires_at=now + policy.token_lifetime,
        )
    )
    body = recovery_message(reset_link(policy, token), policy.token_lifetime)
    enqueue_email(db, Envelope(identity.email, SUBJECT, body), sealer, now)


def resolve_job(
    db: Session, job: RecoveryJob, now: datetime, policy: RecoveryPolicy, sealer: Sealer
) -> None:
    sealed_email, job.sealed_email, job.processed_at = job.sealed_email, None, now
    if sealed_email is None:
        return
    try:
        email = sealer.open(sealed_email)
    except InvalidToken:
        return
    identity = db.scalar(select(Identity).where(by_email(email)))
    if identity is not None and identity.status is IdentityStatus.ACTIVE:
        issue_reset(db, identity, now, policy, sealer)


def process_recovery_jobs(
    database: Database, now: datetime, policy: RecoveryPolicy, sealer: Sealer
) -> int:
    with database.transaction() as db:
        jobs = list(
            db.scalars(
                select(RecoveryJob)
                .where(RecoveryJob.processed_at.is_(None))
                .order_by(RecoveryJob.created_at)
                .limit(JOB_BATCH_SIZE)
                .with_for_update(skip_locked=True)
            )
        )
        for job in jobs:
            with suppress(SQLAlchemyError), db.begin_nested():
                resolve_job(db, job, now, policy, sealer)
        db.execute(delete(RecoveryAttempt).where(RecoveryAttempt.created_at <= now - policy.window))
        return len(jobs)
