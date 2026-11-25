import json
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from typing import Any

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response

from tappy.platform.config import Settings
from tappy.platform.database import Database
from tappy.sales.jobs import JobPolicy, JobRunner
from tests.payments.pey_support import CREATED, FakePey
from tests.payments.webhook_support import Delivery, deliver, settings_for
from tests.sales.support import (
    AMOUNT,
    IDEMPOTENCY_HEADER,
    OPERATOR_A,
    RECEIVER_A,
    bearer,
    create_sale,
    ready_merchant,
    start_client,
)
from tests.support import MovableClock, build_settings, scalar

START = datetime(2026, 11, 25, 12, 0, tzinfo=UTC)
WINDOW = timedelta(seconds=360)
PAID_AT = 1795000000


class SequentialPey(FakePey):
    def __init__(self) -> None:
        super().__init__()
        self.issued = 0

    def handle(self, request: Any) -> Response:
        if request.method == "POST":
            self.issued += 1
            self.body = {**CREATED, "id": f"QR{self.issued:08d}"}
        return super().handle(request)


@pytest.fixture
def clock() -> MovableClock:
    return MovableClock(START)


@pytest.fixture
def fake() -> SequentialPey:
    return SequentialPey()


def expiring_settings(database_url: str) -> Settings:
    return Settings.model_validate(
        {**settings_for(database_url).model_dump(), "qr_expiration_seconds": 360}
    )


@pytest.fixture
def client(
    migrated_database_url: str, fake: SequentialPey, clock: MovableClock
) -> Iterator[TestClient]:
    settings = expiring_settings(migrated_database_url)
    with start_client(settings, migrated_database_url, fake.provider(), clock) as started:
        yield started


def request_qr(client: TestClient, headers: dict[str, str], sale: dict[str, Any]) -> Any:
    return client.post(
        f"/sales/{sale['id']}/attempts",
        json={"method": "qr"},
        headers={**headers, IDEMPOTENCY_HEADER: str(uuid.uuid4())},
    ).json()


def follow(client: TestClient, headers: dict[str, str], sale: dict[str, Any]) -> dict[str, Any]:
    read: dict[str, Any] = client.get(f"/sales/{sale['id']}", headers=headers).json()
    return read


def pay(
    client: TestClient,
    attempt: dict[str, Any],
    transaction_id: str,
    clock: MovableClock,
    message_id: str | None = None,
) -> int:
    event = {
        "type": "codi.qr.payment_received",
        "amount": AMOUNT / 100,
        "bankAccountId": RECEIVER_A["provider_account_id"],
        "codiQrId": attempt["provider_request_id"],
        "datePaid": PAID_AT,
        "transactionId": transaction_id,
        "metadata": {"tappy_attempt_id": attempt["id"]},
    }
    body = json.dumps(event, separators=(",", ":")).encode()
    signed = Delivery(
        message_id=message_id or f"msg_{transaction_id.lower()}",
        timestamp=int(clock.now().timestamp()),
    )
    return deliver(client, body, signed).status_code


def retry_after_expiry(
    client: TestClient, database_url: str, clock: MovableClock, fake: SequentialPey
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, str]]:
    merchant_a = ready_merchant(client, database_url, "Tienda Demo A", OPERATOR_A)
    operator_a = bearer(client, OPERATOR_A)
    sale = create_sale(client, operator_a, merchant_a, amount_cents=AMOUNT).json()
    old = request_qr(client, operator_a, sale)
    clock.advance(WINDOW)
    database = Database.from_settings(build_settings(database_url=database_url))
    try:
        fake.pages = [(200, {"items": [], "nextToken": None})]
        policy = JobPolicy.from_settings(expiring_settings(database_url))
        JobRunner(database, fake.provider(), "test", policy, clock).run()
    finally:
        database.dispose()
    new = request_qr(client, operator_a, sale)
    return sale, old, new, operator_a


def attempt_states(read: dict[str, Any]) -> list[tuple[str, str]]:
    return [(item["status"], item["next_action"]) for item in read["attempts"]]


def test_an_authentic_payment_to_the_old_expired_attempt_covers_the_sale(
    client: TestClient, migrated_database_url: str, clock: MovableClock, fake: SequentialPey
) -> None:
    sale, old, _, operator_a = retry_after_expiry(client, migrated_database_url, clock, fake)

    delivered = pay(client, old, "TX-OLD", clock)
    read = follow(client, operator_a, sale)

    assert delivered == HTTPStatus.NO_CONTENT
    assert read["status"] == "paid"
    assert read["covered"] is True
    assert read["confirmed_amount_cents"] == AMOUNT
    assert [item["provider_transaction_id"] for item in read["transfers"]] == ["TX-OLD"]
    assert read["exceptions"] == []


def test_the_newer_presentation_is_withdrawn_without_promising_cancellation(
    client: TestClient, migrated_database_url: str, clock: MovableClock, fake: SequentialPey
) -> None:
    sale, old, _, operator_a = retry_after_expiry(client, migrated_database_url, clock, fake)

    pay(client, old, "TX-OLD", clock)
    read = follow(client, operator_a, sale)

    assert attempt_states(read) == [("paid", "none"), ("pending", "hide_qr")]
    assert read["attempts"][1]["withdrawn_at"] is not None
    assert read["attempts"][1]["failure_code"] is None
    assert "cancel" not in json.dumps(read).lower()


def test_repeating_the_old_payment_never_duplicates_the_money(
    client: TestClient, migrated_database_url: str, clock: MovableClock, fake: SequentialPey
) -> None:
    sale, old, _, operator_a = retry_after_expiry(client, migrated_database_url, clock, fake)

    pay(client, old, "TX-OLD", clock, "msg_first")
    pay(client, old, "TX-OLD", clock, "msg_redelivered")
    read = follow(client, operator_a, sale)

    assert read["confirmed_amount_cents"] == AMOUNT
    assert len(read["transfers"]) == 1
    assert read["status"] == "paid"


def test_a_second_distinct_transfer_is_kept_and_opens_a_double_reception(
    client: TestClient, migrated_database_url: str, clock: MovableClock, fake: SequentialPey
) -> None:
    sale, old, new, operator_a = retry_after_expiry(client, migrated_database_url, clock, fake)

    pay(client, old, "TX-OLD", clock)
    pay(client, new, "TX-NEW", clock)
    read = follow(client, operator_a, sale)

    assert read["confirmed_amount_cents"] == 2 * AMOUNT
    assert read["status"] == "review"
    assert read["covered"] is True
    assert sorted(item["provider_transaction_id"] for item in read["transfers"]) == [
        "TX-NEW",
        "TX-OLD",
    ]
    assert attempt_states(read) == [("paid", "none"), ("paid", "none")]
    incident = read["exceptions"][0]
    assert [item["reason"] for item in read["exceptions"]] == ["double_reception"]
    assert (incident["expected_amount_cents"], incident["received_amount_cents"]) == (
        AMOUNT,
        AMOUNT,
    )
    assert scalar(migrated_database_url, "SELECT count(*) FROM sales") == 1


def test_the_same_qr_paid_twice_keeps_both_transfers(
    client: TestClient, migrated_database_url: str, clock: MovableClock
) -> None:
    merchant_a = ready_merchant(client, migrated_database_url, "Tienda Demo A", OPERATOR_A)
    operator_a = bearer(client, OPERATOR_A)
    sale = create_sale(client, operator_a, merchant_a, amount_cents=AMOUNT).json()
    attempt = request_qr(client, operator_a, sale)

    pay(client, attempt, "TX-FIRST", clock)
    pay(client, attempt, "TX-SECOND", clock)
    read = follow(client, operator_a, sale)

    assert read["confirmed_amount_cents"] == 2 * AMOUNT
    assert (read["status"], read["covered"]) == ("review", True)
    assert [item["reason"] for item in read["exceptions"]] == ["double_reception"]


def test_an_exact_payment_after_a_short_one_is_kept_and_covers_the_sale_in_review(
    client: TestClient, migrated_database_url: str, clock: MovableClock
) -> None:
    merchant_a = ready_merchant(client, migrated_database_url, "Tienda Demo A", OPERATOR_A)
    operator_a = bearer(client, OPERATOR_A)
    sale = create_sale(client, operator_a, merchant_a, amount_cents=AMOUNT).json()
    attempt = request_qr(client, operator_a, sale)
    short = {
        "type": "codi.qr.payment_received",
        "amount": (AMOUNT - 5000) / 100,
        "bankAccountId": RECEIVER_A["provider_account_id"],
        "codiQrId": attempt["provider_request_id"],
        "datePaid": PAID_AT,
        "transactionId": "TX-SHORT",
        "metadata": {"tappy_attempt_id": attempt["id"]},
    }
    body = json.dumps(short, separators=(",", ":")).encode()
    deliver(client, body, Delivery("msg_short", int(clock.now().timestamp())))

    pay(client, attempt, "TX-EXACT", clock)
    read = follow(client, operator_a, sale)

    assert read["confirmed_amount_cents"] == 2 * AMOUNT - 5000
    assert (read["status"], read["covered"]) == ("review", True)
    assert read["attempts"][0]["status"] == "paid"
    assert sorted(item["reason"] for item in read["exceptions"]) == [
        "amount_mismatch",
        "double_reception",
    ]
