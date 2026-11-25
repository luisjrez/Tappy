import pytest

from tappy.sales.models import AttemptStatus
from tappy.sales.transitions import PAYABLE_ATTEMPT_STATUSES, can_move


@pytest.mark.parametrize(
    ("source", "target", "allowed"),
    [
        (AttemptStatus.PAID, AttemptStatus.PENDING, False),
        (AttemptStatus.PAID, AttemptStatus.RECONCILING, False),
        (AttemptStatus.PAID, AttemptStatus.FAILED, False),
        (AttemptStatus.FAILED, AttemptStatus.PAID, False),
        (AttemptStatus.EXPIRED, AttemptStatus.PAID, True),
        (AttemptStatus.CREATING, AttemptStatus.PENDING, True),
        (AttemptStatus.PENDING, AttemptStatus.CREATING, False),
    ],
)
def test_attempt_transitions_follow_one_table(
    source: AttemptStatus, target: AttemptStatus, allowed: bool
) -> None:
    assert can_move(source, target) is allowed


def test_only_open_or_expired_attempts_can_still_be_paid() -> None:
    assert set(PAYABLE_ATTEMPT_STATUSES) == {
        AttemptStatus.CREATING,
        AttemptStatus.PENDING,
        AttemptStatus.RECONCILING,
        AttemptStatus.EXPIRED,
    }
