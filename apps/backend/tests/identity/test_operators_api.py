from collections.abc import Iterator
from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient

from tappy.identity.models import Role
from tappy.main import create_app
from tests.support import build_settings, create_identity, scalar

ADMIN_EMAIL = "admin@tappy.example"
OPERATOR_EMAIL = "operadora@tappy.example"
PASSWORD = "credencial operativa 2026"
NEW_OPERATOR = "nuevo.operador@tappy.example"
INITIAL_PASSWORD = "entregada en persona 2026"


@pytest.fixture
def client(migrated_database_url: str) -> Iterator[TestClient]:
    create_identity(migrated_database_url, ADMIN_EMAIL, PASSWORD, role=Role.ADMIN)
    create_identity(migrated_database_url, OPERATOR_EMAIL, PASSWORD)
    with TestClient(create_app(build_settings(database_url=migrated_database_url))) as client:
        yield client


def bearer(client: TestClient, email: str, password: str = PASSWORD) -> dict[str, str]:
    response = client.post("/auth/login", json={"email": email, "password": password})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def identity_count(database_url: str) -> object:
    return scalar(database_url, "SELECT count(*) FROM identities")


def test_admin_creates_active_operator_without_echoing_the_secret(client: TestClient) -> None:
    admin = bearer(client, ADMIN_EMAIL)

    created = client.post(
        "/operators",
        json={"email": NEW_OPERATOR, "initial_password": INITIAL_PASSWORD},
        headers=admin,
    )
    fetched = client.get(f"/operators/{created.json()['reference']}", headers=admin)
    operator_login = client.post(
        "/auth/login", json={"email": NEW_OPERATOR, "password": INITIAL_PASSWORD}
    )

    assert created.status_code == HTTPStatus.CREATED
    assert created.json() == {
        "reference": created.json()["reference"],
        "email": NEW_OPERATOR,
        "role": "operator",
        "status": "active",
    }
    assert INITIAL_PASSWORD not in created.text
    assert fetched.json() == created.json()
    assert operator_login.status_code == HTTPStatus.OK


def operator_reference(database_url: str, email: str) -> str:
    return str(
        scalar(database_url, "SELECT id FROM identities WHERE email = :email", {"email": email})
    )


@pytest.mark.parametrize(
    ("actor", "expected"),
    [(None, HTTPStatus.UNAUTHORIZED), (OPERATOR_EMAIL, HTTPStatus.FORBIDDEN)],
)
def test_non_admins_cannot_create_or_deactivate_operators(
    client: TestClient, migrated_database_url: str, actor: str | None, expected: HTTPStatus
) -> None:
    headers = {} if actor is None else bearer(client, actor)
    target = operator_reference(migrated_database_url, OPERATOR_EMAIL)
    before = identity_count(migrated_database_url)

    created = client.post(
        "/operators",
        json={"email": NEW_OPERATOR, "initial_password": INITIAL_PASSWORD},
        headers=headers,
    )
    deactivated = client.post(f"/operators/{target}/deactivate", headers=headers)
    listed = client.get("/operators", headers=headers)
    fetched = client.get(f"/operators/{target}", headers=headers)

    assert created.status_code == expected
    assert deactivated.status_code == expected
    assert listed.status_code == expected
    assert fetched.status_code == expected
    assert identity_count(migrated_database_url) == before
    assert (
        scalar(
            migrated_database_url, "SELECT status FROM identities WHERE id = :id", {"id": target}
        )
        == "active"
    )


def test_repeated_email_is_rejected_without_duplicate(
    client: TestClient, migrated_database_url: str
) -> None:
    admin = bearer(client, ADMIN_EMAIL)
    before = identity_count(migrated_database_url)

    repeated = client.post(
        "/operators",
        json={"email": OPERATOR_EMAIL.upper(), "initial_password": INITIAL_PASSWORD},
        headers=admin,
    )

    assert repeated.status_code == HTTPStatus.CONFLICT
    assert identity_count(migrated_database_url) == before


def test_deactivated_operator_session_stops_authorizing(
    client: TestClient, migrated_database_url: str
) -> None:
    admin = bearer(client, ADMIN_EMAIL)
    operator_tokens = client.post(
        "/auth/login", json={"email": OPERATOR_EMAIL, "password": PASSWORD}
    ).json()
    target = operator_reference(migrated_database_url, OPERATOR_EMAIL)

    deactivated = client.post(f"/operators/{target}/deactivate", headers=admin)
    me = client.get(
        "/auth/me", headers={"Authorization": f"Bearer {operator_tokens['access_token']}"}
    )
    renewed = client.post("/auth/refresh", json={"refresh_token": operator_tokens["refresh_token"]})
    fetched = client.get(f"/operators/{target}", headers=admin)

    assert deactivated.status_code == HTTPStatus.OK
    assert deactivated.json()["status"] == "inactive"
    assert me.status_code == HTTPStatus.UNAUTHORIZED
    assert renewed.status_code == HTTPStatus.UNAUTHORIZED
    assert fetched.json()["status"] == "inactive"


def test_admin_identities_are_not_managed_as_operators(
    client: TestClient, migrated_database_url: str
) -> None:
    admin = bearer(client, ADMIN_EMAIL)
    admin_reference = operator_reference(migrated_database_url, ADMIN_EMAIL)

    response = client.post(f"/operators/{admin_reference}/deactivate", headers=admin)

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json() == {"detail": "Identity not found"}
    assert client.get("/auth/me", headers=admin).status_code == HTTPStatus.OK


def test_invalid_initial_credential_is_rejected_without_echo(
    client: TestClient, migrated_database_url: str
) -> None:
    admin = bearer(client, ADMIN_EMAIL)
    before = identity_count(migrated_database_url)

    response = client.post(
        "/operators", json={"email": NEW_OPERATOR, "initial_password": "corta"}, headers=admin
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
    assert "corta" not in response.text
    assert identity_count(migrated_database_url) == before


def test_there_is_no_public_sign_up_route(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()

    post_routes = {path for path, operations in schema["paths"].items() if "post" in operations}

    assert post_routes == {
        "/auth/login",
        "/auth/refresh",
        "/auth/logout",
        "/operators",
        "/operators/{reference}/deactivate",
    }
