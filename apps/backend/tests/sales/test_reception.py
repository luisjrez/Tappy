import json
import time
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.payments.pey_support import FakePey
from tests.payments.webhook_support import OTHER_SECRET, Delivery, deliver, settings_for
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
from tests.support import execute, run_sales, scalar

PAID_AT = 1795000000
TRANSACTION = "01M3QR8H0RH0XBCKYYD242YXNV"


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


def payment_event(sale: dict[str, Any], **changes: object) -> dict[str, object]:
    attempt = sale["attempts"][0]
    event: dict[str, object] = {
        "type": "codi.qr.payment_received",
        "amount": 300.0,
        "apiKeyId": "01HZZSYNTHETICAPIKEY0000",
        "bankAccountId": RECEIVER_A["provider_account_id"],
        "codiQrId": attempt["provider_request_id"],
        "concept": "",
        "datePaid": PAID_AT,
        "numRef": "0",
        "transactionId": TRANSACTION,
        "metadata": {"tappy_attempt_id": attempt["id"], "tappy_reference": sale["reference"]},
    }
    event.update(changes)
    return {key: value for key, value in event.items() if value is not None}


def send(client: TestClient, event: object, message_id: str = "msg_reception_1") -> int:
    body = json.dumps(event, separators=(",", ":")).encode()
    return deliver(client, body, Delivery(message_id=message_id)).status_code


def detail(client: TestClient, headers: dict[str, str], sale: dict[str, Any]) -> dict[str, Any]:
    read: dict[str, Any] = client.get(f"/sales/{sale['id']}", headers=headers).json()
    return read


def event_status(database_url: str) -> object:
    return scalar(database_url, "SELECT status FROM webhook_events")


def test_exact_evidence_confirms_the_transfer_and_the_sale(
    client: TestClient, migrated_database_url: str
) -> None:
    sale, operator_a = pending_qr(client, migrated_database_url)

    status = send(client, payment_event(sale))
    read = detail(client, operator_a, sale)

    assert status == HTTPStatus.NO_CONTENT
    assert read["status"] == "paid"
    assert read["confirmed_amount_cents"] == AMOUNT
    assert read["transfers"] == [
        {
            "provider_transaction_id": TRANSACTION,
            "amount_cents": AMOUNT,
            "occurred_at": datetime.fromtimestamp(PAID_AT, UTC).isoformat().replace("+00:00", "Z"),
            "received_at": read["transfers"][0]["received_at"],
            "beneficiary_name": RECEIVER_A["beneficiary_name"],
            "masked_account": "**************6782",
        }
    ]
    assert read["attempts"][0]["status"] == "paid"
    assert event_status(migrated_database_url) == "applied"
    assert scalar(migrated_database_url, "SELECT count(*) FROM transactions") == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"bankAccountId": None},
        {"bankAccountId": "bank-account-of-someone-else"},
        {"amount": 300.01},
        {"amount": 300.005},
        {"amount": None},
        {"codiQrId": "UNKNOWN-QR"},
        {"transactionId": None},
        {"metadata": {"tappy_attempt_id": str(uuid.uuid4())}},
        {"type": "codi.pn.payment_received"},
        {"datePaid": None},
    ],
)
def test_insufficient_evidence_never_marks_the_sale_received(
    client: TestClient, migrated_database_url: str, changes: dict[str, object]
) -> None:
    sale, operator_a = pending_qr(client, migrated_database_url)

    status = send(client, payment_event(sale, **changes))
    read = detail(client, operator_a, sale)

    assert status == HTTPStatus.NO_CONTENT
    assert read["status"] == "open"
    assert read["confirmed_amount_cents"] == 0
    assert read["transfers"] == []
    assert read["attempts"][0]["status"] == "pending"
    assert event_status(migrated_database_url) == "unmatched"
    assert scalar(migrated_database_url, "SELECT count(*) FROM transactions") == 0


def test_an_invalid_signature_leaves_the_pending_attempt_untouched(
    client: TestClient, migrated_database_url: str
) -> None:
    sale, operator_a = pending_qr(client, migrated_database_url)
    body = json.dumps(payment_event(sale)).encode()

    response = deliver(client, body, Delivery(secret=OTHER_SECRET))
    read = detail(client, operator_a, sale)

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert read["status"] == "open"
    assert read["attempts"][0]["status"] == "pending"


FAULT = """
CREATE FUNCTION fail_event_updates() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'induced failure'; END; $$;
CREATE TRIGGER fail_event_updates BEFORE UPDATE ON webhook_events
FOR EACH ROW EXECUTE FUNCTION fail_event_updates();
"""


def test_a_failure_inside_the_application_leaves_no_partial_state_and_reprocessing_completes(
    client: TestClient, migrated_database_url: str
) -> None:
    sale, operator_a = pending_qr(client, migrated_database_url)
    execute(migrated_database_url, FAULT)

    stored = send(client, payment_event(sale))
    during = detail(client, operator_a, sale)
    transfers_during = scalar(migrated_database_url, "SELECT count(*) FROM transactions")
    status_during = event_status(migrated_database_url)
    execute(migrated_database_url, "DROP TRIGGER fail_event_updates ON webhook_events")
    processed = run_sales(migrated_database_url, "process-events")
    after = detail(client, operator_a, sale)
    again = run_sales(migrated_database_url, "process-events")

    assert stored == HTTPStatus.NO_CONTENT
    assert during["status"] == "open"
    assert during["transfers"] == []
    assert during["attempts"][0]["status"] == "pending"
    assert transfers_during == 0
    assert status_during == "received"
    assert processed.returncode == 0, processed.stderr
    assert "1 event applied, 0 unmatched" in processed.stdout
    assert after["status"] == "paid"
    assert after["confirmed_amount_cents"] == AMOUNT
    assert "0 events applied, 0 unmatched" in again.stdout
    assert scalar(migrated_database_url, "SELECT count(*) FROM transactions") == 1


def test_the_operations_command_applies_stored_events(
    client: TestClient, migrated_database_url: str
) -> None:
    sale, operator_a = pending_qr(client, migrated_database_url)
    body = json.dumps(payment_event(sale)).encode()
    execute(
        migrated_database_url,
        "INSERT INTO webhook_events (id, provider, environment, provider_event_id, event_type, "
        "payload, payload_digest, signed_at, status, received_at) VALUES (gen_random_uuid(), "
        "'pey', 'test', 'msg_stored', 'codi.qr.payment_received', :body, 'digest', now(), "
        "'received', now())",
        {"body": body},
    )

    processed = run_sales(migrated_database_url, "process-events")

    assert "1 event applied, 0 unmatched" in processed.stdout
    assert detail(client, operator_a, sale)["status"] == "paid"


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE transactions SET amount_cents = 1",
        "DELETE FROM transactions",
        "TRUNCATE transactions CASCADE",
    ],
)
def test_transfers_cannot_be_changed_or_removed_once_recorded(
    client: TestClient, migrated_database_url: str, statement: str
) -> None:
    sale, _ = pending_qr(client, migrated_database_url)
    send(client, payment_event(sale))

    with pytest.raises(Exception, match="recorded transfers are immutable"):
        execute(migrated_database_url, statement)


def test_epoch_seconds_are_read_as_utc(client: TestClient, migrated_database_url: str) -> None:
    sale, operator_a = pending_qr(client, migrated_database_url)
    paid_at = int(time.time()) - 60

    send(client, payment_event(sale, datePaid=paid_at))

    occurred = detail(client, operator_a, sale)["transfers"][0]["occurred_at"]
    assert datetime.fromisoformat(occurred) == datetime.fromtimestamp(paid_at, UTC)


@pytest.mark.parametrize(
    "changes",
    [{"amount": "AMOUNT_OVERFLOW"}, {"datePaid": 10**20}, {"datePaid": -5}],
)
def test_extreme_values_are_treated_as_insufficient_not_as_failures(
    client: TestClient, migrated_database_url: str, changes: dict[str, object]
) -> None:
    sale, _ = pending_qr(client, migrated_database_url)
    event = payment_event(sale, **changes)
    body = json.dumps(event, separators=(",", ":")).replace('"AMOUNT_OVERFLOW"', "1e999999999")

    status = deliver(client, body.encode(), Delivery(message_id="msg_extreme")).status_code
    processed = run_sales(migrated_database_url, "process-events")

    assert status == HTTPStatus.NO_CONTENT
    assert event_status(migrated_database_url) == "unmatched"
    assert "0 failed" in processed.stdout
    assert scalar(migrated_database_url, "SELECT count(*) FROM transactions") == 0


def test_a_transaction_id_already_recorded_for_another_sale_is_unmatched(
    client: TestClient, migrated_database_url: str
) -> None:
    first, operator_a = pending_qr(client, migrated_database_url)
    send(client, payment_event(first), message_id="msg_first")
    second = create_sale(client, operator_a, first["merchant_id"], amount_cents=AMOUNT).json()
    client.post(
        f"/sales/{second['id']}/attempts",
        json={"method": "qr"},
        headers={**operator_a, IDEMPOTENCY_HEADER: str(uuid.uuid4())},
    )
    second = detail(client, operator_a, second)
    execute(
        migrated_database_url,
        "UPDATE payment_attempts SET provider_request_id = 'SECOND-QR' WHERE sale_id = :id",
        {"id": second["id"]},
    )
    second = detail(client, operator_a, second)

    status = send(client, payment_event(second), message_id="msg_second")
    processed = run_sales(migrated_database_url, "process-events")

    assert status == HTTPStatus.NO_CONTENT
    assert detail(client, operator_a, second)["status"] == "open"
    assert (
        scalar(
            migrated_database_url,
            "SELECT status FROM webhook_events WHERE provider_event_id = 'msg_second'",
        )
        == "unmatched"
    )
    assert "0 failed" in processed.stdout
    assert scalar(migrated_database_url, "SELECT count(*) FROM transactions") == 1
