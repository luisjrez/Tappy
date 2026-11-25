from datetime import datetime

from tappy.sales.models import AttemptStatus, PaymentAttempt

ALLOWED_TRANSITIONS: dict[AttemptStatus, frozenset[AttemptStatus]] = {
    AttemptStatus.CREATING: frozenset(
        {AttemptStatus.PENDING, AttemptStatus.RECONCILING, AttemptStatus.FAILED, AttemptStatus.PAID}
    ),
    AttemptStatus.PENDING: frozenset({AttemptStatus.PAID}),
    AttemptStatus.RECONCILING: frozenset({AttemptStatus.PAID}),
    AttemptStatus.EXPIRED: frozenset({AttemptStatus.PAID}),
    AttemptStatus.FAILED: frozenset(),
    AttemptStatus.PAID: frozenset(),
}

PAYABLE_ATTEMPT_STATUSES = tuple(
    source for source, targets in ALLOWED_TRANSITIONS.items() if AttemptStatus.PAID in targets
)


def can_move(source: AttemptStatus, target: AttemptStatus) -> bool:
    return target in ALLOWED_TRANSITIONS[source]


def move(attempt: PaymentAttempt, target: AttemptStatus, now: datetime) -> bool:
    if not can_move(attempt.status, target):
        return False
    attempt.status = target
    attempt.updated_at = now
    return True
