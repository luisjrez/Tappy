import hashlib
import json
import logging
import re
import smtplib
import statistics
import subprocess
import sys
import time
from collections.abc import Iterator
from dataclasses import dataclass
from http import HTTPStatus
from urllib.error import URLError
from urllib.request import Request, urlopen

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response

from tappy.identity.models import IdentityStatus
from tappy.main import create_app
from tappy.notifications.cli import deliver_pending
from tappy.notifications.transport import Envelope
from tappy.platform.config import Settings
from tests.support import (
    app_environment,
    build_settings,
    create_identity,
    execute,
    free_port,
    isolated_environment,
    scalar,
    spawn_tappy,
)

MAILPIT_API = "http://127.0.0.1:8025/api/v1"
OPERATOR_EMAIL = "operadora@tappy.example"
PASSWORD = "mostrador seguro 2026"
GENERIC_ACCEPTED = {"detail": "If the account exists, a recovery email may be sent"}
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
    assert link.group(0).startswith(f"{PUBLIC_BASE_URL}/password-reset#token=")
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
    "recovery_jobs": "SELECT count(*) FROM recovery_jobs",
    "outbound_emails": "SELECT count(*) FROM outbound_emails",
    "password_reset_requests": "SELECT count(*) FROM password_reset_requests",
}
MAKE_DUE = "UPDATE outbound_emails SET next_attempt_at = now() - interval '1 hour'"
ATTEMPTS_AFTER_RETRY = 2
ORIGIN_LIMIT = 2
TIMING_SAMPLES = 15
TIMING_TOLERANCE_SECONDS = 0.02


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
    assert count(migrated_database_url, "recovery_jobs") == 1
    deliver_pending(settings, RecordingTransport())
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
    second_status, second_body = post_to_separate_process(
        migrated_database_url, "/auth/password-reset/request", {"email": OPERATOR_EMAIL}
    )
    with TestClient(create_app(settings)) as third_process:
        login = third_process.post(
            "/auth/login", json={"email": OPERATOR_EMAIL, "password": PASSWORD}
        )

    assert {response.status_code for response in first} == {HTTPStatus.ACCEPTED}
    assert {response.json()["detail"] for response in first} == {GENERIC_ACCEPTED["detail"]}
    assert (second_status, second_body) == (HTTPStatus.ACCEPTED, GENERIC_ACCEPTED)
    assert count(migrated_database_url, "recovery_jobs") == settings.recovery_limit_per_email
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
    assert count(migrated_database_url, "recovery_jobs") == ORIGIN_LIMIT


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
    assert scalar(migrated_database_url, "SELECT sealed_email FROM recovery_jobs") is None
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
        sealed_job = str(scalar(migrated_database_url, "SELECT sealed_email FROM recovery_jobs"))
        transport = RecordingTransport()
        deliver_pending(settings, transport)

    [envelope] = transport.sent
    link = re.search(r"https?://\S+", envelope.body)
    assert link is not None
    token = link.group(0).split("token=", 1)[1]
    assert link.group(0).startswith(f"{PUBLIC_BASE_URL}/password-reset#token=")
    assert "evil.example" not in envelope.body
    assert OPERATOR_EMAIL not in sealed_job
    assert token not in response.text
    assert token not in caplog.text
    assert scalar(migrated_database_url, "SELECT token_digest FROM password_reset_requests") == (
        hashlib.sha256(token.encode()).hexdigest()
    )
    assert scalar(migrated_database_url, "SELECT sealed_body FROM outbound_emails") is None


def test_deliver_command_sends_pending_email(
    client: TestClient, migrated_database_url: str
) -> None:
    request_recovery(client, OPERATOR_EMAIL)

    result = subprocess.run(
        [sys.executable, "-m", "tappy.notifications", "deliver"],
        env=isolated_environment(app_environment(migrated_database_url)),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "sent=1 retried=0 failed=0"
    assert [message.recipients for message in delivered_messages()] == [[OPERATOR_EMAIL]]


def test_deliver_command_requires_known_subcommand(migrated_database_url: str) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "tappy.notifications"],
        env=isolated_environment(app_environment(migrated_database_url)),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode != 0


def post_to_separate_process(
    database_url: str, path: str, payload: dict[str, str]
) -> tuple[int, object]:
    port = free_port()
    process = spawn_tappy({**app_environment(database_url), "TAPPY_PORT": str(port)})
    try:
        deadline = time.monotonic() + 10
        while True:
            try:
                request = Request(
                    f"http://127.0.0.1:{port}{path}",
                    data=json.dumps(payload).encode(),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(request, timeout=2) as response:
                    return response.status, json.loads(response.read())
            except URLError:
                if time.monotonic() > deadline:
                    raise
                time.sleep(0.1)
    finally:
        process.terminate()
        process.wait(timeout=10)


@pytest.mark.parametrize("status", [IdentityStatus.ACTIVE, IdentityStatus.INACTIVE, None])
def test_request_path_does_identical_work_for_every_account(
    settings: Settings, migrated_database_url: str, status: IdentityStatus | None
) -> None:
    if status is not None:
        create_identity(migrated_database_url, OPERATOR_EMAIL, PASSWORD, status=status)
    with TestClient(create_app(settings)) as client:
        response = request_recovery(client, OPERATOR_EMAIL)

    assert response.json() == GENERIC_ACCEPTED
    assert count(migrated_database_url, "recovery_jobs") == 1
    assert count(migrated_database_url, "outbound_emails") == 0
    assert count(migrated_database_url, "password_reset_requests") == 0


def test_response_time_does_not_reveal_existing_accounts(
    settings: Settings, migrated_database_url: str
) -> None:
    roomy = settings.model_copy(
        update={"recovery_limit_per_email": 100, "recovery_limit_per_origin": 100}
    )
    create_identity(migrated_database_url, OPERATOR_EMAIL, PASSWORD)
    with TestClient(create_app(roomy)) as client:
        request_recovery(client, "calentamiento@tappy.example")
        existing = median_seconds(client, OPERATOR_EMAIL)
        unknown = median_seconds(client, "nadie@tappy.example")

    assert abs(existing - unknown) < TIMING_TOLERANCE_SECONDS


def median_seconds(client: TestClient, email: str) -> float:
    samples = []
    for _ in range(TIMING_SAMPLES):
        started = time.perf_counter()
        request_recovery(client, email)
        samples.append(time.perf_counter() - started)
    return statistics.median(samples)


class AmbiguousTransport:
    def send(self, envelope: Envelope) -> None:
        raise smtplib.SMTPServerDisconnected("connection closed after DATA")


def test_ambiguous_provider_response_is_retried_not_reported_as_delivered(
    client: TestClient, settings: Settings, migrated_database_url: str
) -> None:
    request_recovery(client, OPERATOR_EMAIL)

    report = deliver_pending(settings, AmbiguousTransport())

    assert (report.sent, report.retried) == (0, 1)
    assert scalar(migrated_database_url, "SELECT status FROM outbound_emails") == "pending"
    assert (
        scalar(migrated_database_url, "SELECT last_error FROM outbound_emails")
        == "SMTPServerDisconnected"
    )


def test_undecryptable_email_fails_alone_without_blocking_the_queue(
    client: TestClient, settings: Settings, migrated_database_url: str
) -> None:
    create_identity(migrated_database_url, "segunda@tappy.example", PASSWORD)
    request_recovery(client, OPERATOR_EMAIL)
    request_recovery(client, "segunda@tappy.example")
    deliver_pending(settings, FailingTransport())
    execute(
        migrated_database_url,
        "UPDATE outbound_emails SET sealed_body = 'corrupted' WHERE recipient = :email",
        {"email": OPERATOR_EMAIL},
    )
    execute(migrated_database_url, MAKE_DUE)
    transport = RecordingTransport()

    report = deliver_pending(settings, transport)

    assert (report.sent, report.failed) == (1, 1)
    assert [envelope.recipient for envelope in transport.sent] == ["segunda@tappy.example"]
    assert (
        scalar(
            migrated_database_url,
            "SELECT status FROM outbound_emails WHERE recipient = :email",
            {"email": OPERATOR_EMAIL},
        )
        == "failed"
    )
