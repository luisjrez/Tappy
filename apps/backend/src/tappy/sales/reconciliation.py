import logging
import uuid
from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy import select, update
from sqlalchemy.orm import Session

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
    REVIEW = "review"
    NO_EVIDENCE = "no_evidence"
    UNCERTAIN = "uncertain"
    NOT_QUERYABLE = "not_queryable"


@dataclass(frozen=True)
class QueryTarget:
    attempt_id: uuid.UUID
    provider: ProviderName
    provider_request_id: str
    receiver_account: str


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


def query_target(db: Session, attempt_id: uuid.UUID, provider: QrProvider) -> QueryTarget | None:
    attempt = db.get(PaymentAttempt, attempt_id)
    if attempt is None:
        raise AttemptNotFoundError
    if attempt.provider_request_id is None or attempt.provider is not provider.name:
        return None
    return QueryTarget(
        attempt.id, attempt.provider, attempt.provider_request_id, attempt.receiver_account
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
    )


def close_jobs_if_paid(db: Session, attempt_id: uuid.UUID) -> None:
    paid = (
        select(PaymentAttempt.id)
        .where(PaymentAttempt.id == attempt_id, PaymentAttempt.status == AttemptStatus.PAID)
        .exists()
    )
    db.execute(
        update(ReconciliationJob)
        .where(
            ReconciliationJob.attempt_id == attempt_id,
            ReconciliationJob.status == JobStatus.PENDING,
            paid,
        )
        .values(status=JobStatus.DONE)
    )


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
        payments = provider.qr_payments(target.provider_request_id)
    except PaymentsQueryError as error:
        logger.warning(
            "QR payments query for attempt %s failed (%s); payment stays unconfirmed",
            attempt_id,
            error.problem,
        )
        with database.transaction() as db:
            return report_for(db, attempt_id, [], ReconciliationResult.UNCERTAIN, error.problem)
    with database.transaction() as db:
        outcomes = [
            apply_evidence(db, evidence_of(target, payment, environment), None, clock.now())
            for payment in payments
        ]
        close_jobs_if_paid(db, attempt_id)
        return report_for(db, attempt_id, outcomes)
