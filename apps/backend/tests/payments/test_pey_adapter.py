import json
import logging
import uuid
from decimal import Decimal

import httpx2
import pytest

from tappy.payments.provider import (
    IssuedQr,
    ProviderName,
    ProviderRejectedError,
    ProviderUnavailableError,
    QrOrder,
)
from tests.payments.pey_support import API_KEY, BASE_URL, CREATED, FIXTURE, FakePey

ATTEMPT = uuid.UUID("2d0f1a6e-3c55-4c1e-9e0b-6a8f5f1d2b77")
RECEIVER = "01HZY3K8Q4N6V7W8X9Y0Z1A2B3"


def order(amount_cents: int = 30010, concept: str | None = "Dos tacos") -> QrOrder:
    return QrOrder(ATTEMPT, "MSPE6WGBSK", amount_cents, concept, RECEIVER)


def sent_body(fake: FakePey) -> dict[str, object]:
    body: dict[str, object] = json.loads(fake.requests[0].content, parse_float=Decimal)
    return body


@pytest.mark.parametrize(("cents", "pesos"), [(1, Decimal("0.01")), (30010, Decimal("300.10"))])
def test_sends_exact_peso_amounts_and_keeps_the_official_id_and_payload(
    cents: int, pesos: Decimal
) -> None:
    fake = FakePey()

    issued = fake.provider().create_qr(order(cents))

    request = fake.requests[0]
    assert request.method == "POST"
    assert str(request.url) == f"{BASE_URL}/codi/qr"
    assert request.headers["authorization"] == f"Bearer {API_KEY}"
    assert sent_body(fake)["amount"] == pesos
    assert issued == IssuedQr(CREATED["id"], CREATED["qrString"])


def test_request_targets_the_snapshotted_receiver_and_links_the_attempt() -> None:
    fake = FakePey()

    fake.provider().create_qr(order())

    assert sent_body(fake) == {
        "amount": Decimal("300.10"),
        "concept": "Dos tacos",
        "bankAccountId": RECEIVER,
        "metadata": {"tappy_attempt_id": str(ATTEMPT), "tappy_reference": "MSPE6WGBSK"},
    }


def test_omits_the_concept_when_the_sale_has_none() -> None:
    fake = FakePey()

    fake.provider().create_qr(order(concept=None))

    assert "concept" not in sent_body(fake)


def test_adapter_is_labelled_as_the_real_provider() -> None:
    provider = FakePey().provider()

    assert provider.name is ProviderName.PEY
    assert provider.simulated is False


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"id": "", "qrString": "payload"},
        {"id": "AB12CD34EF", "qrString": ""},
        {"id": "AB12CD34EF", "qrString": None},
        {"id": 12345, "qrString": "payload"},
        "not json",
    ],
)
def test_invalid_creation_responses_never_invent_an_identifier(body: object) -> None:
    fake = FakePey(201, body)

    with pytest.raises(ProviderUnavailableError) as raised:
        fake.provider().create_qr(order())

    assert raised.value.reason == "invalid_response"


@pytest.mark.parametrize("example", sorted(FIXTURE["responses"]["400"]))
def test_official_rejections_are_classified_by_type(example: str) -> None:
    body = FIXTURE["responses"]["400"][example]
    fake = FakePey(400, body)

    with pytest.raises(ProviderRejectedError) as raised:
        fake.provider().create_qr(order())

    assert raised.value.code == body["error"]["type"]


def test_rate_limit_is_a_definitive_rejection() -> None:
    fake = FakePey(429, FIXTURE["responses"]["429"]["default"])

    with pytest.raises(ProviderRejectedError) as raised:
        fake.provider().create_qr(order())

    assert raised.value.code == "CALL_LIMIT_REACHED"


@pytest.mark.parametrize(
    ("status", "body"),
    [
        (503, FIXTURE["responses"]["503"]["maintenance"]),
        (500, FIXTURE["responses"]["500"]["invokeError"]),
        (500, FIXTURE["responses"]["500"]["requestIdError"]),
        (400, {"unexpected": True}),
    ],
)
def test_server_errors_and_unknown_errors_are_uncertain(status: int, body: object) -> None:
    fake = FakePey(status, body)

    with pytest.raises(ProviderUnavailableError) as raised:
        fake.provider().create_qr(order())

    assert raised.value.reason in {"server_error", "invalid_response"}


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (httpx2.ReadTimeout("timed out"), "timeout"),
        (httpx2.ConnectError("refused"), "connection"),
    ],
)
def test_timeouts_and_connection_failures_are_uncertain(error: Exception, reason: str) -> None:
    fake = FakePey(error=error)

    with pytest.raises(ProviderUnavailableError) as raised:
        fake.provider().create_qr(order())

    assert raised.value.reason == reason


def test_credentials_never_reach_logs_errors_or_representations(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    rejected = FakePey(400, FIXTURE["responses"]["400"]["invalidAmount"])
    accepted = FakePey()

    with pytest.raises(ProviderRejectedError) as raised:
        rejected.provider().create_qr(order())
    accepted.provider().create_qr(order())

    assert caplog.records
    assert API_KEY not in caplog.text
    assert API_KEY not in str(raised.value)
    assert API_KEY not in repr(accepted.provider())


def test_amounts_that_would_lose_precision_are_never_sent() -> None:
    fake = FakePey()

    with pytest.raises(ValueError, match="exactly"):
        fake.provider().create_qr(order(2**60 + 1))

    assert fake.requests == []
