import json
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from http import HTTPStatus
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tappy.payments.factory import provider_from
from tappy.payments.provider import QrOrder
from tappy.platform.config import Settings
from tappy.platform.database import Database
from tappy.sales.jobs import JobPolicy, JobRunner
from tests.payments.pey_support import FakePey
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
from tests.support import MovableClock, build_settings, execute, scalar

START = datetime(2026, 11, 25, 12, 0, tzinfo=UTC)
WINDOW = timedelta(seconds=360)
PAID_AT = 1795000000


def expiring_settings(database_url: str) -> Settings:
    return Settings.model_validate(
        {**settings_for(database_url).model_dump(), "qr_expiration_seconds": 360}
    )


@pytest.fixture
def clock() -> MovableClock:
    return MovableClock(START)


@pytest.fixture
def fake() -> FakePey:
    return FakePey()


@pytest.fixture
def client(migrated_database_url: str, fake: FakePey, clock: MovableClock) -> Iterator[TestClient]:
    settings = expiring_settings(migrated_database_url)
    with start_client(settings, migrated_database_url, fake.provider(), clock) as started:
        yield started


def pending_qr(
    client: TestClient, database_url: str
) -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
    merchant_a = ready_merchant(client, database_url, "Tienda Demo A", OPERATOR_A)
    operator_a = bearer(client, OPERATOR_A)
    sale = create_sale(client, operator_a, merchant_a, amount_cents=AMOUNT).json()
    attempt = client.post(
        f"/sales/{sale['id']}/attempts",
        json={"method": "qr"},
        headers={**operator_a, IDEMPOTENCY_HEADER: str(uuid.uuid4())},
    ).json()
    return sale, attempt, operator_a


def follow(client: TestClient, headers: dict[str, str], sale: dict[str, Any]) -> dict[str, Any]:
    read: dict[str, Any] = client.get(f"/sales/{sale['id']}", headers=headers).json()
    return read


def pay(client: TestClient, attempt: dict[str, Any], message_id: str, clock: MovableClock) -> int:
    event = {
        "type": "codi.qr.payment_received",
        "amount": AMOUNT / 100,
        "bankAccountId": RECEIVER_A["provider_account_id"],
        "codiQrId": attempt["provider_request_id"],
        "datePaid": PAID_AT,
        "transactionId": f"TX-{message_id.upper()}",
        "metadata": {"tappy_attempt_id": attempt["id"]},
    }
    body = json.dumps(event, separators=(",", ":")).encode()
    signed = Delivery(message_id=message_id, timestamp=int(clock.now().timestamp()))
    return deliver(client, body, signed).status_code


def test_the_qr_window_is_sent_to_pey_and_shown_by_the_server(
    client: TestClient, migrated_database_url: str, fake: FakePey
) -> None:
    sale, attempt, operator_a = pending_qr(client, migrated_database_url)
    read = follow(client, operator_a, sale)

    sent = json.loads(fake.requests[0].content)
    assert sent["expiration"] == WINDOW.total_seconds()
    assert attempt["status"] == "pending"
    assert attempt["expires_at"] == (START + WINDOW).isoformat().replace("+00:00", "Z")
    assert attempt["next_action"] == "show_qr"
    assert read["attempts"][0]["expires_at"] == attempt["expires_at"]


def test_a_reached_server_expiration_shows_expired_and_a_safe_next_action(
    client: TestClient, migrated_database_url: str, clock: MovableClock
) -> None:
    sale, _, operator_a = pending_qr(client, migrated_database_url)

    clock.advance(WINDOW)
    read = follow(client, operator_a, sale)

    attempt = read["attempts"][0]
    assert attempt["status"] == "expired"
    assert attempt["next_action"] == "verify_before_retry"
    assert attempt["failure_code"] is None
    assert read["status"] == "open"
    assert read["confirmed_amount_cents"] == 0
    assert "cancel" not in json.dumps(read).lower()
    assert scalar(migrated_database_url, "SELECT status FROM payment_attempts") == "expired"


@pytest.mark.parametrize("skew", [timedelta(hours=2), -timedelta(hours=2)], ids=["ahead", "behind"])
def test_the_client_clock_never_changes_the_state(
    client: TestClient, migrated_database_url: str, clock: MovableClock, skew: timedelta
) -> None:
    sale, _, operator_a = pending_qr(client, migrated_database_url)
    clock.advance(WINDOW - timedelta(seconds=1))
    client_time = START + skew

    read = client.get(
        f"/sales/{sale['id']}",
        headers={**operator_a, "Date": format_datetime(client_time, usegmt=True)},
        params={"now": client_time.isoformat()},
    ).json()

    assert read["attempts"][0]["status"] == "pending"
    assert read["attempts"][0]["next_action"] == "show_qr"


def test_a_paid_attempt_stays_confirmed_after_its_expiration(
    client: TestClient, migrated_database_url: str, clock: MovableClock
) -> None:
    sale, attempt, operator_a = pending_qr(client, migrated_database_url)
    assert pay(client, attempt, "msg_paid", clock) == HTTPStatus.NO_CONTENT

    clock.advance(WINDOW + timedelta(minutes=1))
    database = Database.from_settings(build_settings(database_url=migrated_database_url))
    try:
        policy = JobPolicy.from_settings(expiring_settings(migrated_database_url))
        summary = JobRunner(database, FakePey().provider(), "test", policy, clock).run()
    finally:
        database.dispose()
    read = follow(client, operator_a, sale)

    assert summary.expired == 0
    assert read["status"] == "paid"
    assert read["attempts"][0]["status"] == "paid"
    assert read["attempts"][0]["next_action"] == "none"
    assert read["confirmed_amount_cents"] == AMOUNT
    assert len(read["transfers"]) == 1


def test_the_batch_expires_pending_attempts_by_the_server_clock(
    client: TestClient, migrated_database_url: str, clock: MovableClock
) -> None:
    pending_qr(client, migrated_database_url)
    database = Database.from_settings(build_settings(database_url=migrated_database_url))
    policy = JobPolicy.from_settings(expiring_settings(migrated_database_url))
    try:
        early = JobRunner(database, FakePey().provider(), "test", policy, clock).run()
        clock.advance(WINDOW)
        verifying = FakePey(pages=[(200, {"items": [], "nextToken": None})]).provider()
        due = JobRunner(database, verifying, "test", policy, clock).run()
    finally:
        database.dispose()

    assert (early.expired, due.expired, due.verified) == (0, 1, 1)
    assert scalar(migrated_database_url, "SELECT status FROM payment_attempts") == "expired"


def test_an_authentic_late_payment_still_confirms_an_expired_attempt(
    client: TestClient, migrated_database_url: str, clock: MovableClock
) -> None:
    sale, attempt, operator_a = pending_qr(client, migrated_database_url)
    clock.advance(WINDOW)
    assert follow(client, operator_a, sale)["attempts"][0]["status"] == "expired"

    delivered = pay(client, attempt, "msg_late", clock)
    read = follow(client, operator_a, sale)

    assert delivered == HTTPStatus.NO_CONTENT
    assert read["status"] == "paid"
    assert read["attempts"][0]["status"] == "paid"
    assert read["confirmed_amount_cents"] == AMOUNT


def test_an_uncertain_attempt_is_not_expired_by_its_window(
    client: TestClient, migrated_database_url: str, clock: MovableClock
) -> None:
    sale, _, operator_a = pending_qr(client, migrated_database_url)
    execute(migrated_database_url, "UPDATE payment_attempts SET status = 'reconciling'")
    clock.advance(WINDOW * 2)

    read = follow(client, operator_a, sale)

    assert read["attempts"][0]["status"] == "reconciling"
    assert read["attempts"][0]["next_action"] == "wait_for_verification"


def test_the_qr_window_respects_the_provider_minimum() -> None:
    base = build_settings().model_dump()

    with pytest.raises(ValueError, match="qr_expiration_seconds"):
        Settings.model_validate({**base, "qr_expiration_seconds": 359})

    assert Settings.model_validate(base).qr_expiration_seconds >= WINDOW.total_seconds()


def test_the_simulator_uses_the_same_server_window() -> None:
    settings = Settings.model_validate(
        {**build_settings().model_dump(), "qr_expiration_seconds": 600}
    )
    order = QrOrder(uuid.uuid4(), "MSPE6WGBSK", AMOUNT, None, "bank-account-demo")

    issued = provider_from(settings).create_qr(order)

    assert issued.valid_for == timedelta(seconds=600)
