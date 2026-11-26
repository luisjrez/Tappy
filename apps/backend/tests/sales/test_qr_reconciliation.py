import json
import uuid
from collections.abc import Iterator
from http import HTTPStatus
from typing import Any

import httpx2
import pytest
from fastapi.testclient import TestClient

from tappy.payments.provider import QrProvider
from tappy.platform.clock import SystemClock
from tappy.platform.database import Database
from tappy.sales.reconciliation import ReconciliationResult, reconcile_attempt
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
from tests.support import build_settings, execute, run_sales, scalar

PAID_AT = 1795000000
TRANSACTION = "01M3QR8H0RH0XBCKYYD242YXNV"
ENVIRONMENT = "test"
USAGE_ERROR = 2
SHORT = 25000


def paid(transaction_id: str = TRANSACTION, amount: float = 300.0) -> dict[str, object]:
    return {
        "id": transaction_id,
        "status": "PAID",
        "amount": amount,
        "currency": "MXN",
        "paymentMethod": "CODI",
        "dateCreated": PAID_AT,
        "datePaid": PAID_AT,
    }


def page(*items: dict[str, object], next_token: str | None = None) -> tuple[int, object]:
    return 200, {"items": list(items), "nextToken": next_token}


@pytest.fixture
def fake() -> FakePey:
    return FakePey()


@pytest.fixture
def client(migrated_database_url: str, fake: FakePey) -> Iterator[TestClient]:
    settings = settings_for(migrated_database_url)
    with start_client(settings, migrated_database_url, fake.provider()) as started:
        yield started


def pending_qr(client: TestClient, database_url: str) -> tuple[dict[str, Any], dict[str, str]]:
    merchant_a = ready_merchant(client, database_url, "Tienda Demo A", OPERATOR_A)
    operator_a = bearer(client, OPERATOR_A)
    sale = create_sale(client, operator_a, merchant_a, amount_cents=AMOUNT).json()
    client.post(
        f"/sales/{sale['id']}/attempts",
        json={"method": "qr"},
        headers={**operator_a, IDEMPOTENCY_HEADER: str(uuid.uuid4())},
    )
    return client.get(f"/sales/{sale['id']}", headers=operator_a).json(), operator_a


def reconcile(
    database_url: str, sale: dict[str, Any], provider: QrProvider
) -> tuple[ReconciliationResult, int]:
    database = Database.from_settings(build_settings(database_url=database_url))
    try:
        report = reconcile_attempt(
            database, uuid.UUID(sale["attempts"][0]["id"]), provider, ENVIRONMENT, SystemClock()
        )
    finally:
        database.dispose()
    return report.result, report.applied


def detail(client: TestClient, headers: dict[str, str], sale: dict[str, Any]) -> dict[str, Any]:
    read: dict[str, Any] = client.get(f"/sales/{sale['id']}", headers=headers).json()
    return read


def transfer_count(database_url: str) -> object:
    return scalar(database_url, "SELECT count(*) FROM transactions")


def webhook(client: TestClient, sale: dict[str, Any]) -> int:
    attempt = sale["attempts"][0]
    event = {
        "type": "codi.qr.payment_received",
        "amount": 300.0,
        "bankAccountId": RECEIVER_A["provider_account_id"],
        "codiQrId": attempt["provider_request_id"],
        "datePaid": PAID_AT,
        "transactionId": TRANSACTION,
        "metadata": {"tappy_attempt_id": attempt["id"]},
    }
    body = json.dumps(event, separators=(",", ":")).encode()
    return deliver(client, body, Delivery(message_id="msg_reconcile")).status_code


def test_evidence_on_a_later_page_confirms_the_sale_once(
    client: TestClient, migrated_database_url: str, fake: FakePey
) -> None:
    sale, operator_a = pending_qr(client, migrated_database_url)
    other = {**paid("TX-PENDING"), "status": "PENDING"}
    fake.pages = [page(other, next_token="token-2"), page(paid()), page(other), page(paid())]

    first = reconcile(migrated_database_url, sale, fake.provider())
    repeated = reconcile(migrated_database_url, sale, fake.provider())
    read = detail(client, operator_a, sale)

    assert first == (ReconciliationResult.CONFIRMED, 1)
    assert repeated == (ReconciliationResult.CONFIRMED, 0)
    assert read["status"] == "paid"
    assert read["confirmed_amount_cents"] == AMOUNT
    assert read["attempts"][0]["status"] == "paid"
    assert [item["provider_transaction_id"] for item in read["transfers"]] == [TRANSACTION]
    assert read["transfers"][0]["masked_account"].endswith(str(RECEIVER_A["clabe"])[-4:])
    assert transfer_count(migrated_database_url) == 1


@pytest.mark.parametrize(
    "answer",
    [page(), page({**paid(), "status": "PENDING", "datePaid": None})],
    ids=["empty", "only-pending"],
)
def test_no_evidence_keeps_the_payment_unconfirmed(
    client: TestClient, migrated_database_url: str, fake: FakePey, answer: tuple[int, object]
) -> None:
    sale, operator_a = pending_qr(client, migrated_database_url)
    fake.pages = [answer]

    result = reconcile(migrated_database_url, sale, fake.provider())
    read = detail(client, operator_a, sale)

    assert result == (ReconciliationResult.NO_EVIDENCE, 0)
    assert read["status"] == "open"
    assert read["attempts"][0]["status"] == "pending"
    assert read["attempts"][0]["failure_code"] is None
    assert transfer_count(migrated_database_url) == 0


@pytest.mark.parametrize(
    "fake_answer",
    [
        FakePey(pages=[(500, {})]),
        FakePey(pages=[(429, {})]),
        FakePey(pages=[(404, {"error": {"type": "NOT_FOUND"}})]),
        FakePey(error=httpx2.ReadTimeout("slow")),
    ],
    ids=["server-error", "rate-limited", "not-found", "timeout"],
)
def test_an_uncertain_answer_keeps_a_reconciling_attempt_waiting(
    client: TestClient, migrated_database_url: str, fake_answer: FakePey
) -> None:
    sale, operator_a = pending_qr(client, migrated_database_url)
    execute(migrated_database_url, "UPDATE payment_attempts SET status = 'reconciling'")
    execute(
        migrated_database_url,
        "INSERT INTO reconciliation_jobs (id, attempt_id, reason, status, run_at, created_at) "
        "SELECT gen_random_uuid(), id, 'timeout', 'pending', now(), now() FROM payment_attempts",
    )

    result = reconcile(migrated_database_url, sale, fake_answer.provider())
    read = detail(client, operator_a, sale)

    assert result == (ReconciliationResult.UNCERTAIN, 0)
    assert read["status"] == "open"
    assert read["attempts"][0]["status"] == "reconciling"
    assert scalar(migrated_database_url, "SELECT status FROM reconciliation_jobs") == "pending"


@pytest.mark.parametrize("reason", ["timeout", "duplicate_provider_id"])
def test_a_confirmed_reconciliation_closes_its_pending_job(
    client: TestClient, migrated_database_url: str, fake: FakePey, reason: str
) -> None:
    sale, _ = pending_qr(client, migrated_database_url)
    execute(migrated_database_url, "UPDATE payment_attempts SET status = 'reconciling'")
    execute(
        migrated_database_url,
        "INSERT INTO reconciliation_jobs (id, attempt_id, reason, status, run_at, created_at) "
        "SELECT gen_random_uuid(), id, :reason, 'pending', now(), now() FROM payment_attempts",
        {"reason": reason},
    )
    fake.pages = [page(paid())]

    result = reconcile(migrated_database_url, sale, fake.provider())

    assert result == (ReconciliationResult.CONFIRMED, 1)
    assert scalar(migrated_database_url, "SELECT status FROM reconciliation_jobs") == "done"
    assert run_sales(migrated_database_url, "reconciliations").stdout.strip() == (
        "No open reconciliations"
    )


def test_a_webhook_then_a_query_for_the_same_transfer_count_once(
    client: TestClient, migrated_database_url: str, fake: FakePey
) -> None:
    sale, operator_a = pending_qr(client, migrated_database_url)
    fake.pages = [page(paid())]

    delivered = webhook(client, sale)
    result = reconcile(migrated_database_url, sale, fake.provider())
    read = detail(client, operator_a, sale)

    assert delivered == HTTPStatus.NO_CONTENT
    assert result == (ReconciliationResult.CONFIRMED, 0)
    assert read["confirmed_amount_cents"] == AMOUNT
    assert len(read["transfers"]) == 1
    assert transfer_count(migrated_database_url) == 1


def test_a_query_then_a_webhook_for_the_same_transfer_count_once(
    client: TestClient, migrated_database_url: str, fake: FakePey
) -> None:
    sale, operator_a = pending_qr(client, migrated_database_url)
    fake.pages = [page(paid())]

    result = reconcile(migrated_database_url, sale, fake.provider())
    delivered = webhook(client, sale)
    read = detail(client, operator_a, sale)

    assert result == (ReconciliationResult.CONFIRMED, 1)
    assert delivered == HTTPStatus.NO_CONTENT
    assert scalar(migrated_database_url, "SELECT status FROM webhook_events") == "duplicate"
    assert read["status"] == "paid"
    assert read["confirmed_amount_cents"] == AMOUNT
    assert transfer_count(migrated_database_url) == 1


def test_a_different_amount_found_by_query_goes_to_review(
    client: TestClient, migrated_database_url: str, fake: FakePey
) -> None:
    sale, operator_a = pending_qr(client, migrated_database_url)
    fake.pages = [page(paid(amount=SHORT / 100))]

    result = reconcile(migrated_database_url, sale, fake.provider())
    read = detail(client, operator_a, sale)

    assert result == (ReconciliationResult.REVIEW, 0)
    assert read["status"] == "review"
    assert read["confirmed_amount_cents"] == SHORT
    assert [item["reason"] for item in read["exceptions"]] == ["amount_mismatch"]


def test_an_attempt_without_a_qr_id_cannot_be_queried(
    client: TestClient, migrated_database_url: str, fake: FakePey
) -> None:
    sale, _ = pending_qr(client, migrated_database_url)
    execute(
        migrated_database_url,
        "UPDATE payment_attempts SET status = 'reconciling', provider_request_id = NULL",
    )

    result = reconcile(migrated_database_url, sale, fake.provider())

    assert result == (ReconciliationResult.NOT_QUERYABLE, 0)
    assert fake.queries() == []


def test_the_command_reconciles_one_attempt(client: TestClient, migrated_database_url: str) -> None:
    sale, _ = pending_qr(client, migrated_database_url)
    attempt_id = sale["attempts"][0]["id"]
    execute(migrated_database_url, "UPDATE payment_attempts SET provider = 'simulated'")

    found = run_sales(migrated_database_url, "reconcile", attempt_id)
    unknown = run_sales(migrated_database_url, "reconcile", str(uuid.uuid4()))
    malformed = run_sales(migrated_database_url, "reconcile", "not-a-uuid")

    assert found.returncode == 0
    assert f"attempt: {attempt_id}" in found.stdout
    assert f"sale reference: {sale['reference']}" in found.stdout
    assert "result: no payment evidence found; the payment stays unconfirmed" in found.stdout
    assert "attempt status: pending" in found.stdout
    assert unknown.returncode == 1
    assert "Attempt not found" in unknown.stderr
    assert malformed.returncode == USAGE_ERROR
