import io
import logging
import re
import uuid
from collections.abc import Iterator
from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from tappy.payments.provider import IssuedQr, QrOrder
from tappy.payments.simulator import SimulatedQrProvider
from tappy.platform.config import Settings
from tappy.platform.diagnostics import configure_logging
from tests.sales.support import (
    AMOUNT,
    IDEMPOTENCY_HEADER,
    OPERATOR_A,
    bearer,
    create_sale,
    ready_merchant,
    start_client,
)
from tests.support import VALID_SECRET, build_settings

TOKEN = "synthetic-bearer-leak-token-0001"
PEY_KEY = "pey-synthetic-api-key-0001"
CLABE = "002180700123456789"
PHONE = "5512345678"
EMAIL = "pagador.sintetico@example.com"
GENERATED = re.compile(r"[0-9a-f]{32}")


class ExplodingProvider(SimulatedQrProvider):
    def create_qr(self, order: QrOrder) -> IssuedQr:
        raise RuntimeError(
            f"pey answered Bearer {TOKEN} for clabe {CLABE}, phone {PHONE}, payer {EMAIL}"
        )


def diagnostic_settings(database_url: str) -> Settings:
    return build_settings(database_url=database_url).model_copy(
        update={"pey_api_key": SecretStr(PEY_KEY)}
    )


@pytest.fixture
def settings(migrated_database_url: str) -> Settings:
    return diagnostic_settings(migrated_database_url)


@pytest.fixture
def log_stream(settings: Settings) -> Iterator[io.StringIO]:
    stream = io.StringIO()
    handler = configure_logging(settings, stream)
    try:
        yield stream
    finally:
        logging.getLogger().removeHandler(handler)


@pytest.fixture
def client(migrated_database_url: str, settings: Settings) -> Iterator[TestClient]:
    with start_client(settings, migrated_database_url, ExplodingProvider()) as client:
        yield client


def test_an_unexpected_error_answers_a_reference_and_logs_it_without_sensitive_data(
    client: TestClient, migrated_database_url: str, log_stream: io.StringIO
) -> None:
    merchant_a = ready_merchant(client, migrated_database_url, "Tienda Demo A", OPERATOR_A)
    operator_a = bearer(client, OPERATOR_A)
    sale = create_sale(client, operator_a, merchant_a, amount_cents=AMOUNT).json()

    response = client.post(
        f"/sales/{sale['id']}/attempts",
        json={"method": "qr"},
        headers={**operator_a, IDEMPOTENCY_HEADER: str(uuid.uuid4())},
    )

    reference = response.headers["X-Request-ID"]
    log = log_stream.getvalue()
    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert response.json() == {"detail": "Internal server error", "reference": reference}
    assert GENERATED.fullmatch(reference)
    assert f"[{reference}]" in log
    assert "Unhandled error in POST /sales/{sale_id}/attempts" in log
    assert "RuntimeError" in log
    assert "Bearer [redacted]" in log
    assert "**************6789" in log
    assert "******5678" in log
    assert "[email]" in log
    for sensitive in (TOKEN, CLABE, PHONE, EMAIL):
        assert sensitive not in log
        assert sensitive not in response.text


def test_configured_secrets_never_reach_a_log_line(
    settings: Settings, log_stream: io.StringIO
) -> None:
    logger = logging.getLogger("tappy.payments.pey")

    logger.warning("pey call with key %s and secret %s", PEY_KEY, VALID_SECRET)

    log = log_stream.getvalue()
    assert "pey call with key [redacted] and secret [redacted]" in log
    assert PEY_KEY not in log
    assert VALID_SECRET not in log


def test_a_safe_caller_reference_is_kept_and_an_unsafe_one_replaced(
    client: TestClient,
) -> None:
    kept = client.get("/health", headers={"X-Request-ID": "caller-ref-0001"})
    replaced = client.get("/health", headers={"X-Request-ID": "bad ref <script>"})

    assert kept.headers["X-Request-ID"] == "caller-ref-0001"
    assert GENERATED.fullmatch(replaced.headers["X-Request-ID"])


def test_every_error_response_carries_its_reference(
    client: TestClient, migrated_database_url: str
) -> None:
    ready_merchant(client, migrated_database_url, "Tienda Demo A", OPERATOR_A)
    operator_a = bearer(client, OPERATOR_A)

    missing = client.get(f"/sales/{uuid.uuid4()}", headers=operator_a)
    anonymous = client.get("/sales")
    invalid = client.post("/sales", json={}, headers={**operator_a, IDEMPOTENCY_HEADER: "k" * 16})

    for response in (missing, anonymous, invalid):
        assert GENERATED.fullmatch(response.headers["X-Request-ID"])
    assert [missing.status_code, anonymous.status_code, invalid.status_code] == [
        HTTPStatus.NOT_FOUND,
        HTTPStatus.UNAUTHORIZED,
        HTTPStatus.UNPROCESSABLE_CONTENT,
    ]
