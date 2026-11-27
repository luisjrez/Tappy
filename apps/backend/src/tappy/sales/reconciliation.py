import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import StrEnum

from sqlalchemy import select, update
from sqlalchemy.orm import Session
from sqlalchemy.sql import ColumnElement

from tappy.payments.provider import (
    PaymentEvidence,
    PaymentsQueryError,
    ProviderName,
    QrPayment,
    QrProvider,
    QueryProblem,
)
from tappy.platform.clock import Clock
from tappy.platform.database import Database
from tappy.sales.errors import AttemptNotFoundError
from tappy.sales.evidence import EvidenceOutcome, apply_evidence
from tappy.sales.models import (
    AttemptMethod,
    AttemptStatus,
    JobStatus,
    PaymentAttempt,
    ReconciliationJob,
    Sale,
    SaleStatus,
)
from tappy.sales.service import AttemptView, describe_attempt

logger = logging.getLogger(__name__)


class ReconciliationResult(StrEnum):
    CONFIRMED = "confirmed"
    VERIFIED = "verified"
    REVIEW = "review"
    NO_EVIDENCE = "no_evidence"
    UNCERTAIN = "uncertain"
    NOT_QUERYABLE = "not_queryable"


QUERYABLE_METHODS = frozenset({AttemptMethod.QR, AttemptMethod.PHONE})


@dataclass(frozen=True)
class QueryTarget:
    attempt_id: uuid.UUID
    provider: ProviderName
    provider_request_id: str
    receiver_account: str
    expired: bool
    method: AttemptMethod


@dataclass(frozen=True)
class ReconciliationReport:
    attempt: AttemptView
    sale_status: SaleStatus
    result: ReconciliationResult
    found: int = 0
    applied: int = 0
    duplicates: int = 0
    in_review: int = 0
    problem: QueryProblem | None = None
    retry_after: timedelta | None = None


def payment_queries(provider: QrProvider) -> dict[AttemptMethod, Callable[[str], list[QrPayment]]]:
    return {AttemptMethod.QR: provider.qr_payments, AttemptMethod.PHONE: provider.phone_payments}


def query_target(db: Session, attempt_id: uuid.UUID, provider: QrProvider) -> QueryTarget | None:
    attempt = db.get(PaymentAttempt, attempt_id)
    if attempt is None:
        raise AttemptNotFoundError
    if (
        attempt.method not in QUERYABLE_METHODS
        or attempt.provider_request_id is None
        or attempt.provider is not provider.name
    ):
        return None
    return QueryTarget(
        attempt.id,
        attempt.provider,
        attempt.provider_request_id,
        attempt.receiver_account,
        attempt.status is AttemptStatus.EXPIRED,
        attempt.method,
    )


def evidence_of(target: QueryTarget, payment: QrPayment, environment: str) -> PaymentEvidence:
    return PaymentEvidence(
        provider=target.provider,
        environment=environment,
        provider_request_id=target.provider_request_id,
        attempt_id=target.attempt_id,
        provider_transaction_id=payment.transaction_id,
        amount_cents=payment.amount_cents,
        receiver_account=target.receiver_account,
        occurred_at=payment.occurred_at,
        bank_time_invalid=payment.bank_time_invalid,
    )


def close_paid_jobs(db: Session, *criteria: ColumnElement[bool]) -> int:
    paid = (
        select(PaymentAttempt.id)
        .where(
            PaymentAttempt.id == ReconciliationJob.attempt_id,
            PaymentAttempt.status == AttemptStatus.PAID,
        )
        .exists()
    )
    closed = db.scalars(
        update(ReconciliationJob)
        .where(
            ReconciliationJob.status.in_([JobStatus.PENDING, JobStatus.EXHAUSTED]),
            paid,
            *criteria,
        )
        .values(status=JobStatus.DONE, lease_owner=None, lease_until=None)
        .returning(ReconciliationJob.id)
    ).all()
    return len(closed)


def mark_verified(db: Session, attempt_id: uuid.UUID, now: datetime) -> bool:
    attempt = db.scalars(
        select(PaymentAttempt)
        .where(PaymentAttempt.id == attempt_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).one()
    if attempt.status is not AttemptStatus.EXPIRED:
        return False
    if attempt.verified_at is None:
        attempt.verified_at = now
        attempt.updated_at = now
    db.flush()
    return True


def report_for(
    db: Session,
    attempt_id: uuid.UUID,
    outcomes: list[EvidenceOutcome],
    result: ReconciliationResult | None = None,
    problem: QueryProblem | None = None,
) -> ReconciliationReport:
    attempt = db.scalars(
        select(PaymentAttempt)
        .where(PaymentAttempt.id == attempt_id)
        .execution_options(populate_existing=True)
    ).one()
    sale_status = db.scalars(select(Sale.status).where(Sale.id == attempt.sale_id)).one()
    return ReconciliationReport(
        describe_attempt(attempt),
        sale_status,
        result or settled_result(attempt, outcomes),
        found=len(outcomes),
        applied=outcomes.count(EvidenceOutcome.APPLIED),
        duplicates=outcomes.count(EvidenceOutcome.DUPLICATE),
        in_review=outcomes.count(EvidenceOutcome.REVIEW),
        problem=problem,
    )


def settled_result(
    attempt: PaymentAttempt, outcomes: list[EvidenceOutcome]
) -> ReconciliationResult:
    if attempt.status is AttemptStatus.PAID:
        return ReconciliationResult.CONFIRMED
    if EvidenceOutcome.REVIEW in outcomes:
        return ReconciliationResult.REVIEW
    return ReconciliationResult.NO_EVIDENCE


def reconcile_attempt(
    database: Database,
    attempt_id: uuid.UUID,
    provider: QrProvider,
    environment: str,
    clock: Clock,
) -> ReconciliationReport:
    with database.transaction() as db:
        target = query_target(db, attempt_id, provider)
        if target is None:
            return report_for(db, attempt_id, [], ReconciliationResult.NOT_QUERYABLE)
    try:
        payments = payment_queries(provider)[target.method](target.provider_request_id)
    except PaymentsQueryError as error:
        logger.warning(
            "Payments query for attempt %s failed (%s); payment stays unconfirmed",
            attempt_id,
            error.problem,
        )
        with database.transaction() as db:
            report = report_for(db, attempt_id, [], ReconciliationResult.UNCERTAIN, error.problem)
        return replace(report, retry_after=error.retry_after)
    with database.transaction() as db:
        outcomes = [
            apply_evidence(db, evidence_of(target, payment, environment), None, clock.now())
            for payment in payments
        ]
        close_paid_jobs(db, ReconciliationJob.attempt_id == attempt_id)
        verified = (
            target.expired
            and EvidenceOutcome.REVIEW not in outcomes
            and mark_verified(db, attempt_id, clock.now())
        )
        return report_for(
            db, attempt_id, outcomes, ReconciliationResult.VERIFIED if verified else None
        )
