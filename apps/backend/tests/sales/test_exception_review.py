import json
import uuid
from collections.abc import Iterator
from http import HTTPStatus
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.payments.pey_support import FakePey
from tests.payments.webhook_support import Delivery, deliver, settings_for
from tests.sales.support import (
    ADMIN,
    IDEMPOTENCY_HEADER,
    OPERATOR_A,
    RECEIVER_A,
    bearer,
    create_sale,
    ready_merchant,
    start_client,
)
from tests.support import execute, scalar

PRICE = 30000
SHORT = 25000


@pytest.fixture
def client(migrated_database_url: str) -> Iterator[TestClient]:
    settings = settings_for(migrated_database_url)
    with start_client(settings, migrated_database_url, FakePey().provider()) as started:
        yield started


def short_payment(client: TestClient, database_url: str) -> tuple[dict[str, Any], str]:
    merchant = ready_merchant(client, database_url, "Tienda Demo A", OPERATOR_A)
    operator_a = bearer(client, OPERATOR_A)
    sale: dict[str, Any] = create_sale(client, operator_a, merchant, amount_cents=PRICE).json()
    attempt = client.post(
        f"/sales/{sale['id']}/attempts",
        json={"method": "qr"},
        headers={**operator_a, IDEMPOTENCY_HEADER: str(uuid.uuid4())},
    ).json()
    event = {
        "type": "codi.qr.payment_received",
        "amount": SHORT / 100,
        "bankAccountId": RECEIVER_A["provider_account_id"],
        "codiQrId": attempt["provider_request_id"],
        "datePaid": 1795000000,
        "transactionId": "TX-SHORT",
        "metadata": {"tappy_attempt_id": attempt["id"]},
    }
    deliver(client, json.dumps(event).encode(), Delivery(message_id="msg_short"))
    exception_id = str(scalar(database_url, "SELECT id FROM payment_exceptions"))
    return sale, exception_id


def money(database_url: str) -> tuple[object, ...]:
    return (
        scalar(database_url, "SELECT status FROM sales"),
        scalar(database_url, "SELECT count(*) FROM transactions"),
        scalar(database_url, "SELECT sum(amount_cents) FROM transactions"),
        scalar(database_url, "SELECT count(*) FROM payment_exceptions WHERE resolved_at IS NULL"),
    )


def test_an_admin_notes_an_incident_and_requests_a_recoverable_reconciliation(
    client: TestClient, migrated_database_url: str
) -> None:
    _, exception_id = short_payment(client, migrated_database_url)
    admin = bearer(client, ADMIN)
    before = money(migrated_database_url)

    noted = client.post(
        f"/exceptions/{exception_id}/notes",
        json={"text": "Customer says they paid twice; checking with the bank"},
        headers=admin,
    )
    requested = client.post(f"/exceptions/{exception_id}/reconciliation", headers=admin)
    detail = client.get(f"/exceptions/{exception_id}", headers=admin).json()

    assert noted.status_code == HTTPStatus.CREATED
    assert noted.json()["author"] == ADMIN
    assert requested.status_code == HTTPStatus.ACCEPTED
    assert requested.json()["outcome"] == "created"
    assert requested.json()["job"]["status"] == "pending"
    assert detail["reason"] == "amount_mismatch"
    assert detail["resolved_at"] is None
    assert [note["text"] for note in detail["notes"]] == [
        "Customer says they paid twice; checking with the bank",
        "Reconciliation requested (created)",
    ]
    assert {note["author"] for note in detail["notes"]} == {ADMIN}
    assert detail["reconciliation"]["status"] == "pending"
    assert scalar(migrated_database_url, "SELECT reason FROM reconciliation_jobs") == (
        "review_requested"
    )
    assert money(migrated_database_url) == before


def test_repeating_the_request_keeps_one_logical_job_and_the_evidence_intact(
    client: TestClient, migrated_database_url: str
) -> None:
    _, exception_id = short_payment(client, migrated_database_url)
    admin = bearer(client, ADMIN)
    before = money(migrated_database_url)
    payload = scalar(migrated_database_url, "SELECT payload_digest FROM webhook_events")

    first = client.post(f"/exceptions/{exception_id}/reconciliation", headers=admin).json()
    second = client.post(f"/exceptions/{exception_id}/reconciliation", headers=admin).json()
    execute(migrated_database_url, "UPDATE reconciliation_jobs SET status = 'exhausted'")
    rearmed = client.post(f"/exceptions/{exception_id}/reconciliation", headers=admin).json()

    assert (first["outcome"], second["outcome"], rearmed["outcome"]) == (
        "created",
        "already_pending",
        "rearmed",
    )
    assert scalar(migrated_database_url, "SELECT count(*) FROM reconciliation_jobs") == 1
    assert scalar(migrated_database_url, "SELECT status FROM reconciliation_jobs") == "pending"
    assert scalar(migrated_database_url, "SELECT tries FROM reconciliation_jobs") == 0
    assert money(migrated_database_url) == before
    assert scalar(migrated_database_url, "SELECT payload_digest FROM webhook_events") == payload


def test_operators_and_anonymous_callers_cannot_review_incidents(
    client: TestClient, migrated_database_url: str
) -> None:
    _, exception_id = short_payment(client, migrated_database_url)
    operator_a = bearer(client, OPERATOR_A)

    responses = [
        client.post(f"/exceptions/{exception_id}/notes", json={"text": "x"}, headers=operator_a),
        client.post(f"/exceptions/{exception_id}/reconciliation", headers=operator_a),
        client.get(f"/exceptions/{exception_id}", headers=operator_a),
        client.post(f"/exceptions/{exception_id}/reconciliation"),
    ]

    assert [response.status_code for response in responses] == [
        HTTPStatus.FORBIDDEN,
        HTTPStatus.FORBIDDEN,
        HTTPStatus.FORBIDDEN,
        HTTPStatus.UNAUTHORIZED,
    ]
    assert scalar(migrated_database_url, "SELECT count(*) FROM exception_notes") == 0
    assert scalar(migrated_database_url, "SELECT count(*) FROM reconciliation_jobs") == 0


@pytest.mark.parametrize("text", ["", "   ", "x" * 1001])
def test_invalid_notes_are_rejected(
    client: TestClient, migrated_database_url: str, text: str
) -> None:
    _, exception_id = short_payment(client, migrated_database_url)

    response = client.post(
        f"/exceptions/{exception_id}/notes", json={"text": text}, headers=bearer(client, ADMIN)
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
    assert scalar(migrated_database_url, "SELECT count(*) FROM exception_notes") == 0


def test_an_unassociated_incident_can_be_noted_but_not_reconciled(
    client: TestClient, migrated_database_url: str
) -> None:
    event = {
        "type": "codi.qr.payment_received",
        "amount": 100.0,
        "bankAccountId": RECEIVER_A["provider_account_id"],
        "codiQrId": "UNKNOWN-QR",
        "datePaid": 1795000000,
        "transactionId": "TX-ORPHAN",
    }
    deliver(client, json.dumps(event).encode(), Delivery(message_id="msg_orphan"))
    exception_id = scalar(migrated_database_url, "SELECT id FROM payment_exceptions")
    admin = bearer(client, ADMIN)

    noted = client.post(f"/exceptions/{exception_id}/notes", json={"text": "No QR"}, headers=admin)
    requested = client.post(f"/exceptions/{exception_id}/reconciliation", headers=admin)
    unknown = client.get(f"/exceptions/{uuid.uuid4()}", headers=admin)

    assert noted.status_code == HTTPStatus.CREATED
    assert requested.status_code == HTTPStatus.CONFLICT
    assert requested.json() == {"detail": "The incident has no QR attempt to reconcile"}
    assert unknown.status_code == HTTPStatus.NOT_FOUND
    assert scalar(migrated_database_url, "SELECT count(*) FROM reconciliation_jobs") == 0
