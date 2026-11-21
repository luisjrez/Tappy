import re
import smtplib
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response
from sqlalchemy.orm import Session

from tappy.identity.models import Identity
from tappy.identity.reset import confirm_password_reset
from tappy.main import create_app
from tappy.notifications.cli import deliver_pending
from tappy.notifications.transport import Envelope
from tappy.platform.config import Settings
from tappy.platform.database import Database
from tests.support import build_settings, create_identity, execute, scalar

OPERATOR_EMAIL = "operadora@tappy.example"
OLD_PASSWORD = "mostrador seguro 2026"
NEW_PASSWORD = "nueva frase muy segura 2026"
TOKEN_IN_LINK = re.compile(r"#token=(\S+)")


class RecordingTransport:
    def __init__(self) -> None:
        self.sent: list[Envelope] = []

    def send(self, envelope: Envelope) -> None:
        self.sent.append(envelope)


@pytest.fixture
def settings(migrated_database_url: str) -> Settings:
    return build_settings(database_url=migrated_database_url)


@pytest.fixture
def client(settings: Settings, migrated_database_url: str) -> Iterator[TestClient]:
    create_identity(migrated_database_url, OPERATOR_EMAIL, OLD_PASSWORD)
    with TestClient(create_app(settings)) as client:
        yield client


def recovery_token(client: TestClient, settings: Settings, email: str = OPERATOR_EMAIL) -> str:
    client.post("/auth/password-reset/request", json={"email": email})
    transport = RecordingTransport()
    deliver_pending(settings, transport)
    match = TOKEN_IN_LINK.search(transport.sent[-1].body)
    assert match is not None
    return match.group(1)


def confirm(client: TestClient, token: str, password: str = NEW_PASSWORD) -> Response:
    return client.post(
        "/auth/password-reset/confirm", json={"token": token, "new_password": password}
    )


def login_status(client: TestClient, password: str, email: str = OPERATOR_EMAIL) -> int:
    return client.post("/auth/login", json={"email": email, "password": password}).status_code


def test_valid_token_sets_new_password_without_signing_in(
    client: TestClient, settings: Settings, migrated_database_url: str
) -> None:
    reference = scalar(migrated_database_url, "SELECT id::text FROM identities")
    token = recovery_token(client, settings)

    response = client.post(
        "/auth/password-reset/confirm", json={"token": token, "new_password": NEW_PASSWORD}
    )

    assert response.status_code == HTTPStatus.NO_CONTENT
    assert "access_token" not in response.text
    assert login_status(client, NEW_PASSWORD) == HTTPStatus.OK
    assert login_status(client, OLD_PASSWORD) == HTTPStatus.UNAUTHORIZED
    tokens = client.post(
        "/auth/login", json={"email": OPERATOR_EMAIL, "password": NEW_PASSWORD}
    ).json()
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert me.json()["reference"] == reference
    assert me.json()["role"] == "operator"


def password_hash(database_url: str) -> object:
    return scalar(
        database_url,
        "SELECT password_hash FROM identities WHERE email = :email",
        {"email": OPERATOR_EMAIL},
    )


INVALID_LINK = {"detail": "This link is invalid or has expired"}


@pytest.mark.parametrize("variant", ["expired", "altered", "reused"])
def test_invalid_links_never_change_the_password(
    client: TestClient, settings: Settings, migrated_database_url: str, variant: str
) -> None:
    token = recovery_token(client, settings)
    if variant == "expired":
        execute(
            migrated_database_url,
            "UPDATE password_reset_requests SET expires_at = now() - interval '1 minute'",
        )
    if variant == "reused":
        assert confirm(client, token).status_code == HTTPStatus.NO_CONTENT
    before = password_hash(migrated_database_url)
    presented = token[:-1] + ("A" if token[-1] != "A" else "B") if variant == "altered" else token

    response = confirm(client, presented, "otra frase distinta 2026")

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.json() == INVALID_LINK
    assert password_hash(migrated_database_url) == before


def test_concurrent_confirmations_change_the_password_once(
    client: TestClient, settings: Settings, migrated_database_url: str
) -> None:
    token = recovery_token(client, settings)
    passwords = [f"frase concurrente numero {index} 2026" for index in range(4)]

    with ThreadPoolExecutor(max_workers=4) as pool:
        statuses = list(
            pool.map(lambda password: confirm(client, token, password).status_code, passwords)
        )

    assert statuses.count(HTTPStatus.NO_CONTENT) == 1
    assert statuses.count(HTTPStatus.BAD_REQUEST) == len(passwords) - 1
    winner = passwords[statuses.index(HTTPStatus.NO_CONTENT)]
    assert login_status(client, winner) == HTTPStatus.OK


def test_deactivated_identity_is_not_reactivated_by_a_pending_link(
    client: TestClient, settings: Settings, migrated_database_url: str
) -> None:
    token = recovery_token(client, settings)
    execute(migrated_database_url, "UPDATE identities SET status = 'inactive'")

    response = confirm(client, token)

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert scalar(migrated_database_url, "SELECT status FROM identities") == "inactive"


@pytest.mark.parametrize("field", ["role", "email", "user_id", "reference"])
def test_extra_identity_fields_are_rejected_without_changes(
    client: TestClient, settings: Settings, migrated_database_url: str, field: str
) -> None:
    token = recovery_token(client, settings)
    before = password_hash(migrated_database_url)

    response = client.post(
        "/auth/password-reset/confirm",
        json={"token": token, "new_password": NEW_PASSWORD, field: "admin@tappy.example"},
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
    assert password_hash(migrated_database_url) == before
    assert scalar(migrated_database_url, "SELECT role FROM identities") == "operator"
    assert confirm(client, token).status_code == HTTPStatus.NO_CONTENT


def test_reset_revokes_every_session_and_pending_link(
    client: TestClient, settings: Settings, migrated_database_url: str
) -> None:
    api_session = client.post(
        "/auth/login", json={"email": OPERATOR_EMAIL, "password": OLD_PASSWORD}
    ).json()
    first_token = recovery_token(client, settings)
    second_token = recovery_token(client, settings)

    response = confirm(client, second_token)

    assert response.status_code == HTTPStatus.NO_CONTENT
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {api_session['access_token']}"})
    assert me.status_code == HTTPStatus.UNAUTHORIZED
    renewal = client.post("/auth/refresh", json={"refresh_token": api_session["refresh_token"]})
    assert renewal.status_code == HTTPStatus.UNAUTHORIZED
    assert (
        confirm(client, first_token, "otra frase distinta 2026").status_code
        == HTTPStatus.BAD_REQUEST
    )
    assert (
        scalar(
            migrated_database_url, "SELECT count(*) FROM access_sessions WHERE revoked_at IS NULL"
        )
        == 0
    )


def test_policy_violation_keeps_the_link_usable(
    client: TestClient, settings: Settings, migrated_database_url: str
) -> None:
    token = recovery_token(client, settings)
    before = password_hash(migrated_database_url)

    rejected = confirm(client, token, "corta")

    assert rejected.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
    assert password_hash(migrated_database_url) == before
    assert confirm(client, token).status_code == HTTPStatus.NO_CONTENT


def test_failure_inside_the_transaction_leaves_everything_unchanged(
    client: TestClient, settings: Settings, migrated_database_url: str
) -> None:
    api_session = client.post(
        "/auth/login", json={"email": OPERATOR_EMAIL, "password": OLD_PASSWORD}
    ).json()
    token = recovery_token(client, settings)
    before = password_hash(migrated_database_url)
    database = Database.from_settings(settings)

    def broken_notice(db: Session, identity: Identity, now: datetime) -> None:
        raise RuntimeError("induced failure")

    with pytest.raises(RuntimeError), database.transaction() as db:
        confirm_password_reset(db, token, NEW_PASSWORD, datetime.now(UTC), broken_notice)
    database.dispose()

    assert password_hash(migrated_database_url) == before
    assert scalar(migrated_database_url, "SELECT consumed_at FROM password_reset_requests") is None
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {api_session['access_token']}"})
    assert me.status_code == HTTPStatus.OK
    assert confirm(client, token).status_code == HTTPStatus.NO_CONTENT


class FailingTransport:
    def send(self, envelope: Envelope) -> None:
        raise smtplib.SMTPServerDisconnected("provider down")


def test_change_notice_is_queued_without_password_and_its_failure_keeps_the_change(
    client: TestClient, settings: Settings, migrated_database_url: str
) -> None:
    token = recovery_token(client, settings)

    confirm(client, token)
    deliver_pending(settings, FailingTransport())
    execute(
        migrated_database_url,
        "UPDATE outbound_emails SET next_attempt_at = now() - interval '1 hour' "
        "WHERE status = 'pending'",
    )
    transport = RecordingTransport()
    deliver_pending(settings, transport)

    [notice] = transport.sent
    assert notice.subject == "Your Tappy password was changed"
    assert NEW_PASSWORD not in notice.body
    assert login_status(client, NEW_PASSWORD) == HTTPStatus.OK
