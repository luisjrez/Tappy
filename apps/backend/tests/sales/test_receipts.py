import json
import uuid
from collections.abc import Iterator
from http import HTTPStatus
from typing import Any

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response

from tests.payments.pey_support import API_KEY, FakePey
from tests.payments.webhook_support import SECRET, Delivery, deliver, settings_for
from tests.sales.support import (
    ADMIN,
    IDEMPOTENCY_HEADER,
    OPERATOR_A,
    OPERATOR_B,
    RECEIVER_A,
    bearer,
    configure,
    create_sale,
    merchant_of,
    ready_merchant,
    start_client,
)

AMOUNT = 45000
PAID_AT = 1795000000
PAYER_CLABE = "002180700123456789"
PAYER_NAME = "Persona Pagadora Sintetica"
TRACKING_KEY = "MBAN01002611250000000001"
NO_RECEPTION = "The sale has no confirmed reception"


@pytest.fixture
def client(migrated_database_url: str) -> Iterator[TestClient]:
    settings = settings_for(migrated_database_url)
    with start_client(settings, migrated_database_url, FakePey().provider()) as started:
        yield started


def pending_sale(
    client: TestClient, database_url: str, amount: int = AMOUNT
) -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
    merchant_a = ready_merchant(client, database_url, "Tienda Demo A", OPERATOR_A)
    operator_a = bearer(client, OPERATOR_A)
    sale = create_sale(client, operator_a, merchant_a, amount_cents=amount, concept="Comida").json()
    attempt = client.post(
        f"/sales/{sale['id']}/attempts",
        json={"method": "qr"},
        headers={**operator_a, IDEMPOTENCY_HEADER: str(uuid.uuid4())},
    ).json()
    return sale, attempt, operator_a


def pay(client: TestClient, attempt: dict[str, Any], amount: int, transaction_id: str) -> None:
    event = {
        "type": "codi.qr.payment_received",
        "amount": amount / 100,
        "bankAccountId": RECEIVER_A["provider_account_id"],
        "codiQrId": attempt["provider_request_id"],
        "datePaid": PAID_AT,
        "transactionId": transaction_id,
        "apiKeyId": "01HZZSYNTHETICAPIKEY0000",
        "metadata": {
            "tappy_attempt_id": attempt["id"],
            "clabe": PAYER_CLABE,
            "name": PAYER_NAME,
            "trackingKey": TRACKING_KEY,
        },
    }
    body = json.dumps(event, separators=(",", ":")).encode()
    deliver(client, body, Delivery(message_id=f"msg_{transaction_id.lower()}"))


def receipt(client: TestClient, headers: dict[str, str], sale_id: str) -> Response:
    return client.get(f"/sales/{sale_id}/receipt", headers=headers)


def test_a_validated_own_transfer_produces_its_receipt(
    client: TestClient, migrated_database_url: str
) -> None:
    sale, attempt, operator_a = pending_sale(client, migrated_database_url)
    pay(client, attempt, AMOUNT, "01M3QR8H0RH0XBCKYYD242YXNV")
    detail = client.get(f"/sales/{sale['id']}", headers=operator_a).json()

    response = receipt(client, operator_a, sale["id"])

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {
        "sale_id": sale["id"],
        "sale_reference": sale["reference"],
        "merchant_name": "Tienda Demo A",
        "beneficiary_name": sale["beneficiary_name"],
        "masked_account": sale["masked_account"],
        "amount_cents": AMOUNT,
        "currency": "MXN",
        "concept": "Comida",
        "provider_transaction_id": "01M3QR8H0RH0XBCKYYD242YXNV",
        "paid_at": detail["transfers"][0]["occurred_at"],
        "received_at": detail["transfers"][0]["received_at"],
        "simulated": False,
        "under_review": False,
    }


@pytest.mark.parametrize("paid_amount", [None, AMOUNT - 5000], ids=["pending", "short"])
def test_a_sale_without_a_confirmed_reception_has_no_receipt(
    client: TestClient, migrated_database_url: str, paid_amount: int | None
) -> None:
    sale, attempt, operator_a = pending_sale(client, migrated_database_url)
    if paid_amount is not None:
        pay(client, attempt, paid_amount, "TX-SHORT")

    response = receipt(client, operator_a, sale["id"])

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json() == {"detail": NO_RECEPTION}


def test_receipts_are_never_shown_for_another_merchant(
    client: TestClient, migrated_database_url: str
) -> None:
    sale, attempt, _ = pending_sale(client, migrated_database_url)
    pay(client, attempt, AMOUNT, "TX-OWN")
    merchant_b = merchant_of(client, migrated_database_url, "Tienda Demo B", OPERATOR_B)
    configure(client, merchant_b, provider_account_id="bank-account-demo-b")

    foreign = receipt(client, bearer(client, OPERATOR_B), sale["id"])
    unknown = receipt(client, bearer(client, OPERATOR_A), str(uuid.uuid4()))
    admin = receipt(client, bearer(client, ADMIN), sale["id"])
    anonymous = receipt(client, {}, sale["id"])

    assert foreign.status_code == HTTPStatus.NOT_FOUND
    assert foreign.json() == {"detail": "Sale not found"}
    assert unknown.status_code == HTTPStatus.NOT_FOUND
    assert admin.status_code == HTTPStatus.OK
    assert anonymous.status_code == HTTPStatus.UNAUTHORIZED


def test_the_receipt_keeps_useful_evidence_but_no_payer_data_or_secrets(
    client: TestClient, migrated_database_url: str
) -> None:
    sale, attempt, operator_a = pending_sale(client, migrated_database_url)
    pay(client, attempt, AMOUNT, "TX-SENSITIVE")

    text = receipt(client, operator_a, sale["id"]).text

    assert "TX-SENSITIVE" in text
    assert sale["reference"] in text
    for sensitive in (
        PAYER_CLABE,
        PAYER_NAME,
        TRACKING_KEY,
        "01HZZSYNTHETICAPIKEY0000",
        API_KEY,
        SECRET,
        RECEIVER_A["provider_account_id"],
        str(RECEIVER_A["clabe"]),
    ):
        assert str(sensitive) not in text


def test_a_double_reception_receipt_shows_the_covering_transfer_under_review(
    client: TestClient, migrated_database_url: str
) -> None:
    sale, attempt, operator_a = pending_sale(client, migrated_database_url)
    pay(client, attempt, AMOUNT, "TX-COVERING")
    pay(client, attempt, AMOUNT, "TX-SECOND")

    body = receipt(client, operator_a, sale["id"]).json()

    assert body["provider_transaction_id"] == "TX-COVERING"
    assert body["amount_cents"] == AMOUNT
    assert body["under_review"] is True
