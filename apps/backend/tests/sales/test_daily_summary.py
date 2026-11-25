import json
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response

from tests.payments.pey_support import CREATED, FakePey
from tests.payments.webhook_support import Delivery, deliver, settings_for
from tests.sales.support import (
    ADMIN,
    IDEMPOTENCY_HEADER,
    OPERATOR_A,
    OPERATOR_B,
    RECEIVER_A,
    bearer,
    create_sale,
    ready_merchant,
    start_client,
)
from tests.support import MovableClock

LOCAL = ZoneInfo("America/Mexico_City")
DAY = "2026-11-25"
PRICE = 30000
NOON = int(datetime(2026, 11, 25, 12, 0, tzinfo=LOCAL).timestamp())
LATE_EVENING = int(datetime(2026, 11, 25, 23, 30, tzinfo=LOCAL).timestamp())
NEXT_DAY = int(datetime(2026, 11, 26, 0, 30, tzinfo=LOCAL).timestamp())


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
def client(migrated_database_url: str) -> Iterator[TestClient]:
    settings = settings_for(migrated_database_url)
    with start_client(settings, migrated_database_url, SequentialPey().provider()) as started:
        yield started


@pytest.fixture
def merchant(client: TestClient, migrated_database_url: str) -> str:
    return ready_merchant(client, migrated_database_url, "Tienda Demo A", OPERATOR_A)


def charge(client: TestClient, merchant: str, amount: int) -> tuple[dict[str, Any], Any]:
    operator_a = bearer(client, OPERATOR_A)
    sale = create_sale(client, operator_a, merchant, amount_cents=amount).json()
    attempt = client.post(
        f"/sales/{sale['id']}/attempts",
        json={"method": "qr"},
        headers={**operator_a, IDEMPOTENCY_HEADER: str(uuid.uuid4())},
    ).json()
    return sale, attempt


def pay(
    client: TestClient, attempt: dict[str, Any], amount: int, transaction_id: str, paid_at: int
) -> None:
    event = {
        "type": "codi.qr.payment_received",
        "amount": amount / 100,
        "bankAccountId": RECEIVER_A["provider_account_id"],
        "codiQrId": attempt["provider_request_id"],
        "datePaid": paid_at,
        "transactionId": transaction_id,
        "metadata": {"tappy_attempt_id": attempt["id"]},
    }
    body = json.dumps(event, separators=(",", ":")).encode()
    deliver(client, body, Delivery(message_id=f"msg_{transaction_id.lower()}"))


def summary(client: TestClient, merchant: str, headers: dict[str, str], **params: str) -> Response:
    return client.get(f"/merchants/{merchant}/summary/daily", headers=headers, params=params)


def test_received_money_counts_transfers_and_covered_sales_but_not_pending(
    client: TestClient, merchant: str
) -> None:
    _, first = charge(client, merchant, 30000)
    _, second = charge(client, merchant, 15000)
    charge(client, merchant, 20000)
    pay(client, first, 30000, "TX-300", NOON)
    pay(client, second, 15000, "TX-150", LATE_EVENING)

    body = summary(client, merchant, bearer(client, OPERATOR_A), date=DAY).json()

    assert body == {
        "merchant_id": merchant,
        "date": DAY,
        "timezone": "America/Mexico_City",
        "received_amount_cents": 45000,
        "currency": "MXN",
        "transfer_count": 2,
        "covered_sale_count": 2,
        "review_sale_count": 0,
        "open_exception_count": 0,
    }


def test_a_day_without_confirmed_transfers_reports_nothing(
    client: TestClient, merchant: str
) -> None:
    _, attempt = charge(client, merchant, 30000)
    charge(client, merchant, 20000)
    pay(client, attempt, 30000, "TX-NEXT-DAY", NEXT_DAY)

    body = summary(client, merchant, bearer(client, OPERATOR_A), date=DAY).json()

    assert (body["received_amount_cents"], body["transfer_count"]) == (0, 0)
    assert (body["covered_sale_count"], body["review_sale_count"]) == (0, 0)
    assert body["open_exception_count"] == 0


def test_a_second_distinct_transfer_counts_money_but_not_another_sale(
    client: TestClient, merchant: str
) -> None:
    sale, attempt = charge(client, merchant, 30000)
    pay(client, attempt, 30000, "TX-ONE", NOON)
    pay(client, attempt, 30000, "TX-TWO", LATE_EVENING)
    operator_a = bearer(client, OPERATOR_A)

    body = summary(client, merchant, operator_a, date=DAY).json()
    detail = client.get(f"/sales/{sale['id']}", headers=operator_a).json()

    counts = (
        body["received_amount_cents"],
        body["transfer_count"],
        body["covered_sale_count"],
        body["review_sale_count"],
        body["open_exception_count"],
    )
    assert counts == (2 * PRICE, 2, 1, 1, 1)
    assert [item["reason"] for item in detail["exceptions"]] == ["double_reception"]


def test_redelivered_evidence_never_inflates_the_summary(client: TestClient, merchant: str) -> None:
    _, attempt = charge(client, merchant, 30000)
    pay(client, attempt, 30000, "TX-ONCE", NOON)
    event = {
        "type": "codi.qr.payment_received",
        "amount": 300.0,
        "bankAccountId": RECEIVER_A["provider_account_id"],
        "codiQrId": attempt["provider_request_id"],
        "datePaid": NOON,
        "transactionId": "TX-ONCE",
        "metadata": {"tappy_attempt_id": attempt["id"]},
    }
    deliver(client, json.dumps(event).encode(), Delivery(message_id="msg_again"))

    body = summary(client, merchant, bearer(client, OPERATOR_A), date=DAY).json()

    assert (body["received_amount_cents"], body["transfer_count"]) == (30000, 1)


def test_the_day_follows_the_business_timezone_not_utc(client: TestClient, merchant: str) -> None:
    _, attempt = charge(client, merchant, 30000)
    pay(client, attempt, 30000, "TX-LATE", LATE_EVENING)
    utc_day = datetime.fromtimestamp(LATE_EVENING, UTC).date().isoformat()

    local = summary(client, merchant, bearer(client, OPERATOR_A), date=DAY).json()
    next_local = summary(client, merchant, bearer(client, OPERATOR_A), date=utc_day).json()

    assert utc_day != DAY
    assert local["received_amount_cents"] == PRICE
    assert next_local["received_amount_cents"] == 0


@pytest.mark.parametrize("day", ["2026-13-01", "25/11/2026", "yesterday"])
def test_invalid_days_are_rejected(client: TestClient, merchant: str, day: str) -> None:
    response = summary(client, merchant, bearer(client, OPERATOR_A), date=day)

    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT


def test_summaries_are_limited_to_accessible_merchants(
    client: TestClient, migrated_database_url: str, merchant: str
) -> None:
    _, attempt = charge(client, merchant, 30000)
    pay(client, attempt, 30000, "TX-PRIVATE", NOON)

    foreign = summary(client, merchant, bearer(client, OPERATOR_B), date=DAY)
    admin = summary(client, merchant, bearer(client, ADMIN), date=DAY)
    unknown = summary(client, str(uuid.uuid4()), bearer(client, OPERATOR_A), date=DAY)
    anonymous = summary(client, merchant, {}, date=DAY)

    assert foreign.status_code == HTTPStatus.NOT_FOUND
    assert foreign.json() == {"detail": "Merchant not found"}
    assert "30000" not in foreign.text
    assert admin.json()["received_amount_cents"] == PRICE
    assert unknown.status_code == HTTPStatus.NOT_FOUND
    assert anonymous.status_code == HTTPStatus.UNAUTHORIZED


def test_the_default_day_is_todays_local_date_on_the_server_clock(
    migrated_database_url: str,
) -> None:
    late_utc = MovableClock(datetime(2026, 11, 26, 5, 0, tzinfo=UTC))
    settings = settings_for(migrated_database_url)
    with start_client(settings, migrated_database_url, FakePey().provider(), late_utc) as client:
        merchant = ready_merchant(client, migrated_database_url, "Tienda Demo A", OPERATOR_A)
        body = summary(client, merchant, bearer(client, OPERATOR_A)).json()

    assert body["date"] == DAY
