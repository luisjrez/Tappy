import base64
import io
import logging
import re
import tempfile
import uuid
from collections.abc import Iterator
from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy.engine import make_url

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
from tests.support import (
    UNREACHABLE_DATABASE_PASSWORD,
    UNREACHABLE_DATABASE_URL,
    VALID_SECRET,
    app_environment,
    build_settings,
    free_port,
    run_identity,
    run_sales,
    spawn_tappy,
    wait_for_json,
)

TOKEN = "synthetic-bearer-leak-token-0001"
PEY_KEY = "pey-synthetic-api-key-0001"
CLABE = "002180700123456789"
PHONE = "5512345678"
EMAIL = "pagador.sintetico@example.com"
GENERATED = re.compile(r"[0-9a-f]{32}")
WEBHOOK_KEY = "whsec_" + base64.b64encode(b"synthetic-webhook-key-0123456789").decode()


class ExplodingProvider(SimulatedQrProvider):
    def create_qr(self, order: QrOrder) -> IssuedQr:
        logging.getLogger("tests.provider").warning("provider about to fail for %s", PHONE)
        raise RuntimeError(
            f"pey answered Bearer {TOKEN} for clabe {CLABE}, phone +52{PHONE}, payer {EMAIL}"
        )


def diagnostic_settings(database_url: str) -> Settings:
    return build_settings(database_url=database_url).model_copy(
        update={"pey_api_key": SecretStr(PEY_KEY), "pey_webhook_secret": SecretStr(WEBHOOK_KEY)}
    )


@pytest.fixture
def settings(migrated_database_url: str) -> Settings:
    return diagnostic_settings(migrated_database_url)


@pytest.fixture
def log_stream(settings: Settings) -> Iterator[io.StringIO]:
    stream = io.StringIO()
    root = logging.getLogger()
    level = root.level
    handler = configure_logging(settings, stream)
    try:
        yield stream
    finally:
        root.removeHandler(handler)
        root.setLevel(level)


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
    assert f"[{reference}] provider about to fail for ******5678" in log
    assert "Unhandled error in POST /sales/{sale_id}/attempts" in log
    assert "RuntimeError" in log
    assert "Bearer [redacted]" in log
    assert "**************6789" in log
    assert "********5678" in log
    assert "[email]" in log
    for sensitive in (TOKEN, CLABE, PHONE, EMAIL):
        assert sensitive not in log
        assert sensitive not in response.text


def test_configured_secrets_never_reach_a_log_line(
    settings: Settings, log_stream: io.StringIO
) -> None:
    logger = logging.getLogger("tappy.payments.pey")

    password = make_url(settings.database_url.get_secret_value()).password
    secrets = (PEY_KEY, VALID_SECRET, WEBHOOK_KEY.removeprefix("whsec_"), password)

    logger.warning("pey key %s, app secret %s, webhook %s, database %s", *secrets)

    log = log_stream.getvalue()
    assert (
        "pey key [redacted], app secret [redacted], webhook [redacted], database [redacted]" in log
    )
    for secret in secrets:
        assert secret
        assert secret not in log


def test_a_configured_secret_too_short_to_redact_is_named_without_its_value(
    migrated_database_url: str,
) -> None:
    short = "pw-1234"
    url = make_url(migrated_database_url).set(password=short)
    settings = diagnostic_settings(url.render_as_string(hide_password=False))
    stream = io.StringIO()
    root = logging.getLogger()
    level = root.level
    handler = configure_logging(settings, stream)
    root.removeHandler(handler)
    root.setLevel(level)

    log = stream.getvalue()
    warning = (
        "WARNING tappy.platform.diagnostics [-] The database password is shorter than "
        "8 characters, so logs cannot redact it"
    )
    assert log.count(warning) == 1
    assert short not in log


def test_a_safe_caller_reference_is_kept_and_an_unsafe_one_replaced(
    client: TestClient,
) -> None:
    kept = client.get("/health", headers={"X-Request-ID": "caller-ref-0001"})
    replaced = client.get("/health", headers={"X-Request-ID": "bad ref <script>"})
    digits_only = client.get("/health", headers={"X-Request-ID": PHONE})

    assert kept.headers["X-Request-ID"] == "caller-ref-0001"
    assert GENERATED.fullmatch(replaced.headers["X-Request-ID"])
    assert GENERATED.fullmatch(digits_only.headers["X-Request-ID"])


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


def test_server_and_command_lines_go_through_the_same_redacted_format(
    migrated_database_url: str,
) -> None:
    port = free_port()
    with tempfile.TemporaryFile() as captured:
        process = spawn_tappy(
            {**app_environment(migrated_database_url), "TAPPY_PORT": str(port)}, captured
        )
        try:
            wait_for_json(
                f"http://127.0.0.1:{port}/health?phone=%2B52{PHONE}&clabe={CLABE}",
                deadline_seconds=10,
            )
        finally:
            process.terminate()
            process.wait(timeout=10)
        captured.seek(0)
        server = captured.read().decode()
    failed = run_sales(UNREACHABLE_DATABASE_URL, "backlog")
    identity = run_identity(UNREACHABLE_DATABASE_URL, "show", "--email", EMAIL)

    assert "INFO uvicorn.error [-] Uvicorn running on" in server
    assert re.search(
        r'INFO uvicorn\.access \[[0-9a-f]{32}\] .*"GET /health\?phone=\*{8}5678&clabe=\*{14}6789 ',
        server,
    )
    assert PHONE not in server
    assert CLABE not in server
    for result, command in (
        (failed, "tappy.sales.cli [-] Command backlog"),
        (identity, "tappy.identity.cli [-] Command show"),
    ):
        assert result.returncode == 1
        assert f"ERROR {command} failed" in result.stderr
        assert "OperationalError" in result.stderr
        assert UNREACHABLE_DATABASE_PASSWORD not in result.stderr
