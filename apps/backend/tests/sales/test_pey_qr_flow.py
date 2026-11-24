import json
import uuid
from http import HTTPStatus
from typing import Any

import pytest
from pydantic import SecretStr

from tappy.payments.factory import provider_from
from tappy.payments.pey import PeyQrProvider
from tappy.platform.config import Settings
from tests.payments.pey_support import API_KEY, CREATED, FIXTURE, FakePey
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
from tests.support import build_settings, scalar


def run_qr(
    migrated_database_url: str, fake: FakePey
) -> tuple[int, dict[str, Any], dict[str, Any], str]:
    settings = build_settings(database_url=migrated_database_url)
    with start_client(settings, migrated_database_url, fake.provider()) as client:
        merchant_a = ready_merchant(client, migrated_database_url, "Tienda Demo A", OPERATOR_A)
        operator_a = bearer(client, OPERATOR_A)
        sale = create_sale(client, operator_a, merchant_a, amount_cents=AMOUNT).json()
        response = client.post(
            f"/sales/{sale['id']}/attempts",
            json={"method": "qr"},
            headers={**operator_a, IDEMPOTENCY_HEADER: str(uuid.uuid4())},
        )
        detail = client.get(f"/sales/{sale['id']}", headers=operator_a).json()
    return response.status_code, response.json(), detail, response.text


def test_pey_qr_is_stored_with_the_official_id_and_payload(migrated_database_url: str) -> None:
    fake = FakePey()

    status, attempt, detail, text = run_qr(migrated_database_url, fake)

    assert status == HTTPStatus.CREATED
    assert attempt["status"] == "pending"
    assert attempt["simulated"] is False
    assert attempt["provider_request_id"] == CREATED["id"]
    assert attempt["qr_payload"] == CREATED["qrString"]
    assert attempt["failure_code"] is None
    assert detail["status"] == "open"
    assert API_KEY not in text
    assert scalar(migrated_database_url, "SELECT provider FROM payment_attempts") == "pey"
    sent = json.loads(fake.requests[0].content)
    assert sent["bankAccountId"] == RECEIVER_A["provider_account_id"]
    assert sent["metadata"]["tappy_attempt_id"] == attempt["id"]


def test_definitive_rejection_fails_the_attempt_with_its_code(
    migrated_database_url: str,
) -> None:
    fake = FakePey(400, FIXTURE["responses"]["400"]["invalidAmount"])

    status, body, detail, text = run_qr(migrated_database_url, fake)

    assert status == HTTPStatus.BAD_GATEWAY
    assert body == {"detail": "The QR provider rejected the request (INVALID_AMOUNT)"}
    attempt = detail["attempts"][0]
    assert attempt["status"] == "failed"
    assert attempt["failure_code"] == "INVALID_AMOUNT"
    assert attempt["provider_request_id"] is None
    assert detail["status"] == "open"
    assert API_KEY not in text


def test_uncertain_response_keeps_the_attempt_creating(migrated_database_url: str) -> None:
    fake = FakePey(201, {"qrString": "payload without id"})

    status, body, detail, _ = run_qr(migrated_database_url, fake)

    assert status == HTTPStatus.SERVICE_UNAVAILABLE
    assert body == {
        "detail": (
            "The QR provider is unavailable (invalid_response); "
            "the attempt is kept for reconciliation"
        )
    }
    attempt = detail["attempts"][0]
    assert attempt["status"] == "creating"
    assert attempt["provider_request_id"] is None


def test_pey_settings_require_a_server_side_key() -> None:
    base = build_settings().model_dump()

    with pytest.raises(ValueError, match="TAPPY_PEY_API_KEY"):
        Settings.model_validate({**base, "payment_provider": "pey"})

    configured = Settings.model_validate(
        {**base, "payment_provider": "pey", "pey_api_key": SecretStr(API_KEY)}
    )
    assert isinstance(provider_from(configured), PeyQrProvider)
    assert configured.pey_base_url == "https://api.pey.mx"
    assert API_KEY not in repr(configured)


@pytest.mark.parametrize(
    ("url", "accepted"),
    [
        ("https://api.pey.mx", True),
        ("http://127.0.0.1:8899", True),
        ("http://localhost:8899", True),
        ("http://api.pey.mx", False),
        ("http://127.0.0.1.example.com", False),
        ("ftp://api.pey.mx", False),
    ],
)
def test_pey_base_url_requires_tls_outside_loopback(url: str, accepted: bool) -> None:
    candidate = {**build_settings().model_dump(), "pey_base_url": url}

    if accepted:
        assert Settings.model_validate(candidate).pey_base_url == url
    else:
        with pytest.raises(ValueError, match="pey_base_url"):
            Settings.model_validate(candidate)


def test_a_provider_id_already_linked_to_another_attempt_is_uncertain(
    migrated_database_url: str,
) -> None:
    fake = FakePey()
    settings = build_settings(database_url=migrated_database_url)
    with start_client(settings, migrated_database_url, fake.provider()) as client:
        merchant_a = ready_merchant(client, migrated_database_url, "Tienda Demo A", OPERATOR_A)
        operator_a = bearer(client, OPERATOR_A)
        responses = []
        for _ in range(2):
            sale = create_sale(client, operator_a, merchant_a, amount_cents=AMOUNT).json()
            responses.append(
                client.post(
                    f"/sales/{sale['id']}/attempts",
                    json={"method": "qr"},
                    headers={**operator_a, IDEMPOTENCY_HEADER: str(uuid.uuid4())},
                )
            )

    assert responses[0].status_code == HTTPStatus.CREATED
    assert responses[1].status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert responses[1].json() == {
        "detail": (
            "The QR provider is unavailable (duplicate_provider_id); "
            "the attempt is kept for reconciliation"
        )
    }
    assert (
        scalar(
            migrated_database_url,
            "SELECT count(*) FROM payment_attempts WHERE provider_request_id = :id",
            {"id": CREATED["id"]},
        )
        == 1
    )
    assert (
        scalar(
            migrated_database_url, "SELECT count(*) FROM payment_attempts WHERE status = 'creating'"
        )
        == 1
    )
