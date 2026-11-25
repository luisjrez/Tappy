import uuid
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response

from tappy.payments.provider import IssuedQr, QrOrder, QrPayment
from tappy.payments.simulator import SimulatedQrProvider
from tappy.platform.config import Settings
from tappy.platform.database import Database
from tappy.platform.quotas import QuotaPolicy
from tappy.sales.service import SaleRequest, create_sale
from tests.sales.support import (
    AMOUNT,
    DEFAULT_MAXIMUM,
    IDEMPOTENCY_HEADER,
    OPERATOR_A,
    OPERATOR_B,
    actor_of,
    bearer,
    configure,
    create_sale_with_key,
    merchant_of,
    ready_merchant,
    sale_count,
    start_client,
)
from tests.sales.support import create_sale as post_sale
from tests.support import MovableClock, build_settings, scalar, wait_until_blocked_on_a_lock

STARTED_AT = datetime(2026, 11, 25, 12, 0, 10, 250000, tzinfo=UTC)
SALE_QUOTA = 3
ATTEMPT_QUOTA = 2
READ_QUOTA = 5
WAIT_SECONDS = 50
BODY_LIMIT = 2048
RECEIVER_B_ACCOUNT = "bank-account-demo-b"


class CountingProvider(SimulatedQrProvider):
    def __init__(self) -> None:
        super().__init__()
        self.created: list[QrOrder] = []
        self.queried: list[str] = []

    def create_qr(self, order: QrOrder) -> IssuedQr:
        self.created.append(order)
        return super().create_qr(order)

    def qr_payments(self, provider_request_id: str) -> list[QrPayment]:
        self.queried.append(provider_request_id)
        return super().qr_payments(provider_request_id)


def quota_settings(database_url: str, **changes: object) -> Settings:
    limits: dict[str, object] = {
        "sale_creation_quota": SALE_QUOTA,
        "attempt_creation_quota": ATTEMPT_QUOTA,
        "sale_read_quota": READ_QUOTA,
        "quota_window_seconds": 60,
        "api_max_body_bytes": BODY_LIMIT,
    }
    return build_settings(database_url=database_url).model_copy(update={**limits, **changes})


@pytest.fixture
def clock() -> MovableClock:
    return MovableClock(STARTED_AT)


@pytest.fixture
def provider() -> CountingProvider:
    return CountingProvider()


@pytest.fixture
def client(
    migrated_database_url: str, clock: MovableClock, provider: CountingProvider
) -> Iterator[TestClient]:
    settings = quota_settings(migrated_database_url)
    with start_client(settings, migrated_database_url, provider, clock) as client:
        yield client


def assert_quota_exceeded(response: Response, wait: int = WAIT_SECONDS) -> None:
    assert response.status_code == HTTPStatus.TOO_MANY_REQUESTS
    assert response.headers["Retry-After"] == str(wait)
    assert response.json() == {
        "detail": f"Quota exceeded; try again in {wait} seconds",
        "retry_after_seconds": wait,
    }


def request_qr_with_key(
    client: TestClient, headers: dict[str, str], sale_id: str, key: str
) -> Response:
    return client.post(
        f"/sales/{sale_id}/attempts",
        json={"method": "qr"},
        headers={**headers, IDEMPOTENCY_HEADER: key},
    )


def request_qr(client: TestClient, headers: dict[str, str], sale_id: str) -> Response:
    return request_qr_with_key(client, headers, sale_id, str(uuid.uuid4()))


def test_sales_within_the_quota_are_created_and_the_excess_gets_429_with_wait_guidance(
    client: TestClient, migrated_database_url: str, clock: MovableClock
) -> None:
    merchant_a = ready_merchant(client, migrated_database_url, "Tienda Demo A", OPERATOR_A)
    operator_a = bearer(client, OPERATOR_A)

    allowed = [
        post_sale(client, operator_a, merchant_a, amount_cents=AMOUNT) for _ in range(SALE_QUOTA)
    ]
    refused = post_sale(client, operator_a, merchant_a, amount_cents=AMOUNT)
    clock.advance(timedelta(seconds=WAIT_SECONDS - 1))
    still_refused = post_sale(client, operator_a, merchant_a, amount_cents=AMOUNT)
    clock.advance(timedelta(milliseconds=750))
    after_waiting = post_sale(client, operator_a, merchant_a, amount_cents=AMOUNT)

    assert [response.status_code for response in allowed] == [HTTPStatus.CREATED] * SALE_QUOTA
    assert_quota_exceeded(refused)
    assert_quota_exceeded(still_refused, wait=1)
    assert after_waiting.status_code == HTTPStatus.CREATED
    assert sale_count(migrated_database_url) == SALE_QUOTA + 1
    assert scalar(
        migrated_database_url,
        "SELECT array_agg(used) FROM operation_quotas WHERE operation = 'sale_creation'",
    ) == [1]


def test_repeated_requests_replay_without_spending_the_quota(
    client: TestClient, migrated_database_url: str
) -> None:
    merchant_a = ready_merchant(client, migrated_database_url, "Tienda Demo A", OPERATOR_A)
    operator_a = bearer(client, OPERATOR_A)
    key = str(uuid.uuid4())

    first = create_sale_with_key(client, operator_a, merchant_a, key, amount_cents=AMOUNT)
    replays = [
        create_sale_with_key(client, operator_a, merchant_a, key, amount_cents=AMOUNT)
        for _ in range(SALE_QUOTA + 1)
    ]
    others = [
        post_sale(client, operator_a, merchant_a, amount_cents=AMOUNT)
        for _ in range(SALE_QUOTA - 1)
    ]
    refused = post_sale(client, operator_a, merchant_a, amount_cents=AMOUNT)

    assert first.status_code == HTTPStatus.CREATED
    assert {response.status_code for response in replays} == {HTTPStatus.OK}
    assert {response.json()["id"] for response in replays} == {first.json()["id"]}
    assert {response.status_code for response in others} == {HTTPStatus.CREATED}
    assert_quota_exceeded(refused)


def test_each_merchant_has_its_own_quota(client: TestClient, migrated_database_url: str) -> None:
    merchant_a = ready_merchant(client, migrated_database_url, "Tienda Demo A", OPERATOR_A)
    merchant_b = merchant_of(client, migrated_database_url, "Tienda Demo B", OPERATOR_B)
    configure(client, merchant_b, provider_account_id=RECEIVER_B_ACCOUNT)
    operator_a = bearer(client, OPERATOR_A)
    for _ in range(SALE_QUOTA):
        post_sale(client, operator_a, merchant_a, amount_cents=AMOUNT)

    refused = post_sale(client, operator_a, merchant_a, amount_cents=AMOUNT)
    other_merchant = post_sale(client, bearer(client, OPERATOR_B), merchant_b, amount_cents=AMOUNT)

    assert_quota_exceeded(refused)
    assert other_merchant.status_code == HTTPStatus.CREATED


def test_qr_requests_over_the_quota_get_429_without_calling_the_provider(
    client: TestClient, migrated_database_url: str, provider: CountingProvider
) -> None:
    merchant_a = ready_merchant(client, migrated_database_url, "Tienda Demo A", OPERATOR_A)
    operator_a = bearer(client, OPERATOR_A)
    sales = [
        post_sale(client, operator_a, merchant_a, amount_cents=AMOUNT).json()["id"]
        for _ in range(ATTEMPT_QUOTA + 1)
    ]

    allowed = [request_qr(client, operator_a, sale_id) for sale_id in sales[:ATTEMPT_QUOTA]]
    refused = request_qr(client, operator_a, sales[-1])

    assert {response.status_code for response in allowed} == {HTTPStatus.CREATED}
    assert_quota_exceeded(refused)
    assert len(provider.created) == ATTEMPT_QUOTA
    assert scalar(migrated_database_url, "SELECT count(*) FROM payment_attempts") == ATTEMPT_QUOTA
    assert (
        scalar(
            migrated_database_url,
            "SELECT count(*) FROM payment_attempts WHERE sale_id = :sale",
            {"sale": sales[-1]},
        )
        == 0
    )


def test_repeated_qr_requests_replay_without_spending_the_quota_or_calling_the_provider(
    client: TestClient, migrated_database_url: str, provider: CountingProvider
) -> None:
    merchant_a = ready_merchant(client, migrated_database_url, "Tienda Demo A", OPERATOR_A)
    operator_a = bearer(client, OPERATOR_A)
    sales = [
        post_sale(client, operator_a, merchant_a, amount_cents=AMOUNT).json()["id"]
        for _ in range(ATTEMPT_QUOTA + 1)
    ]
    key = str(uuid.uuid4())
    first = request_qr_with_key(client, operator_a, sales[0], key)
    second = request_qr(client, operator_a, sales[1])

    replays = [request_qr_with_key(client, operator_a, sales[0], key) for _ in range(2)]
    refused = request_qr(client, operator_a, sales[2])

    assert {first.status_code, second.status_code} == {HTTPStatus.CREATED}
    assert {response.status_code for response in replays} == {HTTPStatus.OK}
    assert {response.json()["id"] for response in replays} == {first.json()["id"]}
    assert_quota_exceeded(refused)
    assert len(provider.created) == ATTEMPT_QUOTA


def test_a_refused_qr_request_spends_no_quota(
    client: TestClient, migrated_database_url: str, provider: CountingProvider
) -> None:
    merchant_a = ready_merchant(client, migrated_database_url, "Tienda Demo A", OPERATOR_A)
    operator_a = bearer(client, OPERATOR_A)
    sales = [
        post_sale(client, operator_a, merchant_a, amount_cents=AMOUNT).json()["id"]
        for _ in range(ATTEMPT_QUOTA)
    ]
    first = request_qr(client, operator_a, sales[0])

    active = [request_qr(client, operator_a, sales[0]) for _ in range(ATTEMPT_QUOTA)]
    other = request_qr(client, operator_a, sales[1])

    assert first.status_code == HTTPStatus.CREATED
    assert {response.status_code for response in active} == {HTTPStatus.CONFLICT}
    assert other.status_code == HTTPStatus.CREATED
    assert len(provider.created) == ATTEMPT_QUOTA


def test_each_actor_has_a_read_quota_that_does_not_block_others(
    client: TestClient, migrated_database_url: str
) -> None:
    merchant_a = ready_merchant(client, migrated_database_url, "Tienda Demo A", OPERATOR_A)
    operator_a = bearer(client, OPERATOR_A)
    admin = bearer(client, "admin@tappy.example")
    sale_id = post_sale(client, operator_a, merchant_a, amount_cents=AMOUNT).json()["id"]
    reads = [
        client.get(f"/sales/{sale_id}", headers=operator_a),
        client.get("/sales", params={"merchant_id": merchant_a}, headers=operator_a),
        client.get(f"/sales/{sale_id}/receipt", headers=operator_a),
        client.get(f"/sales/{sale_id}", headers=operator_a),
        client.get(f"/sales/{sale_id}", headers=operator_a),
    ]

    refused = [
        client.get(f"/sales/{sale_id}", headers=operator_a),
        client.get("/sales", params={"merchant_id": merchant_a}, headers=operator_a),
        client.get(f"/sales/{sale_id}/receipt", headers=operator_a),
    ]
    other_actor = client.get(f"/sales/{sale_id}", headers=admin)

    assert [response.status_code for response in reads] == [
        HTTPStatus.OK,
        HTTPStatus.OK,
        HTTPStatus.NOT_FOUND,
        HTTPStatus.OK,
        HTTPStatus.OK,
    ]
    for response in refused:
        assert_quota_exceeded(response)
    assert other_actor.status_code == HTTPStatus.OK


def test_unauthenticated_reads_are_refused_before_spending_any_quota(
    client: TestClient, migrated_database_url: str
) -> None:
    merchant_a = ready_merchant(client, migrated_database_url, "Tienda Demo A", OPERATOR_A)
    operator_a = bearer(client, OPERATOR_A)
    sale_id = post_sale(client, operator_a, merchant_a, amount_cents=AMOUNT).json()["id"]

    anonymous = [client.get(f"/sales/{sale_id}") for _ in range(READ_QUOTA + 1)]
    authenticated = client.get(f"/sales/{sale_id}", headers=operator_a)

    assert {response.status_code for response in anonymous} == {HTTPStatus.UNAUTHORIZED}
    assert authenticated.status_code == HTTPStatus.OK


def test_oversized_bodies_are_refused_before_creating_anything(
    client: TestClient, migrated_database_url: str
) -> None:
    merchant_a = ready_merchant(client, migrated_database_url, "Tienda Demo A", OPERATOR_A)
    headers = {**bearer(client, OPERATOR_A), IDEMPOTENCY_HEADER: str(uuid.uuid4())}
    oversized = (
        '{"merchant_id": "'
        + merchant_a
        + '", "amount_cents": 30000, "concept": "'
        + "x" * BODY_LIMIT
        + '"}'
    ).encode()

    declared = client.post(
        "/sales", content=oversized, headers={**headers, "Content-Type": "application/json"}
    )
    streamed = client.post(
        "/sales",
        content=iter([oversized[:1024], oversized[1024:]]),
        headers={**headers, "Content-Type": "application/json"},
    )

    assert declared.status_code == HTTPStatus.CONTENT_TOO_LARGE
    assert streamed.status_code == HTTPStatus.CONTENT_TOO_LARGE
    assert sale_count(migrated_database_url) == 0


def race_for_the_last_slot(
    client: TestClient, database_url: str, merchant_a: str, commit: bool
) -> Response:
    operator_a = bearer(client, OPERATOR_A)
    for _ in range(SALE_QUOTA - 1):
        post_sale(client, operator_a, merchant_a, amount_cents=AMOUNT)
    summary = actor_of(client, operator_a)
    database = Database.from_settings(quota_settings(database_url))
    policy = QuotaPolicy(SALE_QUOTA, timedelta(seconds=60))
    try:
        with database.session_factory() as racing, racing.begin():
            request = SaleRequest(
                summary, uuid.UUID(merchant_a), AMOUNT, None, str(uuid.uuid4()), policy
            )
            create_sale(racing, request, DEFAULT_MAXIMUM, STARTED_AT)
            with ThreadPoolExecutor(max_workers=1) as pool:
                waiting = pool.submit(
                    post_sale, client, operator_a, merchant_a, amount_cents=AMOUNT
                )
                wait_until_blocked_on_a_lock(database_url)
                if commit:
                    racing.commit()
                else:
                    racing.rollback()
                return waiting.result(timeout=10)
    finally:
        database.dispose()


def test_a_creation_waiting_for_the_last_slot_is_refused_once_another_takes_it(
    client: TestClient, migrated_database_url: str
) -> None:
    merchant_a = ready_merchant(client, migrated_database_url, "Tienda Demo A", OPERATOR_A)

    response = race_for_the_last_slot(client, migrated_database_url, merchant_a, commit=True)

    assert_quota_exceeded(response)
    assert sale_count(migrated_database_url) == SALE_QUOTA


def test_a_slot_released_by_a_rolled_back_creation_goes_to_the_waiting_one(
    client: TestClient, migrated_database_url: str
) -> None:
    merchant_a = ready_merchant(client, migrated_database_url, "Tienda Demo A", OPERATOR_A)

    response = race_for_the_last_slot(client, migrated_database_url, merchant_a, commit=False)

    assert response.status_code == HTTPStatus.CREATED
    assert sale_count(migrated_database_url) == SALE_QUOTA


def test_simultaneous_qr_requests_never_exceed_the_quota(
    client: TestClient, migrated_database_url: str, provider: CountingProvider
) -> None:
    merchant_a = ready_merchant(client, migrated_database_url, "Tienda Demo A", OPERATOR_A)
    operator_a = bearer(client, OPERATOR_A)
    sales = [
        post_sale(client, operator_a, merchant_a, amount_cents=AMOUNT).json()["id"]
        for _ in range(SALE_QUOTA)
    ]

    with ThreadPoolExecutor(max_workers=len(sales)) as pool:
        responses = list(pool.map(lambda sale_id: request_qr(client, operator_a, sale_id), sales))

    statuses = sorted(response.status_code for response in responses)
    assert statuses == [HTTPStatus.CREATED] * ATTEMPT_QUOTA + [HTTPStatus.TOO_MANY_REQUESTS]
    assert len(provider.created) == ATTEMPT_QUOTA
    assert scalar(migrated_database_url, "SELECT count(*) FROM payment_attempts") == ATTEMPT_QUOTA


def test_reading_a_pending_attempt_many_times_never_calls_the_provider(
    migrated_database_url: str, clock: MovableClock, provider: CountingProvider
) -> None:
    settings = build_settings(database_url=migrated_database_url)
    with start_client(settings, migrated_database_url, provider, clock) as client:
        merchant_a = ready_merchant(client, migrated_database_url, "Tienda Demo A", OPERATOR_A)
        operator_a = bearer(client, OPERATOR_A)
        sale_id = post_sale(client, operator_a, merchant_a, amount_cents=AMOUNT).json()["id"]
        request_qr(client, operator_a, sale_id)

        reads = [client.get(f"/sales/{sale_id}", headers=operator_a) for _ in range(100)]
        history = client.get("/sales", params={"merchant_id": merchant_a}, headers=operator_a)

    assert {response.status_code for response in reads} == {HTTPStatus.OK}
    assert {response.json()["attempts"][0]["status"] for response in reads} == {"pending"}
    assert history.json()["items"][0]["attempt_count"] == 1
    assert len(provider.created) == 1
    assert provider.queried == []
