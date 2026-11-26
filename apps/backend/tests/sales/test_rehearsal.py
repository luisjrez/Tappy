import json
import uuid
from http import HTTPStatus
from typing import Any

from fastapi.testclient import TestClient

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
    app_client,
    bearer,
    create_sale,
    ready_merchant,
    start_client,
)
from tests.support import build_settings, scalar

PAID_AT = 1795000000
PAID_DAY = "2026-11-18"
TRANSACTION = "01M3QR8H0RH0XBCKYYD242YXNV"
ENVIRONMENT = "test"


def paid_page() -> tuple[int, object]:
    item = {
        "id": TRANSACTION,
        "status": "PAID",
        "amount": AMOUNT / 100,
        "currency": "MXN",
        "paymentMethod": "CODI",
        "dateCreated": PAID_AT,
        "datePaid": PAID_AT,
    }
    return 200, {"items": [item], "nextToken": None}


def payment_event(sale: dict[str, Any]) -> bytes:
    attempt = sale["attempts"][0]
    event = {
        "type": "codi.qr.payment_received",
        "amount": AMOUNT / 100,
        "apiKeyId": "01HZZSYNTHETICAPIKEY0000",
        "bankAccountId": RECEIVER_A["provider_account_id"],
        "codiQrId": attempt["provider_request_id"],
        "concept": "",
        "datePaid": PAID_AT,
        "numRef": "0",
        "transactionId": TRANSACTION,
        "metadata": {"tappy_attempt_id": attempt["id"], "tappy_reference": sale["reference"]},
    }
    return json.dumps(event, separators=(",", ":")).encode()


def request_qr(client: TestClient, headers: dict[str, str], sale_id: str, key: str) -> int:
    return client.post(
        f"/sales/{sale_id}/attempts",
        json={"method": "qr"},
        headers={**headers, IDEMPOTENCY_HEADER: key},
    ).status_code


def reconcile(
    database_url: str, attempt_id: str, fake: FakePey
) -> tuple[ReconciliationResult, int]:
    database = Database.from_settings(build_settings(database_url=database_url))
    try:
        report = reconcile_attempt(
            database, uuid.UUID(attempt_id), fake.provider(), ENVIRONMENT, SystemClock()
        )
    finally:
        database.dispose()
    return report.result, report.applied


def test_a_rehearsal_with_lost_responses_a_restart_and_repeated_evidence_keeps_one_reception(
    migrated_database_url: str,
) -> None:
    settings = settings_for(migrated_database_url)
    issuing = FakePey()
    with start_client(settings, migrated_database_url, issuing.provider()) as before_restart:
        merchant = ready_merchant(
            before_restart, migrated_database_url, "Tienda Demo A", OPERATOR_A
        )
        operator = bearer(before_restart, OPERATOR_A)
        sale = create_sale(before_restart, operator, merchant, amount_cents=AMOUNT).json()
        key = str(uuid.uuid4())
        first = request_qr(before_restart, operator, sale["id"], key)
        retried = request_qr(before_restart, operator, sale["id"], key)
        pending = before_restart.get(f"/sales/{sale['id']}", headers=operator).json()

    querying = FakePey(pages=[paid_page()])
    with app_client(settings, querying.provider()) as after_restart:
        body = payment_event(pending)
        deliveries = [
            deliver(after_restart, body, Delivery(message_id=message_id)).status_code
            for message_id in ("msg_rehearsal_1", "msg_rehearsal_1", "msg_rehearsal_2")
        ]
        queried = reconcile(migrated_database_url, pending["attempts"][0]["id"], querying)
        detail = after_restart.get(f"/sales/{sale['id']}", headers=operator).json()
        history = after_restart.get("/sales", headers=operator).json()
        summary = after_restart.get(
            f"/merchants/{merchant}/summary/daily", headers=operator, params={"date": PAID_DAY}
        ).json()

    assert (first, retried) == (HTTPStatus.CREATED, HTTPStatus.OK)
    assert len([request for request in issuing.requests if request.method == "POST"]) == 1
    assert pending["status"] == "open"
    assert pending["attempts"][0]["status"] == "pending"
    assert deliveries == [HTTPStatus.NO_CONTENT] * 3
    assert queried == (ReconciliationResult.CONFIRMED, 0)
    assert detail["status"] == "paid"
    assert detail["confirmed_amount_cents"] == AMOUNT
    assert [transfer["provider_transaction_id"] for transfer in detail["transfers"]] == [
        TRANSACTION
    ]
    assert [(item["id"], item["status"]) for item in history["items"]] == [(sale["id"], "paid")]
    assert (summary["received_amount_cents"], summary["transfer_count"]) == (AMOUNT, 1)
    assert (summary["covered_sale_count"], summary["open_exception_count"]) == (1, 0)
    assert detail["exceptions"] == []
    assert scalar(migrated_database_url, "SELECT count(*) FROM transactions") == 1
    assert (
        scalar(
            migrated_database_url, "SELECT string_agg(DISTINCT environment, ',') FROM transactions"
        )
        == ENVIRONMENT
    )
    assert (
        scalar(
            migrated_database_url,
            "SELECT string_agg(status || ':' || environment, ',' ORDER BY provider_event_id) "
            "FROM webhook_events",
        )
        == "applied:test,duplicate:test"
    )
