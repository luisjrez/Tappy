import hashlib
import json
import logging
import re
import smtplib
from collections.abc import Iterator
from dataclasses import dataclass
from http import HTTPStatus
from urllib.request import Request, urlopen

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response

from tappy.identity.models import IdentityStatus
from tappy.main import create_app
from tappy.notifications.cli import deliver_pending
from tappy.notifications.transport import Envelope
from tappy.platform.config import Settings
from tests.support import build_settings, create_identity, execute, scalar

MAILPIT_API = "http://127.0.0.1:8025/api/v1"
OPERATOR_EMAIL = "operadora@tappy.example"
PASSWORD = "mostrador seguro 2026"
GENERIC_ACCEPTED = {"detail": "If the account exists, a recovery email will be sent"}
PUBLIC_BASE_URL = "https://admin.tappy.example"


def mailpit(method: str, path: str) -> object:
    with urlopen(Request(f"{MAILPIT_API}{path}", method=method), timeout=5) as response:
        body = response.read()
    return json.loads(body) if method == "GET" else None


@dataclass(frozen=True)
class DeliveredMessage:
    recipients: list[str]
    text: str


def delivered_messages() -> list[DeliveredMessage]:
    listing = mailpit("GET", "/messages")
    assert isinstance(listing, dict)
    messages: list[DeliveredMessage] = []
    for summary in listing["messages"]:
        detail = mailpit("GET", f"/message/{summary['ID']}")
        assert isinstance(detail, dict)
        recipients = [str(recipient["Address"]) for recipient in detail["To"]]
        messages.append(DeliveredMessage(recipients, str(detail["Text"])))
    return messages


@pytest.fixture
def settings(migrated_database_url: str) -> Settings:
    mailpit("DELETE", "/messages")
    return build_settings(database_url=migrated_database_url).model_copy(
        update={"public_base_url": PUBLIC_BASE_URL}
    )


@pytest.fixture
def client(settings: Settings, migrated_database_url: str) -> Iterator[TestClient]:
    create_identity(migrated_database_url, OPERATOR_EMAIL, PASSWORD)
    with TestClient(create_app(settings)) as client:
        yield client


def request_recovery(client: TestClient, email: str) -> Response:
    return client.post("/auth/password-reset/request", json={"email": email})


def test_active_identity_receives_link_with_configured_origin(
    client: TestClient, settings: Settings
) -> None:
    response = client.post("/auth/password-reset/request", json={"email": OPERATOR_EMAIL})
    deliver_pending(settings)

    [message] = delivered_messages()
    link = re.search(r"https://\S+", message.text)

    assert response.status_code == HTTPStatus.ACCEPTED
    assert response.json() == GENERIC_ACCEPTED
    assert message.recipients == [OPERATOR_EMAIL]
    assert link is not None
    assert link.group(0).startswith(f"{PUBLIC_BASE_URL}/password-reset?token=")
    token = link.group(0).split("token=", 1)[1]
    assert token not in response.text


class RecordingTransport:
    def __init__(self) -> None:
        self.sent: list[Envelope] = []

    def send(self, envelope: Envelope) -> None:
        self.sent.append(envelope)


class FailingTransport:
    def send(self, envelope: Envelope) -> None:
        raise smtplib.SMTPDataError(451, b"temporary local problem")


COUNTS = {
    "outbound_emails": "SELECT count(*) FROM outbound_emails",
    "password_reset_requests": "SELECT count(*) FROM password_reset_requests",
}
MAKE_DUE = "UPDATE outbound_emails SET next_attempt_at = now() - interval '1 hour'"
ATTEMPTS_AFTER_RETRY = 2
ORIGIN_LIMIT = 2


def count(database_url: str, table: str) -> object:
    return scalar(database_url, COUNTS[table])


@pytest.mark.parametrize("status", [None, IdentityStatus.INACTIVE])
def test_unknown_or_inactive_accounts_get_the_same_answer_and_nothing_else(
    settings: Settings, migrated_database_url: str, status: IdentityStatus | None
) -> None:
    email = "nadie@tappy.example"
    if status is not None:
        create_identity(migrated_database_url, email, PASSWORD, status=status)
    with TestClient(create_app(settings)) as client:
        response = request_recovery(client, email)

    assert response.status_code == HTTPStatus.ACCEPTED
    assert response.json() == GENERIC_ACCEPTED
    assert count(migrated_database_url, "outbound_emails") == 0
    assert count(migrated_database_url, "password_reset_requests") == 0
    assert (
        scalar(migrated_database_url, "SELECT count(*) FROM identities WHERE status = 'active'")
        == 0
    )


def test_limits_persist_across_processes_and_never_touch_credentials(
    settings: Settings, migrated_database_url: str
) -> None:
    create_identity(migrated_database_url, OPERATOR_EMAIL, PASSWORD)
    with TestClient(create_app(settings)) as first_process:
        first = [request_recovery(first_process, OPERATOR_EMAIL) for _ in range(5)]
    with TestClient(create_app(settings)) as second_process:
        second = request_recovery(second_process, OPERATOR_EMAIL)
        login = second_process.post(
            "/auth/login", json={"email": OPERATOR_EMAIL, "password": PASSWORD}
        )

    assert {response.status_code for response in [*first, second]} == {HTTPStatus.ACCEPTED}
    assert {response.text for response in [*first, second]} == {
        json.dumps(GENERIC_ACCEPTED, separators=(",", ":"))
    }
    assert count(migrated_database_url, "outbound_emails") == settings.recovery_limit_per_email
    assert login.status_code == HTTPStatus.OK


def test_origin_limit_applies_across_different_accounts(
    settings: Settings, migrated_database_url: str
) -> None:
    limited = settings.model_copy(update={"recovery_limit_per_origin": ORIGIN_LIMIT})
    emails = [f"operador{index}@tappy.example" for index in range(4)]
    for email in emails:
        create_identity(migrated_database_url, email, PASSWORD)
    with TestClient(create_app(limited)) as client:
        responses = [request_recovery(client, email) for email in emails]

    assert {response.status_code for response in responses} == {HTTPStatus.ACCEPTED}
    assert count(migrated_database_url, "outbound_emails") == ORIGIN_LIMIT


def test_provider_failure_is_retried_after_restart_without_changing_credentials(
    client: TestClient, settings: Settings, migrated_database_url: str
) -> None:
    request_recovery(client, OPERATOR_EMAIL)

    failed_attempt = deliver_pending(settings, FailingTransport())
    not_yet_due = deliver_pending(settings, RecordingTransport())
    execute(migrated_database_url, MAKE_DUE)
    recovered = RecordingTransport()
    after_restart = deliver_pending(settings, recovered)

    assert (failed_attempt.sent, failed_attempt.retried) == (0, 1)
    assert (not_yet_due.sent, not_yet_due.retried) == (0, 0)
    assert after_restart.sent == 1
    assert [envelope.recipient for envelope in recovered.sent] == [OPERATOR_EMAIL]
    assert scalar(migrated_database_url, "SELECT attempts FROM outbound_emails") == (
        ATTEMPTS_AFTER_RETRY
    )
    assert scalar(migrated_database_url, "SELECT sealed_body FROM outbound_emails") is None
    login = client.post("/auth/login", json={"email": OPERATOR_EMAIL, "password": PASSWORD})
    assert login.status_code == HTTPStatus.OK


def test_delivery_gives_up_after_bounded_attempts(
    client: TestClient, settings: Settings, migrated_database_url: str
) -> None:
    bounded = settings.model_copy(update={"delivery_max_attempts": ATTEMPTS_AFTER_RETRY})
    request_recovery(client, OPERATOR_EMAIL)

    deliver_pending(bounded, FailingTransport())
    execute(migrated_database_url, MAKE_DUE)
    final = deliver_pending(bounded, FailingTransport())

    assert final.failed == 1
    assert scalar(migrated_database_url, "SELECT status FROM outbound_emails") == "failed"
    assert scalar(migrated_database_url, "SELECT sealed_body FROM outbound_emails") is None
    assert (
        scalar(migrated_database_url, "SELECT last_error FROM outbound_emails") == "SMTPDataError"
    )


def test_link_origin_ignores_host_headers_and_raw_token_is_never_stored(
    client: TestClient,
    settings: Settings,
    migrated_database_url: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.DEBUG):
        response = client.post(
            "/auth/password-reset/request",
            json={"email": OPERATOR_EMAIL},
            headers={"Host": "evil.example", "X-Forwarded-Host": "evil.example"},
        )
        sealed = str(scalar(migrated_database_url, "SELECT sealed_body FROM outbound_emails"))
        transport = RecordingTransport()
        deliver_pending(settings, transport)

    [envelope] = transport.sent
    link = re.search(r"https?://\S+", envelope.body)
    assert link is not None
    token = link.group(0).split("token=", 1)[1]
    assert link.group(0).startswith(f"{PUBLIC_BASE_URL}/password-reset?token=")
    assert "evil.example" not in envelope.body
    assert token not in sealed
    assert token not in response.text
    assert token not in caplog.text
    assert scalar(migrated_database_url, "SELECT token_digest FROM password_reset_requests") == (
        hashlib.sha256(token.encode()).hexdigest()
    )
    assert scalar(migrated_database_url, "SELECT sealed_body FROM outbound_emails") is None
