import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response
from sqlalchemy import create_engine, text

from tappy.payments.simulator import SimulatedQrProvider
from tappy.platform.database import Database
from tappy.sales.attempts import AttemptRequest, reserve_attempt
from tappy.sales.models import AttemptMethod
from tests.sales.support import (
    ADMIN,
    AMOUNT,
    BLOCKED_DISABLED,
    IDEMPOTENCY_HEADER,
    OPERATOR_A,
    OPERATOR_B,
    actor_of,
    app_client,
    bearer,
    configure,
    create_sale,
    ready_merchant,
    start_client,
)
from tests.support import build_settings, execute, scalar, wait_until_blocked_on_a_lock

ACTIVE_CONFLICT = "The sale already has an active payment attempt"
NOT_OPEN = "The sale is not open"
RESERVED_AT = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)


def reserve(
    client: TestClient,
    headers: dict[str, str],
    sale_id: str,
    method: str = "qr",
    key: str | None = None,
) -> Response:
    return client.post(
        f"/sales/{sale_id}/attempts",
        json={"method": method},
        headers={**headers, IDEMPOTENCY_HEADER: key or str(uuid.uuid4())},
    )


def open_sale(client: TestClient, database_url: str) -> tuple[str, dict[str, str]]:
    merchant_a = ready_merchant(client, database_url, "Tienda Demo A", OPERATOR_A)
    operator_a = bearer(client, OPERATOR_A)
    sale = create_sale(client, operator_a, merchant_a, amount_cents=AMOUNT).json()
    return sale["id"], operator_a


def attempt_count(database_url: str) -> object:
    return scalar(database_url, "SELECT count(*) FROM payment_attempts")


def test_reserving_an_attempt_leaves_it_creating_on_the_sale(
    client: TestClient, migrated_database_url: str
) -> None:
    sale_id, operator_a = open_sale(client, migrated_database_url)

    reserved = reserve(client, operator_a, sale_id, method="phone")
    sale = client.get(f"/sales/{sale_id}", headers=operator_a).json()

    assert reserved.status_code == HTTPStatus.CREATED
    attempt = reserved.json()
    assert attempt == {
        "id": attempt["id"],
        "sale_id": sale_id,
        "sale_reference": sale["reference"],
        "method": "phone",
        "status": "creating",
        "simulated": True,
        "provider_request_id": None,
        "qr_payload": None,
        "failure_code": None,
        "created_at": attempt["created_at"],
    }
    assert sale["status"] == "open"
    assert sale["attempts"] == [attempt]
    assert attempt_count(migrated_database_url) == 1


def test_repeating_a_reservation_returns_the_same_attempt(
    client: TestClient, migrated_database_url: str
) -> None:
    sale_id, operator_a = open_sale(client, migrated_database_url)
    key = str(uuid.uuid4())

    first = reserve(client, operator_a, sale_id, key=key)
    repeated = reserve(client, operator_a, sale_id, key=key)
    other_method = reserve(client, operator_a, sale_id, method="link", key=key)

    assert repeated.status_code == HTTPStatus.OK
    assert repeated.json() == first.json()
    assert other_method.status_code == HTTPStatus.CONFLICT
    assert attempt_count(migrated_database_url) == 1


@pytest.mark.parametrize("method", ["qr", "phone", "link"])
def test_second_attempt_with_another_key_or_channel_conflicts(
    client: TestClient, migrated_database_url: str, method: str
) -> None:
    sale_id, operator_a = open_sale(client, migrated_database_url)
    first = reserve(client, operator_a, sale_id)

    second = reserve(client, operator_a, sale_id, method=method)

    assert second.status_code == HTTPStatus.CONFLICT
    assert second.json() == {"detail": ACTIVE_CONFLICT}
    assert attempt_count(migrated_database_url) == 1
    sale = client.get(f"/sales/{sale_id}", headers=operator_a).json()
    assert sale["attempts"] == [first.json()]


@pytest.mark.parametrize("status", ["expired", "failed"])
def test_finished_attempts_allow_a_new_reservation(
    client: TestClient, migrated_database_url: str, status: str
) -> None:
    sale_id, operator_a = open_sale(client, migrated_database_url)
    reserve(client, operator_a, sale_id)
    execute(migrated_database_url, "UPDATE payment_attempts SET status = :s", {"s": status})

    retried = reserve(client, operator_a, sale_id)

    assert retried.status_code == HTTPStatus.CREATED
    assert attempt_count(migrated_database_url) == len(["finished", "retried"])


@pytest.mark.parametrize("status", ["pending", "reconciling"])
def test_pending_and_reconciling_attempts_stay_active(
    client: TestClient, migrated_database_url: str, status: str
) -> None:
    sale_id, operator_a = open_sale(client, migrated_database_url)
    reserve(client, operator_a, sale_id)
    execute(migrated_database_url, "UPDATE payment_attempts SET status = :s", {"s": status})

    second = reserve(client, operator_a, sale_id)

    assert second.status_code == HTTPStatus.CONFLICT
    assert attempt_count(migrated_database_url) == 1


def test_database_allows_only_one_active_attempt_per_sale(
    client: TestClient, migrated_database_url: str
) -> None:
    sale_id, operator_a = open_sale(client, migrated_database_url)
    reserve(client, operator_a, sale_id)

    with pytest.raises(Exception, match="uq_payment_attempts_active_sale"):
        execute(
            migrated_database_url,
            "INSERT INTO payment_attempts (id, sale_id, created_by, method, status, provider, "
            "simulated, receiver_account, created_at, updated_at, version) "
            "SELECT gen_random_uuid(), sale_id, created_by, 'link', 'pending', provider, "
            "simulated, receiver_account, created_at, updated_at, 1 FROM payment_attempts",
        )


def test_reservation_requires_an_open_sale_and_an_enabled_receiver(
    client: TestClient, migrated_database_url: str
) -> None:
    sale_id, operator_a = open_sale(client, migrated_database_url)
    merchant_id = client.get(f"/sales/{sale_id}", headers=operator_a).json()["merchant_id"]

    configure(client, merchant_id, enabled=False)
    blocked = reserve(client, operator_a, sale_id)
    configure(client, merchant_id)
    execute(migrated_database_url, "UPDATE sales SET status = 'paid'")
    closed = reserve(client, operator_a, sale_id)

    assert blocked.status_code == HTTPStatus.CONFLICT
    assert blocked.json() == {"detail": BLOCKED_DISABLED}
    assert closed.status_code == HTTPStatus.CONFLICT
    assert closed.json() == {"detail": NOT_OPEN}
    assert attempt_count(migrated_database_url) == 0


def test_reservation_is_limited_to_operators_of_the_sale(
    client: TestClient, migrated_database_url: str
) -> None:
    sale_id, _ = open_sale(client, migrated_database_url)
    ready_merchant(client, migrated_database_url, "Tienda Demo B", OPERATOR_B)

    foreign = reserve(client, bearer(client, OPERATOR_B), sale_id)
    as_admin = reserve(client, bearer(client, ADMIN), sale_id)
    unknown = reserve(client, bearer(client, OPERATOR_A), str(uuid.uuid4()))
    anonymous = reserve(client, {}, sale_id)

    assert foreign.status_code == HTTPStatus.NOT_FOUND
    assert foreign.json() == {"detail": "Sale not found"}
    assert as_admin.status_code == HTTPStatus.FORBIDDEN
    assert unknown.status_code == HTTPStatus.NOT_FOUND
    assert anonymous.status_code == HTTPStatus.UNAUTHORIZED
    assert attempt_count(migrated_database_url) == 0


@pytest.mark.parametrize(
    ("body", "headers"),
    [
        ({"method": "nfc"}, {}),
        ({}, {}),
        ({"method": "qr", "receiver_id": "x"}, {}),
        ({"method": "qr", "status": "pending"}, {}),
        ({"method": "qr"}, {IDEMPOTENCY_HEADER: "short"}),
    ],
)
def test_malformed_reservations_are_rejected(
    client: TestClient,
    migrated_database_url: str,
    body: dict[str, object],
    headers: dict[str, str],
) -> None:
    sale_id, operator_a = open_sale(client, migrated_database_url)

    response = client.post(
        f"/sales/{sale_id}/attempts",
        json=body,
        headers={**operator_a, IDEMPOTENCY_HEADER: str(uuid.uuid4()), **headers},
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
    assert attempt_count(migrated_database_url) == 0


def test_concurrent_reservations_leave_a_single_active_attempt(
    client: TestClient, migrated_database_url: str
) -> None:
    sale_id, operator_a = open_sale(client, migrated_database_url)
    database = Database.from_settings(build_settings(database_url=migrated_database_url))
    try:
        with database.session_factory() as racing, racing.begin():
            request = AttemptRequest(
                actor_of(client, operator_a),
                uuid.UUID(sale_id),
                AttemptMethod.QR,
                str(uuid.uuid4()),
            )
            held = reserve_attempt(racing, request, SimulatedQrProvider(), RESERVED_AT)
            with ThreadPoolExecutor(max_workers=1) as pool:
                attempt = pool.submit(reserve, client, operator_a, sale_id, "phone")
                wait_until_blocked_on_a_lock(migrated_database_url)
                racing.commit()
                response = attempt.result(timeout=10)
    finally:
        database.dispose()

    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json() == {"detail": ACTIVE_CONFLICT}
    sale = client.get(f"/sales/{sale_id}", headers=operator_a).json()
    assert [item["id"] for item in sale["attempts"]] == [held.attempt.id]


def test_interrupted_reservation_stays_recoverable_after_a_restart(
    migrated_database_url: str,
) -> None:
    settings = build_settings(database_url=migrated_database_url)
    with start_client(settings, migrated_database_url) as first:
        sale_id, operator_a = open_sale(first, migrated_database_url)

        key = str(uuid.uuid4())
        reserved = reserve(first, operator_a, sale_id, method="phone", key=key).json()

    with app_client(settings) as restarted:
        retried = reserve(restarted, operator_a, sale_id, method="phone", key=key)
        sale = restarted.get(f"/sales/{sale_id}", headers=operator_a).json()

    assert retried.status_code == HTTPStatus.OK
    assert retried.json() == reserved
    assert sale["attempts"] == [reserved]
    assert sale["attempts"][0]["status"] == "creating"


def test_reservation_interrupted_before_commit_leaves_no_trace(
    client: TestClient, migrated_database_url: str
) -> None:
    sale_id, operator_a = open_sale(client, migrated_database_url)
    key = str(uuid.uuid4())
    database = Database.from_settings(build_settings(database_url=migrated_database_url))
    try:
        with database.session_factory() as interrupted, interrupted.begin():
            request = AttemptRequest(
                actor_of(client, operator_a), uuid.UUID(sale_id), AttemptMethod.QR, key
            )
            reserve_attempt(interrupted, request, SimulatedQrProvider(), RESERVED_AT)
            interrupted.rollback()
    finally:
        database.dispose()

    retried = reserve(client, operator_a, sale_id, key=key)

    assert retried.status_code == HTTPStatus.CREATED
    assert attempt_count(migrated_database_url) == 1


def test_reservation_waits_for_a_concurrent_status_change_and_honours_it(
    client: TestClient, migrated_database_url: str
) -> None:
    sale_id, operator_a = open_sale(client, migrated_database_url)
    engine = create_engine(migrated_database_url)
    try:
        with engine.connect() as racing, racing.begin() as transaction:
            racing.execute(text("UPDATE sales SET status = 'paid'"))
            with ThreadPoolExecutor(max_workers=1) as pool:
                attempt = pool.submit(reserve, client, operator_a, sale_id)
                wait_until_blocked_on_a_lock(migrated_database_url)
                transaction.commit()
                response = attempt.result(timeout=10)
    finally:
        engine.dispose()

    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json() == {"detail": NOT_OPEN}
    assert attempt_count(migrated_database_url) == 0
