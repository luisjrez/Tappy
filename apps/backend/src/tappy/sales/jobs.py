import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from sqlalchemy import case, or_, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from tappy.payments.provider import QrProvider
from tappy.platform.clock import Clock
from tappy.platform.config import Settings
from tappy.platform.database import Database
from tappy.sales.attempts import recover_interrupted
from tappy.sales.expiration import expire_due_attempts
from tappy.sales.models import JobStatus, ReconciliationJob
from tappy.sales.receptions import ProcessingSummary, process_received_events
from tappy.sales.reconciliation import (
    ReconciliationReport,
    ReconciliationResult,
    close_paid_jobs,
    reconcile_attempt,
)

logger = logging.getLogger(__name__)

LEASE_EXPIRED = "lease_expired"


class JobOutcome(StrEnum):
    CONFIRMED = "confirmed"
    VERIFIED = "verified"
    IN_REVIEW = "in_review"
    RESCHEDULED = "rescheduled"
    EXHAUSTED = "exhausted"
    LEASE_LOST = "lease_lost"
    FAILED = "failed"


FINISHED = {
    ReconciliationResult.CONFIRMED: JobOutcome.CONFIRMED,
    ReconciliationResult.VERIFIED: JobOutcome.VERIFIED,
    ReconciliationResult.REVIEW: JobOutcome.IN_REVIEW,
}


@dataclass(frozen=True)
class JobPolicy:
    lease: timedelta
    batch_size: int
    max_tries: int
    backoff: timedelta
    backoff_max: timedelta
    creation_timeout: timedelta

    @classmethod
    def from_settings(cls, settings: Settings) -> JobPolicy:
        return cls(
            lease=timedelta(seconds=settings.job_lease_seconds),
            batch_size=settings.job_batch_size,
            max_tries=settings.job_max_tries,
            backoff=timedelta(seconds=settings.job_backoff_seconds),
            backoff_max=timedelta(seconds=settings.job_backoff_max_seconds),
            creation_timeout=timedelta(seconds=settings.attempt_creation_timeout_seconds),
        )

    def delay(self, tries: int, retry_after: timedelta | None) -> timedelta:
        growing = min(self.backoff * (1 << min(tries - 1, 30)), self.backoff_max)
        return max(growing, retry_after or timedelta(0))


@dataclass(frozen=True)
class ClaimedJob:
    id: uuid.UUID
    attempt_id: uuid.UUID
    owner: uuid.UUID
    tries: int


@dataclass(frozen=True)
class JobRunSummary:
    events: ProcessingSummary
    recovered: int
    claimed: int = 0
    confirmed: int = 0
    verified: int = 0
    in_review: int = 0
    rescheduled: int = 0
    exhausted: int = 0
    lease_lost: int = 0
    closed: int = 0
    expired: int = 0
    failed: int = 0


def exhaust_abandoned(db: Session, policy: JobPolicy, now: datetime) -> int:
    abandoned = db.scalars(
        update(ReconciliationJob)
        .where(
            ReconciliationJob.status == JobStatus.PENDING,
            ReconciliationJob.tries >= policy.max_tries,
            or_(ReconciliationJob.lease_until.is_(None), ReconciliationJob.lease_until <= now),
        )
        .values(
            status=JobStatus.EXHAUSTED,
            lease_owner=None,
            lease_until=None,
            last_problem=case(
                (ReconciliationJob.lease_until.is_not(None), LEASE_EXPIRED),
                else_=ReconciliationJob.last_problem,
            ),
        )
        .returning(ReconciliationJob.id)
    ).all()
    return len(abandoned)


def claim_jobs(db: Session, policy: JobPolicy, now: datetime) -> list[ClaimedJob]:
    due = db.scalars(
        select(ReconciliationJob.id)
        .where(
            ReconciliationJob.status == JobStatus.PENDING,
            ReconciliationJob.run_at <= now,
            ReconciliationJob.tries < policy.max_tries,
            or_(ReconciliationJob.lease_until.is_(None), ReconciliationJob.lease_until <= now),
        )
        .order_by(ReconciliationJob.run_at, ReconciliationJob.id)
        .limit(policy.batch_size)
        .with_for_update(skip_locked=True)
    ).all()
    if not due:
        return []
    owner = uuid.uuid4()
    rows = db.execute(
        update(ReconciliationJob)
        .where(ReconciliationJob.id.in_(due))
        .values(
            lease_owner=owner,
            lease_until=now + policy.lease,
            tries=ReconciliationJob.tries + 1,
        )
        .returning(ReconciliationJob.id, ReconciliationJob.attempt_id, ReconciliationJob.tries)
    ).all()
    return [ClaimedJob(job_id, attempt_id, owner, tries) for job_id, attempt_id, tries in rows]


def held_claim(db: Session, job: ClaimedJob) -> ReconciliationJob | None:
    return db.scalar(
        select(ReconciliationJob)
        .where(
            ReconciliationJob.id == job.id,
            ReconciliationJob.lease_owner == job.owner,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def finish_job(db: Session, job: ClaimedJob) -> bool:
    current = db.scalars(
        select(ReconciliationJob)
        .where(ReconciliationJob.id == job.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).one()
    if current.status is JobStatus.DONE:
        return True
    if current.status is not JobStatus.PENDING or current.lease_owner != job.owner:
        return False
    current.status = JobStatus.DONE
    current.lease_owner = None
    current.lease_until = None
    return True


def reschedule_job(
    db: Session,
    job: ClaimedJob,
    policy: JobPolicy,
    now: datetime,
    report: ReconciliationReport,
) -> JobOutcome:
    held = held_claim(db, job)
    if held is None:
        return JobOutcome.LEASE_LOST
    held.last_problem = report.problem or report.result
    held.lease_owner = None
    held.lease_until = None
    if held.tries >= policy.max_tries or report.result is ReconciliationResult.NOT_QUERYABLE:
        held.status = JobStatus.EXHAUSTED
        return JobOutcome.EXHAUSTED
    held.run_at = now + policy.delay(held.tries, report.retry_after)
    return JobOutcome.RESCHEDULED


@dataclass(frozen=True)
class JobRunner:
    database: Database
    provider: QrProvider
    environment: str
    policy: JobPolicy
    clock: Clock

    def run(self) -> JobRunSummary:
        events = process_received_events(self.database, self.clock, self.policy.batch_size)
        now = self.clock.now()
        with self.database.transaction() as db:
            closed = close_paid_jobs(db)
            expired = expire_due_attempts(db, now)
            recovered = recover_interrupted(db, now - self.policy.creation_timeout, now)
            abandoned = exhaust_abandoned(db, self.policy, now)
            claimed = claim_jobs(db, self.policy, now)
        outcomes = [self.run_claimed(job) for job in claimed]
        return JobRunSummary(
            events=events,
            recovered=recovered,
            claimed=len(claimed),
            confirmed=outcomes.count(JobOutcome.CONFIRMED),
            verified=outcomes.count(JobOutcome.VERIFIED),
            in_review=outcomes.count(JobOutcome.IN_REVIEW),
            rescheduled=outcomes.count(JobOutcome.RESCHEDULED),
            exhausted=outcomes.count(JobOutcome.EXHAUSTED) + abandoned,
            lease_lost=outcomes.count(JobOutcome.LEASE_LOST),
            closed=closed,
            expired=expired,
            failed=outcomes.count(JobOutcome.FAILED),
        )

    def run_claimed(self, job: ClaimedJob) -> JobOutcome:
        try:
            return self.run_job(job)
        except SQLAlchemyError as error:
            logger.error(
                "Reconciliation job %s failed (%s); it is retried after its lease",
                job.id,
                type(error).__name__,
            )
            return JobOutcome.FAILED

    def run_job(self, job: ClaimedJob) -> JobOutcome:
        report = reconcile_attempt(
            self.database, job.attempt_id, self.provider, self.environment, self.clock
        )
        with self.database.transaction() as db:
            finished = FINISHED.get(report.result)
            if finished is None:
                return reschedule_job(db, job, self.policy, self.clock.now(), report)
            return finished if finish_job(db, job) else JobOutcome.LEASE_LOST
