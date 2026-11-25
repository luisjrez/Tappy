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

from tappy.platform.database import Database
from tappy.sales.reconciliation import reconcile_attempt
from tests.payments.pey_support import CREATED, FakePey
from tests.payments.webhook_support import Delivery, deliver, settings_for
from tests.sales.support import (
    IDEMPOTENCY_HEADER,
    OPERATOR_A,
    OPERATOR_B,
    RECEIVER_A,
    bearer,
    create_sale,
    ready_merchant,
    start_client,
)
from tests.support import MovableClock, build_settings, execute

LOCAL = ZoneInfo("America/Mexico_City")
PRICE = 10000


def local(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=LOCAL)


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
    return MovableClock(local(2026, 12, 1, 9, 0))


@pytest.fixture
def client(migrated_database_url: str, clock: MovableClock) -> Iterator[TestClient]:
    settings = settings_for(migrated_database_url)
    provider = SequentialPey().provider()
    with start_client(settings, migrated_database_url, provider, clock) as started:
        yield started


@pytest.fixture
def merchant(client: TestClient, migrated_database_url: str) -> str:
    return ready_merchant(client, migrated_database_url, "Tienda Demo A", OPERATOR_A)


def charge(client: TestClient, merchant: str) -> Any:
    operator_a = bearer(client, OPERATOR_A)
    sale = create_sale(client, operator_a, merchant, amount_cents=PRICE).json()
    return client.post(
        f"/sales/{sale['id']}/attempts",
        json={"method": "qr"},
        headers={**operator_a, IDEMPOTENCY_HEADER: str(uuid.uuid4())},
    ).json()


def pay(
    client: TestClient,
    clock: MovableClock,
    attempt: dict[str, Any],
    transaction_id: str,
    paid: datetime | None,
) -> None:
    event: dict[str, object] = {
        "type": "codi.qr.payment_received",
        "amount": PRICE / 100,
        "bankAccountId": RECEIVER_A["provider_account_id"],
        "codiQrId": attempt["provider_request_id"],
        "transactionId": transaction_id,
        "metadata": {"tappy_attempt_id": attempt["id"]},
    }
    if paid is not None:
        event["datePaid"] = int(paid.timestamp())
    signed = Delivery(f"msg_{transaction_id.lower()}", int(clock.now().timestamp()))
    deliver(client, json.dumps(event, separators=(",", ":")).encode(), signed)


def reconcile_with_bank_time(
    database_url: str, attempt: dict[str, Any], clock: MovableClock, paid: datetime
) -> None:
    item = {
        "id": "TX-JANUARY",
        "status": "PAID",
        "amount": PRICE / 100,
        "datePaid": int(paid.timestamp()),
    }
    database = Database.from_settings(build_settings(database_url=database_url))
    try:
        provider = FakePey(pages=[(200, {"items": [item], "nextToken": None})]).provider()
        reconcile_attempt(database, uuid.UUID(attempt["id"]), provider, "test", clock)
    finally:
        database.dispose()


def period(
    client: TestClient, merchant: str, headers: dict[str, str], kind: str, day: str
) -> Response:
    return client.get(
        f"/merchants/{merchant}/summary", headers=headers, params={"period": kind, "date": day}
    )


def totals(body: dict[str, Any]) -> tuple[str, str, int, int]:
    return body["start"], body["end"], body["received_amount_cents"], body["transfer_count"]


def test_movements_follow_the_local_calendar_and_monday_to_sunday_weeks(
    client: TestClient, merchant: str, clock: MovableClock
) -> None:
    for transaction, paid in (
        ("TX-SUNDAY-LATE", local(2026, 11, 29, 23, 30)),
        ("TX-MONDAY-EARLY", local(2026, 11, 30, 0, 30)),
        ("TX-MONTH-END", local(2026, 11, 30, 23, 50)),
        ("TX-DECEMBER", local(2026, 12, 1, 0, 10)),
    ):
        pay(client, clock, charge(client, merchant), transaction, paid)
    operator_a = bearer(client, OPERATOR_A)

    sunday = period(client, merchant, operator_a, "day", "2026-11-29").json()
    monday = period(client, merchant, operator_a, "day", "2026-11-30").json()
    first_week = period(client, merchant, operator_a, "week", "2026-11-29").json()
    second_week = period(client, merchant, operator_a, "week", "2026-11-30").json()
    november = period(client, merchant, operator_a, "month", "2026-11-15").json()
    december = period(client, merchant, operator_a, "month", "2026-12-31").json()

    assert totals(sunday) == ("2026-11-29", "2026-11-29", PRICE, 1)
    assert totals(monday) == ("2026-11-30", "2026-11-30", 2 * PRICE, 2)
    assert totals(first_week) == ("2026-11-23", "2026-11-29", PRICE, 1)
    assert totals(second_week) == ("2026-11-30", "2026-12-06", 3 * PRICE, 3)
    assert totals(november) == ("2026-11-01", "2026-11-30", 3 * PRICE, 3)
    assert totals(december) == ("2026-12-01", "2026-12-31", PRICE, 1)
    assert [day["date"] for day in first_week["days"]][::6] == ["2026-11-23", "2026-11-29"]
    assert len(november["days"]) == len(range(1, 31))
    assert [day["transfer_count"] for day in november["days"][-2:]] == [1, 2]
    assert first_week["timezone"] == "America/Mexico_City"


def test_a_valid_reception_without_a_bank_time_uses_the_reception_time_explicitly(
    client: TestClient, merchant: str, clock: MovableClock
) -> None:
    attempt = charge(client, merchant)
    pay(client, clock, attempt, "TX-NO-BANK-TIME", None)
    operator_a = bearer(client, OPERATOR_A)

    day = period(client, merchant, operator_a, "day", "2026-12-01").json()
    sale_id = client.get("/sales", headers=operator_a).json()["items"][0]["id"]
    transfer = client.get(f"/sales/{sale_id}", headers=operator_a).json()["transfers"][0]

    assert totals(day) == ("2026-12-01", "2026-12-01", PRICE, 1)
    assert day["reception_dated_transfer_count"] == 1
    assert transfer["occurred_at"] is None
    assert transfer["dated_by"] == "reception"
    assert transfer["received_at"] == clock.now().astimezone(UTC).isoformat().replace("+00:00", "Z")


def test_a_month_end_payment_notified_next_month_counts_once_in_its_bank_month(
    client: TestClient, migrated_database_url: str, merchant: str, clock: MovableClock
) -> None:
    attempt = charge(client, merchant)
    clock.current = local(2027, 2, 1, 0, 20)
    pay(client, clock, attempt, "TX-JANUARY", local(2027, 1, 31, 23, 50))
    reconcile_with_bank_time(migrated_database_url, attempt, clock, local(2027, 1, 31, 23, 50))
    operator_a = bearer(client, OPERATOR_A)

    january = period(client, merchant, operator_a, "month", "2027-01-10").json()
    february = period(client, merchant, operator_a, "month", "2027-02-10").json()

    assert (january["received_amount_cents"], january["covered_sale_count"]) == (PRICE, 1)
    assert (february["received_amount_cents"], february["transfer_count"]) == (0, 0)


def test_a_late_bank_time_moves_a_reception_dated_transfer_to_its_bank_period_once(
    client: TestClient, migrated_database_url: str, merchant: str, clock: MovableClock
) -> None:
    attempt = charge(client, merchant)
    clock.current = local(2027, 2, 1, 0, 20)
    pay(client, clock, attempt, "TX-JANUARY", None)
    operator_a = bearer(client, OPERATOR_A)
    before = period(client, merchant, operator_a, "month", "2027-02-10").json()

    reconcile_with_bank_time(migrated_database_url, attempt, clock, local(2027, 1, 31, 23, 50))
    reconcile_with_bank_time(migrated_database_url, attempt, clock, local(2027, 1, 15, 9, 0))
    january = period(client, merchant, operator_a, "month", "2027-01-10").json()
    february = period(client, merchant, operator_a, "month", "2027-02-10").json()
    transfer = client.get(f"/sales/{attempt['sale_id']}", headers=operator_a).json()["transfers"]

    assert (before["received_amount_cents"], before["reception_dated_transfer_count"]) == (PRICE, 1)
    assert (january["received_amount_cents"], january["reception_dated_transfer_count"]) == (
        PRICE,
        0,
    )
    assert [day["date"] for day in january["days"] if day["transfer_count"]] == ["2027-01-31"]
    assert (february["received_amount_cents"], february["transfer_count"]) == (0, 0)
    assert len(transfer) == 1
    assert transfer[0]["dated_by"] == "bank"


def test_the_database_only_lets_a_missing_bank_time_be_filled_once(
    client: TestClient, migrated_database_url: str, merchant: str, clock: MovableClock
) -> None:
    pay(client, clock, charge(client, merchant), "TX-DATED", None)

    execute(migrated_database_url, "UPDATE transactions SET occurred_at = now()")
    for statement in (
        "UPDATE transactions SET occurred_at = now() - interval '1 day'",
        "UPDATE transactions SET amount_cents = 1",
        "DELETE FROM transactions",
    ):
        with pytest.raises(Exception, match="recorded transfers are immutable"):
            execute(migrated_database_url, statement)


def test_the_daily_endpoint_matches_the_day_period(
    client: TestClient, merchant: str, clock: MovableClock
) -> None:
    pay(client, clock, charge(client, merchant), "TX-SAME", local(2026, 11, 30, 12, 0))
    operator_a = bearer(client, OPERATOR_A)

    daily = client.get(
        f"/merchants/{merchant}/summary/daily", headers=operator_a, params={"date": "2026-11-30"}
    ).json()
    day = period(client, merchant, operator_a, "day", "2026-11-30").json()

    shared = ("received_amount_cents", "transfer_count", "covered_sale_count")
    assert [daily[key] for key in shared] == [day[key] for key in shared]


@pytest.mark.parametrize(
    "params",
    [
        {"period": "year", "date": "2026-11-30"},
        {"period": "week", "date": "2026-02-30"},
        {"date": "2026-11-30"},
        {"period": "week", "date": "2026-11-30", "extra": "1"},
    ],
)
def test_invalid_periods_are_rejected(
    client: TestClient, merchant: str, params: dict[str, str]
) -> None:
    response = client.get(
        f"/merchants/{merchant}/summary", headers=bearer(client, OPERATOR_A), params=params
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT


def test_period_summaries_are_limited_to_accessible_merchants(
    client: TestClient, merchant: str
) -> None:
    foreign = period(client, merchant, bearer(client, OPERATOR_B), "month", "2026-11-30")

    assert foreign.status_code == HTTPStatus.NOT_FOUND
    assert foreign.json() == {"detail": "Merchant not found"}
