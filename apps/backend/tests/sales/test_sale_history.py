import json
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from typing import Any

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response

from tests.payments.pey_support import CREATED, FakePey
from tests.payments.webhook_support import Delivery, deliver, settings_for
from tests.sales.support import (
    ADMIN,
    AMOUNT,
    BLOCKED_DISABLED,
    IDEMPOTENCY_HEADER,
    OPERATOR_A,
    OPERATOR_B,
    RECEIVER_A,
    bearer,
    configure,
    create_sale,
    merchant_of,
    ready_merchant,
    start_client,
)
from tests.support import MovableClock, execute

START = datetime(2026, 11, 25, 12, 0, tzinfo=UTC)
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
def client(migrated_database_url: str, clock: MovableClock) -> Iterator[TestClient]:
    settings = settings_for(migrated_database_url)
    provider = SequentialPey().provider()
    with start_client(settings, migrated_database_url, provider, clock) as started:
        yield started


def history(client: TestClient, headers: dict[str, str], **params: str | int) -> Response:
    return client.get("/sales", headers=headers, params=params)


def every_page(client: TestClient, headers: dict[str, str], **params: str | int) -> list[list[str]]:
    pages: list[list[str]] = []
    cursor: str | None = None
    while True:
        query: dict[str, str | int] = {**params, **({"cursor": cursor} if cursor else {})}
        body = history(client, headers, **query).json()
        pages.append([item["id"] for item in body["items"]])
        cursor = body["next_cursor"]
        if cursor is None:
            return pages


def new_sale(
    client: TestClient, headers: dict[str, str], merchant: str, amount: int = AMOUNT
) -> dict[str, Any]:
    sale: dict[str, Any] = create_sale(client, headers, merchant, amount_cents=amount).json()
    return sale


def request_qr(client: TestClient, headers: dict[str, str], sale: dict[str, Any]) -> Any:
    return client.post(
        f"/sales/{sale['id']}/attempts",
        json={"method": "qr"},
        headers={**headers, IDEMPOTENCY_HEADER: str(uuid.uuid4())},
    ).json()


def pay(
    client: TestClient, attempt: dict[str, Any], transaction_id: str, clock: MovableClock
) -> None:
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
    signed = Delivery(f"msg_{transaction_id.lower()}", int(clock.now().timestamp()))
    deliver(client, body, signed)


def test_consecutive_pages_are_stable_without_repeats_or_gaps(
    client: TestClient, migrated_database_url: str, clock: MovableClock
) -> None:
    merchant_a = ready_merchant(client, migrated_database_url, "Tienda Demo A", OPERATOR_A)
    operator_a = bearer(client, OPERATOR_A)
    created = []
    for minutes in (0, 3, 6, 6, 9):
        clock.current = START + timedelta(minutes=minutes)
        sale = new_sale(client, operator_a, merchant_a)
        request_qr(client, operator_a, sale)
        created.append(sale)
    clock.current = START + timedelta(minutes=12)

    pages = every_page(client, operator_a, limit=2)
    first = history(client, operator_a, limit=2).json()
    new_sale(client, operator_a, merchant_a)
    second_after_insert = history(client, operator_a, limit=2, cursor=first["next_cursor"])

    flat = [sale_id for page in pages for sale_id in page]
    expected = [sale["id"] for sale in sorted(created, key=lambda s: (s["created_at"], s["id"]))]
    assert [len(page) for page in pages] == [2, 2, 1]
    assert flat == expected[::-1]
    assert len(set(flat)) == len(flat)
    assert [item["id"] for item in second_after_insert.json()["items"]] == pages[1]


def test_rows_carry_the_sale_summary_without_attempt_duplication(
    client: TestClient, migrated_database_url: str, clock: MovableClock
) -> None:
    merchant_a = ready_merchant(client, migrated_database_url, "Tienda Demo A", OPERATOR_A)
    operator_a = bearer(client, OPERATOR_A)
    sale = new_sale(client, operator_a, merchant_a)
    attempt = request_qr(client, operator_a, sale)
    pay(client, attempt, "TX-ROW", clock)

    body = history(client, operator_a).json()

    assert body == {
        "items": [
            {
                "id": sale["id"],
                "merchant_id": merchant_a,
                "reference": sale["reference"],
                "amount_cents": AMOUNT,
                "currency": "MXN",
                "concept": None,
                "status": "paid",
                "covered": True,
                "confirmed_amount_cents": AMOUNT,
                "attempt_count": 1,
                "beneficiary_name": sale["beneficiary_name"],
                "masked_account": sale["masked_account"],
                "created_at": sale["created_at"],
            }
        ],
        "next_cursor": None,
    }


@pytest.mark.parametrize(
    "params",
    [
        {"status": "cancelled"},
        {"limit": 0},
        {"limit": 51},
        {"foo": "1"},
        {"cursor": "not-a-cursor"},
        {"created_from": "2026-11-25T12:00:00"},
        {"created_from": "2026-11-26T00:00:00Z", "created_to": "2026-11-25T00:00:00Z"},
        {"merchant_id": "not-a-uuid"},
    ],
)
def test_invalid_history_requests_are_rejected(
    client: TestClient, migrated_database_url: str, params: dict[str, str | int]
) -> None:
    ready_merchant(client, migrated_database_url, "Tienda Demo A", OPERATOR_A)

    response = history(client, bearer(client, OPERATOR_A), **params)

    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT


def test_history_never_exposes_another_merchant(
    client: TestClient, migrated_database_url: str
) -> None:
    merchant_a = ready_merchant(client, migrated_database_url, "Tienda Demo A", OPERATOR_A)
    merchant_b = merchant_of(client, migrated_database_url, "Tienda Demo B", OPERATOR_B)
    configure(client, merchant_b, provider_account_id="bank-account-demo-b")
    operator_a = bearer(client, OPERATOR_A)
    operator_b = bearer(client, OPERATOR_B)
    sale_a = new_sale(client, operator_a, merchant_a)
    sale_b = new_sale(client, operator_b, merchant_b)
    foreign_cursor = history(client, bearer(client, ADMIN), limit=1).json()["next_cursor"]

    own = history(client, operator_a).json()
    filtered_foreign = history(client, operator_a, merchant_id=merchant_b)
    cursor_from_admin = history(client, operator_a, cursor=foreign_cursor).json()
    admin = history(client, bearer(client, ADMIN)).json()
    anonymous = history(client, {})

    assert [item["id"] for item in own["items"]] == [sale_a["id"]]
    assert filtered_foreign.status_code == HTTPStatus.NOT_FOUND
    assert filtered_foreign.json() == {"detail": "Merchant not found"}
    assert sale_b["id"] not in json.dumps(cursor_from_admin)
    assert {item["id"] for item in admin["items"]} == {sale_a["id"], sale_b["id"]}
    assert anonymous.status_code == HTTPStatus.UNAUTHORIZED


def test_status_filters_keep_pending_apart_from_confirmed_one_row_per_sale(
    client: TestClient, migrated_database_url: str, clock: MovableClock
) -> None:
    merchant_a = ready_merchant(client, migrated_database_url, "Tienda Demo A", OPERATOR_A)
    operator_a = bearer(client, OPERATOR_A)
    retried = new_sale(client, operator_a, merchant_a)
    first = request_qr(client, operator_a, retried)
    execute(
        migrated_database_url,
        "UPDATE payment_attempts SET status = 'expired', verified_at = now() WHERE id = :id",
        {"id": first["id"]},
    )
    request_qr(client, operator_a, retried)
    clock.advance(timedelta(minutes=1))
    pending = new_sale(client, operator_a, merchant_a)
    request_qr(client, operator_a, pending)
    clock.advance(timedelta(minutes=1))
    confirmed = new_sale(client, operator_a, merchant_a)
    pay(client, request_qr(client, operator_a, confirmed), "TX-CONFIRMED", clock)

    open_pages = every_page(client, operator_a, status="open", limit=1)
    paid = history(client, operator_a, status="paid").json()["items"]

    assert open_pages == [[pending["id"]], [retried["id"]]]
    assert [(item["id"], item["covered"]) for item in paid] == [(confirmed["id"], True)]
    rows = history(client, operator_a).json()["items"]
    assert [item["attempt_count"] for item in rows] == [1, 1, 2]


def test_history_filters_by_creation_time_and_merchant(
    client: TestClient, migrated_database_url: str, clock: MovableClock
) -> None:
    merchant_a = ready_merchant(client, migrated_database_url, "Tienda Demo A", OPERATOR_A)
    operator_a = bearer(client, OPERATOR_A)
    early = new_sale(client, operator_a, merchant_a)
    clock.advance(timedelta(minutes=10))
    late = new_sale(client, operator_a, merchant_a)
    boundary = (START + timedelta(minutes=5)).isoformat()

    before = history(client, operator_a, created_to=boundary, merchant_id=merchant_a).json()
    after = history(client, operator_a, created_from=boundary).json()

    assert [item["id"] for item in before["items"]] == [early["id"]]
    assert [item["id"] for item in after["items"]] == [late["id"]]


def test_history_keeps_confirmed_sales_after_the_receiver_is_disabled(
    client: TestClient, migrated_database_url: str, clock: MovableClock
) -> None:
    merchant_a = ready_merchant(client, migrated_database_url, "Tienda Demo A", OPERATOR_A)
    operator_a = bearer(client, OPERATOR_A)
    sale = new_sale(client, operator_a, merchant_a)
    pay(client, request_qr(client, operator_a, sale), "TX-KEPT", clock)

    configure(client, merchant_a, enabled=False)
    rows = history(client, operator_a).json()["items"]
    blocked = create_sale(client, operator_a, merchant_a, amount_cents=AMOUNT)

    assert [(row["id"], row["status"]) for row in rows] == [(sale["id"], "paid")]
    assert rows[0]["beneficiary_name"] == sale["beneficiary_name"]
    assert rows[0]["masked_account"] == sale["masked_account"]
    assert blocked.status_code == HTTPStatus.CONFLICT
    assert blocked.json() == {"detail": BLOCKED_DISABLED}


def test_fifty_is_the_largest_accepted_limit(client: TestClient, migrated_database_url: str) -> None:
    ready_merchant(client, migrated_database_url, "Tienda Demo A", OPERATOR_A)

    response = history(client, bearer(client, OPERATOR_A), limit=50)

    assert response.status_code == HTTPStatus.OK
