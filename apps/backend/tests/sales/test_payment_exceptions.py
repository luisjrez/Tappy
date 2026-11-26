import json
import uuid
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tappy.payments.provider import PaymentEvidence, ProviderName
from tappy.platform.database import Database
from tappy.sales.evidence import apply_evidence
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
SHORT = 25000
OVER = 31000


@pytest.fixture
def client(migrated_database_url: str) -> Iterator[TestClient]:
    provider = FakePey().provider()
    with start_client(settings_for(migrated_database_url), migrated_database_url, provider) as c:
        yield c


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


def send(client: TestClient, sale: dict[str, Any], message_id: str, **changes: object) -> int:
    attempt = sale["attempts"][0]
    event: dict[str, object] = {
        "type": "codi.qr.payment_received",
        "amount": 300.0,
        "bankAccountId": RECEIVER_A["provider_account_id"],
        "codiQrId": attempt["provider_request_id"],
        "datePaid": PAID_AT,
        "transactionId": f"TX-{message_id}",
        "metadata": {"tappy_attempt_id": attempt["id"]},
    }
    event.update(changes)
    body = json.dumps({k: v for k, v in event.items() if v is not None}).encode()
    return deliver(client, body, Delivery(message_id=message_id)).status_code


def detail(client: TestClient, headers: dict[str, str], sale: dict[str, Any]) -> dict[str, Any]:
    read: dict[str, Any] = client.get(f"/sales/{sale['id']}", headers=headers).json()
    return read


def event_status(database_url: str, message_id: str) -> object:
    return scalar(
        database_url,
        "SELECT status FROM webhook_events WHERE provider_event_id = :id",
        {"id": message_id},
    )


def test_a_short_own_transfer_is_kept_and_opens_an_incident_without_covering_the_sale(
    client: TestClient, migrated_database_url: str
) -> None:
    sale, operator_a = pending_qr(client, migrated_database_url)

    status = send(client, sale, "msg_short", amount=250.0)
    read = detail(client, operator_a, sale)

    assert status == HTTPStatus.NO_CONTENT
    assert read["status"] == "review"
    assert read["confirmed_amount_cents"] == SHORT
    assert [transfer["amount_cents"] for transfer in read["transfers"]] == [SHORT]
    assert read["exceptions"] == [
        {
            "reason": "amount_mismatch",
            "expected_amount_cents": AMOUNT,
            "received_amount_cents": SHORT,
            "created_at": read["exceptions"][0]["created_at"],
            "resolved_at": None,
        }
    ]
    assert read["attempts"][0]["status"] != "paid"
    assert event_status(migrated_database_url, "msg_short") == "review"


def test_an_over_payment_is_also_an_incident(
    client: TestClient, migrated_database_url: str
) -> None:
    sale, operator_a = pending_qr(client, migrated_database_url)

    send(client, sale, "msg_over", amount=310.0)
    read = detail(client, operator_a, sale)

    assert read["status"] == "review"
    assert read["exceptions"][0]["reason"] == "amount_mismatch"
    assert read["confirmed_amount_cents"] == OVER


@pytest.mark.parametrize("account", ["bank-account-of-someone-else", None])
def test_money_to_another_account_never_counts_for_the_merchant(
    client: TestClient, migrated_database_url: str, account: str | None
) -> None:
    sale, operator_a = pending_qr(client, migrated_database_url)

    send(client, sale, "msg_foreign", bankAccountId=account)
    read = detail(client, operator_a, sale)

    assert read["status"] == "open"
    assert read["confirmed_amount_cents"] == 0
    assert read["transfers"] == []
    assert [exception["reason"] for exception in read["exceptions"]] == ["receiver_mismatch"]
    assert scalar(migrated_database_url, "SELECT count(*) FROM transactions") == 0
    assert event_status(migrated_database_url, "msg_foreign") == "review"


@pytest.mark.parametrize(
    "changes",
    [{"codiQrId": "UNKNOWN-QR"}, {"metadata": {"tappy_attempt_id": str(uuid.uuid4())}}],
)
def test_unassociable_evidence_stays_in_review_without_approximate_association(
    client: TestClient, migrated_database_url: str, changes: dict[str, object]
) -> None:
    sale, operator_a = pending_qr(client, migrated_database_url)

    send(client, sale, "msg_unknown", **changes)
    execute(migrated_database_url, "UPDATE webhook_events SET status = 'received'")
    processed = run_sales(migrated_database_url, "process-events")
    listed = run_sales(migrated_database_url, "exceptions")
    read = detail(client, operator_a, sale)

    assert read["status"] == "open"
    assert read["exceptions"] == []
    assert read["transfers"] == []
    assert (
        scalar(
            migrated_database_url,
            "SELECT reason || ':' || coalesce(sale_id::text, 'none') FROM payment_exceptions",
        )
        == "unassociated:none"
    )
    assert "1 in review" in processed.stdout
    assert "unassociated" in listed.stdout
    assert "msg_unknown" in listed.stdout
    assert event_status(migrated_database_url, "msg_unknown") == "review"


def test_a_transfer_id_already_used_with_other_data_opens_an_incident(
    client: TestClient, migrated_database_url: str
) -> None:
    sale, operator_a = pending_qr(client, migrated_database_url)
    send(client, sale, "msg_e1", transactionId="TX-SHARED")

    send(client, sale, "msg_e2", transactionId="TX-SHARED", amount=310.0)
    read = detail(client, operator_a, sale)

    assert read["status"] == "paid"
    assert read["confirmed_amount_cents"] == AMOUNT
    assert [exception["reason"] for exception in read["exceptions"]] == ["conflicting_transfer"]
    assert event_status(migrated_database_url, "msg_e2") == "review"


@pytest.mark.parametrize(
    "changes", [{"transactionId": None}, {"datePaid": "yesterday"}, {"amount": None}]
)
def test_incomplete_evidence_for_the_attempt_goes_to_review(
    client: TestClient, migrated_database_url: str, changes: dict[str, object]
) -> None:
    sale, operator_a = pending_qr(client, migrated_database_url)

    send(client, sale, "msg_incomplete", **changes)
    read = detail(client, operator_a, sale)

    assert read["status"] == "open"
    assert read["transfers"] == []
    assert [exception["reason"] for exception in read["exceptions"]] == ["incomplete_evidence"]


def test_reprocessing_an_incident_never_duplicates_it_or_the_money(
    client: TestClient, migrated_database_url: str
) -> None:
    sale, operator_a = pending_qr(client, migrated_database_url)
    send(client, sale, "msg_short", amount=250.0)
    execute(migrated_database_url, "UPDATE webhook_events SET status = 'received'")

    run_sales(migrated_database_url, "process-events")
    read = detail(client, operator_a, sale)

    assert len(read["exceptions"]) == 1
    assert read["confirmed_amount_cents"] == SHORT
    assert scalar(migrated_database_url, "SELECT count(*) FROM transactions") == 1


def test_a_sale_in_review_accepts_no_new_attempts(
    client: TestClient, migrated_database_url: str
) -> None:
    sale, operator_a = pending_qr(client, migrated_database_url)
    send(client, sale, "msg_short", amount=250.0)

    retried = client.post(
        f"/sales/{sale['id']}/attempts",
        json={"method": "qr"},
        headers={**operator_a, IDEMPOTENCY_HEADER: str(uuid.uuid4())},
    )

    assert retried.status_code == HTTPStatus.CONFLICT


def test_reprocessing_keeps_the_event_in_review(
    client: TestClient, migrated_database_url: str
) -> None:
    sale, _ = pending_qr(client, migrated_database_url)
    send(client, sale, "msg_short", amount=250.0)
    execute(migrated_database_url, "UPDATE webhook_events SET status = 'received'")

    run_sales(migrated_database_url, "process-events")

    assert event_status(migrated_database_url, "msg_short") == "review"


def test_incidents_without_an_event_are_not_duplicated(migrated_database_url: str) -> None:
    evidence = PaymentEvidence(
        provider=ProviderName.PEY,
        environment="test",
        provider_request_id="UNKNOWN-QR",
        attempt_id=None,
        provider_transaction_id="TX-QUERY",
        amount_cents=AMOUNT,
        receiver_account=str(RECEIVER_A["provider_account_id"]),
        occurred_at=datetime.fromtimestamp(PAID_AT, UTC),
    )
    database = Database.from_settings(build_settings(database_url=migrated_database_url))
    other = replace(evidence, provider_transaction_id="TX-OTHER-QUERY")
    try:
        for item in (evidence, evidence, other):
            with database.transaction() as session:
                apply_evidence(session, item, None, datetime.now(UTC))
    finally:
        database.dispose()

    assert scalar(migrated_database_url, "SELECT count(*) FROM payment_exceptions") == len(
        {evidence.provider_transaction_id, other.provider_transaction_id}
    )
