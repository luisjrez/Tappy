import hashlib
import json
import uuid
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tappy.payments.provider import PaymentEvidence, ProviderName
from tappy.platform.config import Settings
from tappy.platform.database import Database
from tappy.sales.evidence import EvidenceOutcome, apply_evidence
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
from tests.support import build_settings, execute, run_sales, scalar, wait_until_blocked_on_a_lock

TRANSACTION = "01M3QR8H0RH0XBCKYYD242YXNV"
PAID_AT = 1795000000
BOTH_ENVIRONMENTS = 2
NOW = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)


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


def payment_body(sale: dict[str, Any], **changes: object) -> bytes:
    attempt = sale["attempts"][0]
    event: dict[str, object] = {
        "type": "codi.qr.payment_received",
        "amount": 300.0,
        "bankAccountId": RECEIVER_A["provider_account_id"],
        "codiQrId": attempt["provider_request_id"],
        "datePaid": PAID_AT,
        "transactionId": TRANSACTION,
        "metadata": {"tappy_attempt_id": attempt["id"]},
    }
    event.update(changes)
    return json.dumps(event, separators=(",", ":")).encode()


def detail(client: TestClient, headers: dict[str, str], sale: dict[str, Any]) -> dict[str, Any]:
    read: dict[str, Any] = client.get(f"/sales/{sale['id']}", headers=headers).json()
    return read


def status_of(database_url: str, message_id: str) -> object:
    return scalar(
        database_url,
        "SELECT status FROM webhook_events WHERE provider_event_id = :id",
        {"id": message_id},
    )


def evidence_for(sale: dict[str, Any]) -> PaymentEvidence:
    attempt = sale["attempts"][0]
    return PaymentEvidence(
        provider=ProviderName.PEY,
        environment="test",
        provider_request_id=attempt["provider_request_id"],
        attempt_id=uuid.UUID(attempt["id"]),
        provider_transaction_id=TRANSACTION,
        amount_cents=AMOUNT,
        receiver_account=str(RECEIVER_A["provider_account_id"]),
        occurred_at=datetime.fromtimestamp(PAID_AT, UTC),
    )


def test_redelivering_the_same_event_keeps_one_transfer(
    client: TestClient, migrated_database_url: str
) -> None:
    sale, operator_a = pending_qr(client, migrated_database_url)
    body = payment_body(sale)

    first = deliver(client, body, Delivery(message_id="msg_e1")).status_code
    repeated = deliver(client, body, Delivery(message_id="msg_e1")).status_code
    read = detail(client, operator_a, sale)

    assert (first, repeated) == (HTTPStatus.NO_CONTENT, HTTPStatus.NO_CONTENT)
    assert read["confirmed_amount_cents"] == AMOUNT
    assert len(read["transfers"]) == 1
    assert scalar(migrated_database_url, "SELECT count(*) FROM webhook_events") == 1
    assert status_of(migrated_database_url, "msg_e1") == "applied"


def test_another_event_for_the_same_transfer_is_recognised_as_duplicate(
    client: TestClient, migrated_database_url: str
) -> None:
    sale, operator_a = pending_qr(client, migrated_database_url)
    body = payment_body(sale)
    deliver(client, body, Delivery(message_id="msg_e1"))

    second = deliver(client, body, Delivery(message_id="msg_e2")).status_code
    read = detail(client, operator_a, sale)

    assert second == HTTPStatus.NO_CONTENT
    assert status_of(migrated_database_url, "msg_e2") == "duplicate"
    assert read["confirmed_amount_cents"] == AMOUNT
    assert scalar(migrated_database_url, "SELECT count(*) FROM transactions") == 1


def test_same_event_id_with_other_content_is_flagged_and_the_original_kept(
    client: TestClient, migrated_database_url: str
) -> None:
    sale, operator_a = pending_qr(client, migrated_database_url)
    original = payment_body(sale)
    variant = payment_body(sale, amount=999.0, transactionId="TX-VARIANT")
    deliver(client, original, Delivery(message_id="msg_e1"))

    response = deliver(client, variant, Delivery(message_id="msg_e1"))
    read = detail(client, operator_a, sale)
    listed = run_sales(migrated_database_url, "event-conflicts")

    assert response.status_code == HTTPStatus.NO_CONTENT
    assert scalar(migrated_database_url, "SELECT payload FROM webhook_events") == original
    assert scalar(migrated_database_url, "SELECT payload FROM webhook_event_conflicts") == variant
    assert read["confirmed_amount_cents"] == AMOUNT
    assert scalar(migrated_database_url, "SELECT count(*) FROM transactions") == 1
    assert listed.returncode == 0, listed.stderr
    assert "msg_e1" in listed.stdout
    assert "conflicting content" in listed.stdout


def test_repeated_conflicting_variants_are_kept_once(
    client: TestClient, migrated_database_url: str
) -> None:
    sale, _ = pending_qr(client, migrated_database_url)
    deliver(client, payment_body(sale), Delivery(message_id="msg_e1"))
    variant = payment_body(sale, amount=999.0)

    deliver(client, variant, Delivery(message_id="msg_e1"))
    deliver(client, variant, Delivery(message_id="msg_e1"))

    assert scalar(migrated_database_url, "SELECT count(*) FROM webhook_event_conflicts") == 1


def test_concurrent_event_and_query_evidence_for_one_transfer_count_once(
    client: TestClient, migrated_database_url: str
) -> None:
    sale, operator_a = pending_qr(client, migrated_database_url)
    database = Database.from_settings(build_settings(database_url=migrated_database_url))
    try:
        with database.session_factory() as racing, racing.begin():
            held = apply_evidence(racing, evidence_for(sale), None, NOW)
            with ThreadPoolExecutor(max_workers=1) as pool:
                attempt = pool.submit(
                    deliver, client, payment_body(sale), Delivery(message_id="msg_e2")
                )
                wait_until_blocked_on_a_lock(migrated_database_url)
                racing.commit()
                response = attempt.result(timeout=10)
        with database.transaction() as session:
            again = apply_evidence(session, evidence_for(sale), None, NOW)
    finally:
        database.dispose()

    assert held is EvidenceOutcome.APPLIED
    assert response.status_code == HTTPStatus.NO_CONTENT
    assert status_of(migrated_database_url, "msg_e2") == "duplicate"
    assert again is EvidenceOutcome.DUPLICATE
    read = detail(client, operator_a, sale)
    assert read["confirmed_amount_cents"] == AMOUNT
    assert scalar(migrated_database_url, "SELECT count(*) FROM transactions") == 1


def test_reprocessing_never_adds_a_second_effect(
    client: TestClient, migrated_database_url: str
) -> None:
    sale, operator_a = pending_qr(client, migrated_database_url)
    deliver(client, payment_body(sale), Delivery(message_id="msg_e1"))
    execute(migrated_database_url, "UPDATE webhook_events SET status = 'received'")

    processed = run_sales(migrated_database_url, "process-events")

    assert "1 duplicate" in processed.stdout
    assert detail(client, operator_a, sale)["confirmed_amount_cents"] == AMOUNT
    assert scalar(migrated_database_url, "SELECT count(*) FROM transactions") == 1


def test_event_ids_are_unique_per_provider_and_environment(
    client: TestClient, migrated_database_url: str
) -> None:
    sale, _ = pending_qr(client, migrated_database_url)
    execute(
        migrated_database_url,
        "INSERT INTO webhook_events (id, provider, environment, provider_event_id, event_type, "
        "payload, payload_digest, signed_at, status, received_at) VALUES (gen_random_uuid(), "
        "'pey', 'production', 'msg_e1', 'codi.qr.payment_received', 'x', 'digest', now(), "
        "'unmatched', now())",
    )

    deliver(client, payment_body(sale), Delivery(message_id="msg_e1"))

    assert scalar(migrated_database_url, "SELECT count(*) FROM webhook_events") == BOTH_ENVIRONMENTS
    assert (
        scalar(
            migrated_database_url,
            "SELECT status FROM webhook_events WHERE environment = 'test'",
        )
        == "applied"
    )


def test_same_transaction_with_other_amount_is_not_hidden_as_duplicate(
    client: TestClient, migrated_database_url: str
) -> None:
    sale, operator_a = pending_qr(client, migrated_database_url)
    deliver(client, payment_body(sale), Delivery(message_id="msg_e1"))

    deliver(client, payment_body(sale, amount=310.0), Delivery(message_id="msg_e2"))

    assert status_of(migrated_database_url, "msg_e2") == "review"
    assert detail(client, operator_a, sale)["confirmed_amount_cents"] == AMOUNT


def test_redelivering_an_event_still_waiting_applies_it(
    client: TestClient, migrated_database_url: str
) -> None:
    sale, operator_a = pending_qr(client, migrated_database_url)
    body = payment_body(sale)
    execute(
        migrated_database_url,
        "INSERT INTO webhook_events (id, provider, environment, provider_event_id, event_type, "
        "payload, payload_digest, signed_at, status, received_at) VALUES (gen_random_uuid(), "
        "'pey', 'test', 'msg_e1', 'codi.qr.payment_received', :body, :digest, now(), "
        "'received', now())",
        {"body": body, "digest": hashlib.sha256(body).hexdigest()},
    )

    deliver(client, body, Delivery(message_id="msg_e1"))

    assert status_of(migrated_database_url, "msg_e1") == "applied"
    assert detail(client, operator_a, sale)["status"] == "paid"


def test_a_conflict_on_an_event_not_yet_applied_keeps_applying_the_original(
    client: TestClient, migrated_database_url: str
) -> None:
    sale, operator_a = pending_qr(client, migrated_database_url)
    original = payment_body(sale)
    execute(
        migrated_database_url,
        "INSERT INTO webhook_events (id, provider, environment, provider_event_id, event_type, "
        "payload, payload_digest, signed_at, status, received_at) VALUES (gen_random_uuid(), "
        "'pey', 'test', 'msg_e1', 'codi.qr.payment_received', :body, :digest, now(), "
        "'received', now())",
        {"body": original, "digest": hashlib.sha256(original).hexdigest()},
    )

    deliver(client, payment_body(sale, amount=999.0), Delivery(message_id="msg_e1"))
    run_sales(migrated_database_url, "process-events")

    read = detail(client, operator_a, sale)
    assert read["confirmed_amount_cents"] == AMOUNT
    assert scalar(migrated_database_url, "SELECT count(*) FROM webhook_event_conflicts") == 1


def test_transfer_ids_are_unique_per_provider_and_environment(
    client: TestClient, migrated_database_url: str
) -> None:
    sale, _ = pending_qr(client, migrated_database_url)
    execute(
        migrated_database_url,
        "INSERT INTO transactions (id, sale_id, attempt_id, provider, environment, "
        "provider_transaction_id, amount_cents, currency, receiver_account, occurred_at, "
        "received_at) SELECT gen_random_uuid(), sale_id, id, 'pey', 'production', :tx, 1, "
        "'MXN', receiver_account, now(), now() FROM payment_attempts",
        {"tx": TRANSACTION},
    )

    deliver(client, payment_body(sale), Delivery(message_id="msg_e1"))

    assert status_of(migrated_database_url, "msg_e1") == "applied"
    assert (
        scalar(
            migrated_database_url, "SELECT count(*) FROM transactions WHERE environment = 'test'"
        )
        == 1
    )


@pytest.mark.parametrize("environment", ["Production", "x" * 33, "prod env"])
def test_environment_names_are_short_lowercase_identifiers(environment: str) -> None:
    with pytest.raises(ValueError, match="environment"):
        Settings.model_validate({**build_settings().model_dump(), "environment": environment})
