import uuid
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from typing import Any

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response

from tappy.payments.provider import QrProvider
from tappy.platform.config import Settings
from tappy.platform.database import Database
from tappy.sales.attempts import AttemptRequest, reserve_attempt
from tappy.sales.jobs import JobPolicy, JobRunner
from tappy.sales.models import AttemptMethod
from tappy.sales.reconciliation import reconcile_attempt
from tests.payments.pey_support import CREATED, FakePey
from tests.payments.webhook_support import settings_for
from tests.sales.support import (
    AMOUNT,
    IDEMPOTENCY_HEADER,
    OPERATOR_A,
    actor_of,
    bearer,
    create_sale,
    ready_merchant,
    start_client,
)
from tests.support import (
    MovableClock,
    build_settings,
    execute,
    scalar,
    wait_until_blocked_on_a_lock,
)

START = datetime(2026, 11, 25, 12, 0, tzinfo=UTC)
WINDOW = timedelta(seconds=360)
UNVERIFIED = "The previous attempt expired; verify it before creating another"
ACTIVE = "The sale already has an active payment attempt"


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


def open_sale(client: TestClient, database_url: str) -> tuple[dict[str, Any], dict[str, str]]:
    merchant_a = ready_merchant(client, database_url, "Tienda Demo A", OPERATOR_A)
    operator_a = bearer(client, OPERATOR_A)
    return create_sale(client, operator_a, merchant_a, amount_cents=AMOUNT).json(), operator_a


def request_qr(
    client: TestClient, headers: dict[str, str], sale: dict[str, Any], key: str | None = None
) -> Response:
    return client.post(
        f"/sales/{sale['id']}/attempts",
        json={"method": "qr"},
        headers={**headers, IDEMPOTENCY_HEADER: key or str(uuid.uuid4())},
    )


def follow(client: TestClient, headers: dict[str, str], sale: dict[str, Any]) -> dict[str, Any]:
    read: dict[str, Any] = client.get(f"/sales/{sale['id']}", headers=headers).json()
    return read


def run_batch(database_url: str, provider: QrProvider, clock: MovableClock) -> Any:
    database = Database.from_settings(build_settings(database_url=database_url))
    try:
        policy = JobPolicy.from_settings(expiring_settings(database_url))
        return JobRunner(database, provider, "test", policy, clock).run()
    finally:
        database.dispose()


def expired_and_verified(
    client: TestClient, database_url: str, clock: MovableClock, fake: SequentialPey
) -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
    sale, operator_a = open_sale(client, database_url)
    first = request_qr(client, operator_a, sale).json()
    clock.advance(WINDOW)
    fake.pages = [(200, {"items": [], "nextToken": None})]
    run_batch(database_url, fake.provider(), clock)
    return sale, first, operator_a


def test_a_verified_expired_attempt_allows_a_linked_retry_on_the_same_sale(
    client: TestClient, migrated_database_url: str, clock: MovableClock, fake: SequentialPey
) -> None:
    sale, first, operator_a = expired_and_verified(client, migrated_database_url, clock, fake)
    verified = follow(client, operator_a, sale)["attempts"][0]

    retried = request_qr(client, operator_a, sale)
    read = follow(client, operator_a, sale)

    assert verified["next_action"] == "new_attempt"
    assert retried.status_code == HTTPStatus.CREATED
    retry = retried.json()
    assert retry["sale_id"] == sale["id"]
    assert retry["sale_reference"] == sale["reference"]
    assert retry["previous_attempt_id"] == first["id"]
    assert retry["late_payment_possible"] is True
    assert retry["provider_request_id"] != first["provider_request_id"]
    assert retry["status"] == "pending"
    assert read["amount_cents"] == AMOUNT
    assert read["status"] == "open"
    assert [(item["status"], item["verified_at"] is not None) for item in read["attempts"]] == [
        ("expired", True),
        ("pending", False),
    ]
    assert scalar(migrated_database_url, "SELECT count(*) FROM sales") == 1


def test_repeating_a_retry_returns_the_same_attempt(
    client: TestClient, migrated_database_url: str, clock: MovableClock, fake: SequentialPey
) -> None:
    sale, _, operator_a = expired_and_verified(client, migrated_database_url, clock, fake)
    key = str(uuid.uuid4())

    first = request_qr(client, operator_a, sale, key)
    repeated = request_qr(client, operator_a, sale, key)

    assert repeated.status_code == HTTPStatus.OK
    assert repeated.json()["id"] == first.json()["id"]
    assert scalar(migrated_database_url, "SELECT count(*) FROM payment_attempts") == len(
        ["expired", "retry"]
    )


def test_an_expired_attempt_needs_verification_before_a_retry(
    client: TestClient, migrated_database_url: str, clock: MovableClock
) -> None:
    sale, operator_a = open_sale(client, migrated_database_url)
    request_qr(client, operator_a, sale)
    clock.advance(WINDOW)
    assert follow(client, operator_a, sale)["attempts"][0]["status"] == "expired"

    blocked = request_qr(client, operator_a, sale)

    assert blocked.status_code == HTTPStatus.CONFLICT
    assert blocked.json() == {"detail": UNVERIFIED}
    assert scalar(migrated_database_url, "SELECT count(*) FROM payment_attempts") == 1


def test_an_uncertain_verification_keeps_the_retry_blocked(
    client: TestClient, migrated_database_url: str, clock: MovableClock
) -> None:
    sale, operator_a = open_sale(client, migrated_database_url)
    request_qr(client, operator_a, sale)
    clock.advance(WINDOW)
    run_batch(migrated_database_url, FakePey(pages=[(500, {})]).provider(), clock)

    blocked = request_qr(client, operator_a, sale)

    assert blocked.status_code == HTTPStatus.CONFLICT
    assert blocked.json() == {"detail": UNVERIFIED}
    assert follow(client, operator_a, sale)["attempts"][0]["verified_at"] is None


@pytest.mark.parametrize("status", ["creating", "pending", "reconciling"])
def test_an_active_or_uncertain_attempt_blocks_a_retry(
    client: TestClient, migrated_database_url: str, status: str
) -> None:
    sale, operator_a = open_sale(client, migrated_database_url)
    request_qr(client, operator_a, sale)
    execute(migrated_database_url, "UPDATE payment_attempts SET status = :s", {"s": status})

    blocked = request_qr(client, operator_a, sale)

    assert blocked.status_code == HTTPStatus.CONFLICT
    assert blocked.json() == {"detail": ACTIVE}
    assert scalar(migrated_database_url, "SELECT count(*) FROM payment_attempts") == 1


def test_a_failed_attempt_allows_a_retry_without_a_late_payment_warning(
    client: TestClient, migrated_database_url: str
) -> None:
    sale, operator_a = open_sale(client, migrated_database_url)
    first = request_qr(client, operator_a, sale).json()
    execute(
        migrated_database_url,
        "UPDATE payment_attempts SET status = 'failed', provider_request_id = NULL, "
        "qr_payload = NULL, failure_code = 'INVALID_PARAMETERS'",
    )

    retried = request_qr(client, operator_a, sale)

    assert retried.status_code == HTTPStatus.CREATED
    assert retried.json()["previous_attempt_id"] == first["id"]
    assert retried.json()["late_payment_possible"] is False


def test_a_late_payment_found_by_the_verification_needs_no_retry(
    client: TestClient, migrated_database_url: str, clock: MovableClock
) -> None:
    sale, operator_a = open_sale(client, migrated_database_url)
    request_qr(client, operator_a, sale)
    clock.advance(WINDOW)
    paid = {
        "id": "01M3QR8H0RH0XBCKYYD242YXNV",
        "status": "PAID",
        "amount": AMOUNT / 100,
        "datePaid": 1795000000,
    }
    summary = run_batch(
        migrated_database_url,
        FakePey(pages=[(200, {"items": [paid], "nextToken": None})]).provider(),
        clock,
    )

    read = follow(client, operator_a, sale)
    retried = request_qr(client, operator_a, sale)

    assert (summary.expired, summary.confirmed) == (1, 1)
    assert read["status"] == "paid"
    assert retried.status_code == HTTPStatus.CONFLICT


def test_concurrent_retries_leave_a_single_new_attempt(
    client: TestClient, migrated_database_url: str, clock: MovableClock, fake: SequentialPey
) -> None:
    sale, _, operator_a = expired_and_verified(client, migrated_database_url, clock, fake)
    database = Database.from_settings(build_settings(database_url=migrated_database_url))
    try:
        with database.session_factory() as racing, racing.begin():
            request = AttemptRequest(
                actor_of(client, operator_a),
                uuid.UUID(sale["id"]),
                AttemptMethod.QR,
                str(uuid.uuid4()),
            )
            held = reserve_attempt(racing, request, fake.provider(), clock.now())
            with ThreadPoolExecutor(max_workers=1) as pool:
                other = pool.submit(request_qr, client, operator_a, sale)
                wait_until_blocked_on_a_lock(migrated_database_url)
                racing.commit()
                response = other.result(timeout=10)
    finally:
        database.dispose()

    read = follow(client, operator_a, sale)
    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json() == {"detail": ACTIVE}
    assert [item["id"] for item in read["attempts"]][1:] == [held.attempt.id]
    assert held.attempt.previous_attempt_id == read["attempts"][0]["id"]
    assert scalar(migrated_database_url, "SELECT count(*) FROM sales") == 1


def test_the_late_payment_warning_covers_every_earlier_qr(
    client: TestClient, migrated_database_url: str, clock: MovableClock, fake: SequentialPey
) -> None:
    sale, _, operator_a = expired_and_verified(client, migrated_database_url, clock, fake)
    second = request_qr(client, operator_a, sale).json()
    execute(
        migrated_database_url,
        "UPDATE payment_attempts SET status = 'failed', provider_request_id = NULL, "
        "qr_payload = NULL, failure_code = 'INVALID_PARAMETERS' WHERE id = :id",
        {"id": second["id"]},
    )

    third = request_qr(client, operator_a, sale).json()

    assert third["previous_attempt_id"] == second["id"]
    assert third["late_payment_possible"] is True


class ExpiringDuringQuery(FakePey):
    def __init__(self, database_url: str) -> None:
        super().__init__(pages=[(200, {"items": [], "nextToken": None})])
        self.database_url = database_url

    def handle(self, request: Any) -> Response:
        if request.method == "GET":
            execute(self.database_url, "UPDATE payment_attempts SET status = 'expired'")
        return super().handle(request)


def test_a_query_made_before_the_expiration_never_verifies_it(
    client: TestClient, migrated_database_url: str, clock: MovableClock
) -> None:
    sale, operator_a = open_sale(client, migrated_database_url)
    first = request_qr(client, operator_a, sale).json()
    database = Database.from_settings(build_settings(database_url=migrated_database_url))
    try:
        provider = ExpiringDuringQuery(migrated_database_url).provider()
        report = reconcile_attempt(database, uuid.UUID(first["id"]), provider, "test", clock)
    finally:
        database.dispose()

    assert report.result.value == "no_evidence"
    assert follow(client, operator_a, sale)["attempts"][0]["verified_at"] is None
    assert request_qr(client, operator_a, sale).json() == {"detail": UNVERIFIED}
