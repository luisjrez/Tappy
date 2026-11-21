import hashlib
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient

from tappy.identity.models import IdentityStatus, Role
from tappy.main import create_app
from tests.support import MovableClock, build_settings, create_identity, execute, scalar

OPERATOR_EMAIL = "operadora@tappy.example"
OPERATOR_PASSWORD = "mostrador seguro 2026"


@pytest.fixture
def client(migrated_database_url: str) -> Iterator[TestClient]:
    with TestClient(create_app(build_settings(database_url=migrated_database_url))) as client:
        yield client


def test_active_operator_logs_in_and_reads_own_identity(
    client: TestClient, migrated_database_url: str
) -> None:
    reference = create_identity(migrated_database_url, OPERATOR_EMAIL, OPERATOR_PASSWORD)

    session = client.post(
        "/auth/login", json={"email": OPERATOR_EMAIL, "password": OPERATOR_PASSWORD}
    )
    token = session.json()["access_token"]
    identity = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert session.status_code == HTTPStatus.OK
    assert session.json()["token_type"] == "bearer"
    assert set(session.json()) == {
        "access_token",
        "token_type",
        "expires_at",
        "refresh_token",
        "refresh_expires_at",
    }
    assert identity.status_code == HTTPStatus.OK
    assert identity.json() == {
        "reference": reference,
        "email": OPERATOR_EMAIL,
        "role": "operator",
        "status": "active",
    }
    assert OPERATOR_PASSWORD not in identity.text
    assert token not in identity.text


@pytest.mark.parametrize(
    ("email", "password", "status"),
    [
        (OPERATOR_EMAIL, "not the right passphrase", IdentityStatus.ACTIVE),
        (OPERATOR_EMAIL, OPERATOR_PASSWORD, IdentityStatus.INACTIVE),
        ("nadie@tappy.example", OPERATOR_PASSWORD, IdentityStatus.ACTIVE),
        ("not-an-email", OPERATOR_PASSWORD, IdentityStatus.ACTIVE),
    ],
)
def test_rejected_logins_share_one_generic_error_and_create_no_session(
    client: TestClient,
    migrated_database_url: str,
    email: str,
    password: str,
    status: IdentityStatus,
) -> None:
    create_identity(migrated_database_url, OPERATOR_EMAIL, OPERATOR_PASSWORD, status=status)

    response = client.post("/auth/login", json={"email": email, "password": password})

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {"detail": "Invalid email or password"}
    assert scalar(migrated_database_url, "SELECT count(*) FROM access_sessions") == 0


def test_requests_without_valid_token_are_rejected(
    client: TestClient, migrated_database_url: str
) -> None:
    create_identity(migrated_database_url, OPERATOR_EMAIL, OPERATOR_PASSWORD)
    token = client.post(
        "/auth/login", json={"email": OPERATOR_EMAIL, "password": OPERATOR_PASSWORD}
    ).json()["access_token"]
    altered = token[:-1] + ("A" if token[-1] != "A" else "B")

    responses = [
        client.get("/auth/me"),
        client.get("/auth/me", headers={"Authorization": f"Bearer {altered}"}),
        client.get("/auth/me", headers={"Authorization": f"Basic {token}"}),
    ]

    for response in responses:
        assert response.status_code == HTTPStatus.UNAUTHORIZED
        assert response.headers["www-authenticate"] == "Bearer"


def test_each_token_only_reveals_its_own_identity(
    client: TestClient, migrated_database_url: str
) -> None:
    own_reference = create_identity(migrated_database_url, OPERATOR_EMAIL, OPERATOR_PASSWORD)
    other_reference = create_identity(
        migrated_database_url, "otra@tappy.example", "otra frase segura 2026"
    )
    other_token = client.post(
        "/auth/login", json={"email": "otra@tappy.example", "password": "otra frase segura 2026"}
    ).json()["access_token"]

    response = client.get(
        "/auth/me",
        params={"email": OPERATOR_EMAIL, "reference": own_reference},
        headers={"Authorization": f"Bearer {other_token}"},
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json()["reference"] == other_reference
    assert response.json()["email"] == "otra@tappy.example"


def test_expired_token_is_rejected(migrated_database_url: str) -> None:
    clock = MovableClock(datetime(2026, 11, 20, 12, 0, tzinfo=UTC))
    create_identity(migrated_database_url, OPERATOR_EMAIL, OPERATOR_PASSWORD)
    app = create_app(build_settings(database_url=migrated_database_url), clock=clock)

    with TestClient(app) as client:
        token = client.post(
            "/auth/login", json={"email": OPERATOR_EMAIL, "password": OPERATOR_PASSWORD}
        ).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        clock.advance(timedelta(minutes=14, seconds=59))
        before_expiry = client.get("/auth/me", headers=headers)
        clock.advance(timedelta(seconds=1))
        at_expiry = client.get("/auth/me", headers=headers)

    assert before_expiry.status_code == HTTPStatus.OK
    assert at_expiry.status_code == HTTPStatus.UNAUTHORIZED


def test_only_a_digest_of_the_token_is_stored(
    client: TestClient, migrated_database_url: str
) -> None:
    create_identity(migrated_database_url, OPERATOR_EMAIL, OPERATOR_PASSWORD)
    token = client.post(
        "/auth/login", json={"email": OPERATOR_EMAIL, "password": OPERATOR_PASSWORD}
    ).json()["access_token"]

    stored = scalar(migrated_database_url, "SELECT token_digest FROM access_sessions")

    assert stored == hashlib.sha256(token.encode()).hexdigest()
    assert stored != token


def test_active_administrator_logs_in(client: TestClient, migrated_database_url: str) -> None:
    create_identity(
        migrated_database_url, "admin@tappy.example", OPERATOR_PASSWORD, role=Role.ADMIN
    )

    login_response = client.post(
        "/auth/login", json={"email": "admin@tappy.example", "password": OPERATOR_PASSWORD}
    )
    identity = client.get(
        "/auth/me", headers={"Authorization": f"Bearer {login_response.json()['access_token']}"}
    )

    assert identity.status_code == HTTPStatus.OK
    assert identity.json()["role"] == "admin"


def test_token_stops_working_when_identity_becomes_inactive(
    client: TestClient, migrated_database_url: str
) -> None:
    create_identity(migrated_database_url, OPERATOR_EMAIL, OPERATOR_PASSWORD)
    token = client.post(
        "/auth/login", json={"email": OPERATOR_EMAIL, "password": OPERATOR_PASSWORD}
    ).json()["access_token"]

    execute(migrated_database_url, "UPDATE identities SET status = 'inactive'")
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_revoked_session_is_rejected(client: TestClient, migrated_database_url: str) -> None:
    create_identity(migrated_database_url, OPERATOR_EMAIL, OPERATOR_PASSWORD)
    token = client.post(
        "/auth/login", json={"email": OPERATOR_EMAIL, "password": OPERATOR_PASSWORD}
    ).json()["access_token"]

    execute(migrated_database_url, "UPDATE access_sessions SET revoked_at = now()")
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == HTTPStatus.UNAUTHORIZED
