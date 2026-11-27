import json
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from http import HTTPStatus
from pathlib import Path
from typing import Any

import httpx2
import pytest
from fastapi.testclient import TestClient

from tappy.payments.events import ReceivedEvent, store_event
from tappy.payments.pey import PeyQrProvider
from tappy.payments.provider import IssuedPhoneRequest, PhoneOrder, ProviderName
from tappy.platform.clock import SystemClock
from tappy.platform.config import Settings
from tappy.platform.database import Database
from tappy.platform.phones import phone_list
from tappy.sales.receptions import process_stored
from tappy.sales.reconciliation import ReconciliationReport, ReconciliationResult, reconcile_attempt
from tests.payments.pey_support import PUSH_CREATED, FakePey
from tests.payments.webhook_support import Delivery, deliver, settings_for
from tests.sales.phone_support import (
    ALLOWED,
    CONSENTED,
    demo_list_settings,
    open_sale,
    posted,
    request_phone,
)
from tests.sales.support import AMOUNT, RECEIVER_A, create_sale, start_client
from tests.support import build_settings, execute, run_sales, scalar

FIXTURES = Path(__file__).parents[1] / "fixtures" / "pey"
WEBHOOK_FIXTURE: dict[str, Any] = json.loads((FIXTURES / "webhook-codi-pn.json").read_text())
TRANSACTION_FIXTURE: dict[str, Any] = json.loads((FIXTURES / "transaction.json").read_text())
TRANSACTION_ID = PUSH_CREATED["transactionId"]
PHONE_EVENT = WEBHOOK_FIXTURE["event"]


def confirmation_settings(database_url: str, **changes: object) -> Settings:
    return settings_for(database_url).model_copy(
        update={"phone_request_numbers": phone_list(ALLOWED), **changes}
    )


@pytest.fixture
def fake() -> FakePey:
    return FakePey(status=200, body=PUSH_CREATED)


@pytest.fixture
def client(migrated_database_url: str, fake: FakePey) -> Iterator[TestClient]:
    settings = confirmation_settings(migrated_database_url)
    with start_client(settings, migrated_database_url, fake.provider()) as started:
        yield started


def pending_phone_request(
    client: TestClient, database_url: str
) -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
    sale, operator = open_sale(client, database_url)
    attempt = request_phone(
        client, operator, sale["id"], {"method": "phone", "phone_number": CONSENTED}
    ).json()
    return sale, attempt, operator


def push_paid_event(attempt: dict[str, Any], **changes: object) -> bytes:
    event = {
        **WEBHOOK_FIXTURE["example"],
        "amount": AMOUNT / 100,
        "bankAccountId": RECEIVER_A["provider_account_id"],
        "transactionId": attempt["provider_request_id"],
        **changes,
    }
    return json.dumps(event, separators=(",", ":")).encode()


def transaction(status: str, amount: float = AMOUNT / 100) -> tuple[int, object]:
    example = TRANSACTION_FIXTURE["responses"]["200"]["default"]
    return 200, {**example, "id": TRANSACTION_ID, "status": status, "amount": amount}


def reconcile(database_url: str, attempt: dict[str, Any], fake: FakePey) -> ReconciliationReport:
    database = Database.from_settings(build_settings(database_url=database_url))
    try:
        return reconcile_attempt(
            database, uuid.UUID(attempt["id"]), fake.provider(), "test", SystemClock()
        )
    finally:
        database.dispose()


class EarlyPaymentPey(PeyQrProvider):
    def __init__(self, fake: FakePey, database_url: str) -> None:
        issuing = fake.provider()
        super().__init__(issuing.settings, issuing.transport)
        self.database_url = database_url

    def request_phone_payment(self, order: PhoneOrder) -> IssuedPhoneRequest:
        event = {
            **WEBHOOK_FIXTURE["example"],
            "amount": order.amount_cents / 100,
            "bankAccountId": order.receiver_account,
            "transactionId": TRANSACTION_ID,
        }
        received = ReceivedEvent(
            provider=ProviderName.PEY,
            environment="test",
            message_id="msg_push_early",
            event_type=PHONE_EVENT,
            body=json.dumps(event).encode(),
            signed_at=datetime.now(UTC),
        )
        database = Database.from_settings(build_settings(database_url=self.database_url))
        try:
            with database.transaction() as session:
                store_event(session, received, datetime.now(UTC))
            process_stored(database, received, SystemClock())
        finally:
            database.dispose()
        return super().request_phone_payment(order)


def read(client: TestClient, operator: dict[str, str], sale: dict[str, Any]) -> dict[str, Any]:
    body: dict[str, Any] = client.get(f"/sales/{sale['id']}", headers=operator).json()
    return body


def test_an_exact_phone_payment_event_confirms_the_sale_once(
    client: TestClient, migrated_database_url: str
) -> None:
    sale, attempt, operator = pending_phone_request(client, migrated_database_url)
    body = push_paid_event(attempt)

    statuses = [
        deliver(client, body, Delivery(message_id=message)).status_code
        for message in ("msg_push_1", "msg_push_1", "msg_push_2")
    ]
    detail = read(client, operator, sale)

    assert statuses == [HTTPStatus.NO_CONTENT] * 3
    assert detail["status"] == "paid"
    assert detail["confirmed_amount_cents"] == AMOUNT
    assert [transfer["provider_transaction_id"] for transfer in detail["transfers"]] == [
        TRANSACTION_ID
    ]
    assert detail["attempts"][0]["status"] == "paid"
    assert detail["exceptions"] == []
    assert scalar(migrated_database_url, "SELECT count(*) FROM transactions") == 1
    assert (
        scalar(
            migrated_database_url,
            "SELECT string_agg(status, ',' ORDER BY provider_event_id) FROM webhook_events",
        )
        == "applied,duplicate"
    )


def test_a_query_finds_the_paid_phone_payment_through_its_transaction(
    client: TestClient, migrated_database_url: str, fake: FakePey
) -> None:
    sale, attempt, operator = pending_phone_request(client, migrated_database_url)
    fake.pages = [transaction("PAID")]

    report = reconcile(migrated_database_url, attempt, fake)
    detail = read(client, operator, sale)

    assert [request.url.path for request in fake.queries()] == [f"/transaction/{TRANSACTION_ID}"]
    assert report.result is ReconciliationResult.CONFIRMED
    assert (report.found, report.applied) == (1, 1)
    assert detail["status"] == "paid"
    assert detail["confirmed_amount_cents"] == AMOUNT


def test_a_webhook_and_a_query_for_the_same_phone_payment_count_once(
    client: TestClient, migrated_database_url: str, fake: FakePey
) -> None:
    _sale, attempt, _operator = pending_phone_request(client, migrated_database_url)
    fake.pages = [transaction("PAID")]

    deliver(client, push_paid_event(attempt), Delivery(message_id="msg_push_query"))
    report = reconcile(migrated_database_url, attempt, fake)

    assert (report.result, report.found, report.duplicates) == (
        ReconciliationResult.CONFIRMED,
        1,
        1,
    )
    assert scalar(migrated_database_url, "SELECT count(*) FROM transactions") == 1


def test_a_different_amount_goes_to_review_instead_of_confirming(
    client: TestClient, migrated_database_url: str
) -> None:
    sale, attempt, operator = pending_phone_request(client, migrated_database_url)

    deliver(
        client,
        push_paid_event(attempt, amount=AMOUNT / 100 + 2.5),
        Delivery(message_id="msg_push_fee"),
    )
    detail = read(client, operator, sale)

    assert detail["status"] == "review"
    assert [item["reason"] for item in detail["exceptions"]] == ["amount_mismatch"]


def test_a_pending_transaction_is_not_read_as_a_rejection(
    client: TestClient, migrated_database_url: str, fake: FakePey
) -> None:
    sale, attempt, operator = pending_phone_request(client, migrated_database_url)
    fake.pages = [transaction("PENDING")]

    report = reconcile(migrated_database_url, attempt, fake)
    detail = read(client, operator, sale)

    assert report.result is ReconciliationResult.NO_EVIDENCE
    assert detail["status"] == "open"
    assert [(item["status"], item["failure_code"]) for item in detail["attempts"]] == [
        ("pending", None)
    ]


@pytest.mark.parametrize(
    ("page", "problem"),
    [
        ((404, TRANSACTION_FIXTURE["responses"]["404"]["default"]), "not_found"),
        ((429, TRANSACTION_FIXTURE["responses"]["429"]["default"]), "rate_limited"),
        ((500, TRANSACTION_FIXTURE["responses"]["500"]["default"]), "server_error"),
        ((200, "not json"), "invalid_response"),
        (
            (200, {**TRANSACTION_FIXTURE["responses"]["200"]["default"], "status": "PAID"}),
            "invalid_response",
        ),
    ],
)
def test_an_unanswered_query_keeps_the_doubt_and_never_fails_the_request(
    client: TestClient,
    migrated_database_url: str,
    fake: FakePey,
    page: tuple[int, object],
    problem: str,
) -> None:
    sale, attempt, operator = pending_phone_request(client, migrated_database_url)
    fake.pages = [page]

    report = reconcile(migrated_database_url, attempt, fake)
    detail = read(client, operator, sale)

    assert report.result is ReconciliationResult.UNCERTAIN
    assert report.problem is not None
    assert report.problem.value == problem
    assert [(item["status"], item["failure_code"]) for item in detail["attempts"]] == [
        ("pending", None)
    ]
    assert [request.method for request in fake.requests] == ["POST", "GET"]


def test_a_lost_query_answer_never_sends_a_new_request_to_the_phone(
    client: TestClient, migrated_database_url: str, fake: FakePey
) -> None:
    _sale, attempt, _operator = pending_phone_request(client, migrated_database_url)
    fake.error = httpx2.ReadTimeout("query lost")

    report = reconcile(migrated_database_url, attempt, fake)

    assert report.result is ReconciliationResult.UNCERTAIN
    assert [request.method for request in fake.requests] == ["POST", "GET"]


def test_an_expired_unpaid_phone_request_is_verified_and_allows_a_new_attempt(
    client: TestClient, migrated_database_url: str, fake: FakePey
) -> None:
    sale, attempt, operator = pending_phone_request(client, migrated_database_url)
    execute(
        migrated_database_url,
        "UPDATE payment_attempts SET expires_at = now() - interval '1 minute'",
    )
    read(client, operator, sale)
    fake.pages = [transaction("PENDING")]

    report = reconcile(migrated_database_url, attempt, fake)
    fake.body = {**PUSH_CREATED, "transactionId": "01J5KXYZ1234567890ABCE"}
    retried = request_phone(
        client, operator, sale["id"], {"method": "phone", "phone_number": CONSENTED}
    )

    assert report.result is ReconciliationResult.VERIFIED
    assert retried.status_code == HTTPStatus.CREATED
    assert retried.json()["previous_attempt_id"] == attempt["id"]


def test_new_phone_requests_over_the_quota_get_429_without_reaching_pey(
    migrated_database_url: str, fake: FakePey
) -> None:
    settings = confirmation_settings(migrated_database_url, attempt_creation_quota=1)
    with start_client(settings, migrated_database_url, fake.provider()) as client:
        first, operator = open_sale(client, migrated_database_url)
        second = create_sale(client, operator, first["merchant_id"], amount_cents=AMOUNT).json()
        allowed = request_phone(
            client, operator, first["id"], {"method": "phone", "phone_number": CONSENTED}
        )
        refused = request_phone(
            client, operator, second["id"], {"method": "phone", "phone_number": CONSENTED}
        )

    assert allowed.status_code == HTTPStatus.CREATED
    assert refused.status_code == HTTPStatus.TOO_MANY_REQUESTS
    assert len(posted(fake)) == 1


def test_phone_requests_can_be_enabled_outside_tests_once_payments_are_verifiable() -> None:
    settings = demo_list_settings("production", CONSENTED, provider="pey")

    assert settings.phone_request_numbers == frozenset({CONSENTED})


def test_the_jobs_runner_verifies_an_expired_phone_request(migrated_database_url: str) -> None:
    settings = confirmation_settings(migrated_database_url)
    with start_client(settings, migrated_database_url) as client:
        sale, _attempt, operator = pending_phone_request(client, migrated_database_url)
        execute(
            migrated_database_url,
            "UPDATE payment_attempts SET expires_at = now() - interval '1 minute'",
        )
        read(client, operator, sale)

        batch = run_sales(migrated_database_url, "run-jobs")
        detail = read(client, operator, sale)

    assert batch.returncode == 0
    assert "verified unpaid: 1" in batch.stdout
    assert "exhausted: 0" in batch.stdout
    assert detail["attempts"][0]["verified_at"] is not None
    assert detail["attempts"][0]["next_action"] == "new_attempt"


def test_a_payment_event_before_the_phone_request_answer_ends_confirmed(
    migrated_database_url: str, fake: FakePey
) -> None:
    provider = EarlyPaymentPey(fake, migrated_database_url)
    settings = confirmation_settings(migrated_database_url)
    with start_client(settings, migrated_database_url, provider) as client:
        sale, attempt, operator = pending_phone_request(client, migrated_database_url)
        detail = read(client, operator, sale)

    assert attempt["provider_request_id"] == TRANSACTION_ID
    assert detail["status"] == "paid"
    assert detail["attempts"][0]["status"] == "paid"
    assert [(item["reason"], item["resolved_at"] is not None) for item in detail["exceptions"]] == [
        ("unassociated", True)
    ]
    assert scalar(migrated_database_url, "SELECT status FROM webhook_events") == "applied"
    assert scalar(migrated_database_url, "SELECT count(*) FROM transactions") == 1


def test_a_link_attempt_is_never_queried_as_another_channel(
    client: TestClient, migrated_database_url: str, fake: FakePey
) -> None:
    sale, operator = open_sale(client, migrated_database_url)
    link = request_phone(client, operator, sale["id"], {"method": "link"}).json()
    execute(
        migrated_database_url,
        "UPDATE payment_attempts SET provider = 'pey', provider_request_id = :id",
        {"id": TRANSACTION_ID},
    )

    report = reconcile(migrated_database_url, link, fake)

    assert report.result is ReconciliationResult.NOT_QUERYABLE
    assert fake.queries() == []
