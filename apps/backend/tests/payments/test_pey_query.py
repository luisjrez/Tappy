from datetime import UTC, datetime, timedelta
from typing import Any

import httpx2
import pytest

from tappy.payments.provider import PaymentsQueryError, QrPayment, QueryProblem
from tappy.platform.config import MAX_QUERY_PAGES
from tests.payments.pey_support import API_KEY, QUERY_FIXTURE, FakePey

QR_ID = "AB12CD34EF"
EXAMPLE: dict[str, Any] = QUERY_FIXTURE["responses"]["200"]["default"]
PAID_AT = 1795000000


def item(transaction_id: str, status: str = "PAID", amount: object = 300.0) -> dict[str, object]:
    return {
        "id": transaction_id,
        "status": status,
        "amount": amount,
        "currency": "MXN",
        "paymentMethod": "CODI",
        "dateCreated": PAID_AT,
        "datePaid": PAID_AT,
    }


def page(*items: dict[str, object], next_token: str | None = None) -> tuple[int, object]:
    return 200, {"items": list(items), "nextToken": next_token}


def test_follows_next_tokens_and_returns_only_paid_transactions() -> None:
    fake = FakePey(
        pages=[
            page(item("TX-PENDING", status="PENDING"), next_token="token-2"),
            page(item("TX-PAID")),
        ]
    )

    payments = fake.provider().qr_payments(QR_ID)

    first, second = fake.queries()
    assert first.url.path == f"/transaction/codi/qr/{QR_ID}"
    assert "nextToken" not in first.url.params
    assert second.url.params["nextToken"] == "token-2"
    assert first.headers["Authorization"] == f"Bearer {API_KEY}"
    assert payments == [QrPayment("TX-PAID", 30000, datetime.fromtimestamp(PAID_AT, UTC))]


def test_the_official_example_page_is_understood() -> None:
    fake = FakePey(pages=[(200, {**EXAMPLE, "nextToken": None})])

    payments = fake.provider().qr_payments(QR_ID)

    assert payments == [
        QrPayment("01HXYZTXN1234567890ABCDE00", 10000, datetime.fromtimestamp(1704067200, UTC))
    ]


def test_an_empty_answer_is_no_evidence_rather_than_a_rejection() -> None:
    assert FakePey(pages=[page()]).provider().qr_payments(QR_ID) == []


def test_unusable_amounts_or_dates_are_kept_as_incomplete_payments() -> None:
    broken = {**item("TX-BROKEN", amount=300.001), "datePaid": None}

    payments = FakePey(pages=[page(broken)]).provider().qr_payments(QR_ID)

    assert payments == [QrPayment("TX-BROKEN", None, None)]


@pytest.mark.parametrize(
    ("answer", "problem"),
    [
        ((404, QUERY_FIXTURE["responses"]["404"]["default"]), QueryProblem.NOT_FOUND),
        ((429, {}), QueryProblem.RATE_LIMITED),
        ((500, {}), QueryProblem.SERVER_ERROR),
        ((400, QUERY_FIXTURE["responses"]["400"]["invalidNextToken"]), QueryProblem.REJECTED),
        ((200, "not json"), QueryProblem.INVALID_RESPONSE),
        ((200, {"items": [{"status": "PAID"}], "nextToken": None}), QueryProblem.INVALID_RESPONSE),
    ],
)
def test_provider_problems_leave_the_payment_uncertain(
    answer: tuple[int, object], problem: QueryProblem
) -> None:
    with pytest.raises(PaymentsQueryError) as raised:
        FakePey(pages=[answer]).provider().qr_payments(QR_ID)

    assert raised.value.problem is problem


@pytest.mark.parametrize(
    ("error", "problem"),
    [
        (httpx2.ReadTimeout("slow"), QueryProblem.TIMEOUT),
        (httpx2.ConnectError("down"), QueryProblem.CONNECTION),
    ],
)
def test_network_failures_leave_the_payment_uncertain(
    error: Exception, problem: QueryProblem
) -> None:
    with pytest.raises(PaymentsQueryError) as raised:
        FakePey(error=error).provider().qr_payments(QR_ID)

    assert raised.value.problem is problem


def test_the_query_is_bounded_in_pages() -> None:
    endless = [page(next_token=f"token-{number}") for number in range(50)]
    fake = FakePey(pages=endless)

    with pytest.raises(PaymentsQueryError) as raised:
        fake.provider().qr_payments(QR_ID)

    assert raised.value.problem is QueryProblem.TOO_MANY_PAGES
    assert len(fake.queries()) == MAX_QUERY_PAGES


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("120", timedelta(seconds=120)),
        ("0", timedelta(0)),
        ("999999999999", timedelta(days=1)),
        ("Wed, 21 Oct 2026 07:28:00 GMT", None),
        ("-5", None),
    ],
)
def test_a_rate_limit_carries_the_providers_bounded_wait(
    header: str, expected: timedelta | None
) -> None:
    answer = httpx2.Response(429, json={}, headers={"Retry-After": header})

    with pytest.raises(PaymentsQueryError) as raised:
        FakePey(pages=[answer]).provider().qr_payments(QR_ID)

    assert raised.value.problem is QueryProblem.RATE_LIMITED
    assert raised.value.retry_after == expected
