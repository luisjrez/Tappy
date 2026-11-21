import re
from collections.abc import Iterator
from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response

from tappy.identity.models import Role
from tappy.main import create_app
from tests.support import build_settings, create_identity, scalar

ADMIN_EMAIL = "admin@tappy.example"
OPERATOR_EMAIL = "operadora@tappy.example"
PASSWORD = "panel interno seguro 2026"
NEW_OPERATOR = "nuevo.operador@tappy.example"
INITIAL_PASSWORD = "entregada en persona 2026"
CSRF_FIELD = re.compile(r'name="csrftoken" value="([^"]+)"')


@pytest.fixture
def client(migrated_database_url: str) -> Iterator[TestClient]:
    create_identity(migrated_database_url, ADMIN_EMAIL, PASSWORD, role=Role.ADMIN)
    create_identity(migrated_database_url, OPERATOR_EMAIL, PASSWORD)
    app = create_app(build_settings(database_url=migrated_database_url))
    with TestClient(app, base_url="https://testserver") as client:
        yield client


def csrf_token(client: TestClient, path: str) -> str:
    match = CSRF_FIELD.search(client.get(path).text)
    assert match is not None
    return match.group(1)


def sign_in(client: TestClient) -> None:
    client.post(
        "/admin/login",
        data={
            "username": ADMIN_EMAIL,
            "password": PASSWORD,
            "csrftoken": csrf_token(client, "/admin/login"),
        },
    )


def create_from_form(client: TestClient, email: str, password: str = INITIAL_PASSWORD) -> Response:
    return client.post(
        "/admin/operators/create",
        data={
            "email": email,
            "initial_password": password,
            "csrftoken": csrf_token(client, "/admin/operators"),
        },
        follow_redirects=False,
    )


def identity_count(database_url: str) -> object:
    return scalar(database_url, "SELECT count(*) FROM identities")


def test_admin_creates_operator_from_form_and_sees_it_listed(
    client: TestClient, migrated_database_url: str
) -> None:
    sign_in(client)

    created = create_from_form(client, NEW_OPERATOR)
    listing = client.get(created.headers["location"])

    assert created.status_code == HTTPStatus.SEE_OTHER
    assert created.headers["location"].endswith("/admin/operators")
    assert f"Operator {NEW_OPERATOR} created" in listing.text
    assert INITIAL_PASSWORD not in listing.text
    assert (
        scalar(
            migrated_database_url,
            "SELECT status FROM identities WHERE email = :email",
            {"email": NEW_OPERATOR},
        )
        == "active"
    )


def test_anonymous_form_submission_changes_nothing(
    client: TestClient, migrated_database_url: str
) -> None:
    before = identity_count(migrated_database_url)
    token = csrf_token(client, "/admin/login")

    response = client.post(
        "/admin/operators/create",
        data={"email": NEW_OPERATOR, "initial_password": INITIAL_PASSWORD, "csrftoken": token},
        follow_redirects=False,
    )

    assert response.status_code == HTTPStatus.SEE_OTHER
    assert "/admin/login" in response.headers["location"]
    assert identity_count(migrated_database_url) == before


def test_form_without_csrf_changes_nothing(client: TestClient, migrated_database_url: str) -> None:
    sign_in(client)
    before = identity_count(migrated_database_url)

    response = client.post(
        "/admin/operators/create",
        data={"email": NEW_OPERATOR, "initial_password": INITIAL_PASSWORD},
        follow_redirects=False,
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert identity_count(migrated_database_url) == before


def test_repeated_email_in_form_is_rejected_without_duplicate(
    client: TestClient, migrated_database_url: str
) -> None:
    sign_in(client)
    before = identity_count(migrated_database_url)

    response = create_from_form(client, OPERATOR_EMAIL.upper())
    listing = client.get(response.headers["location"])

    assert response.status_code == HTTPStatus.SEE_OTHER
    assert "already exists" in listing.text
    assert INITIAL_PASSWORD not in listing.text
    assert identity_count(migrated_database_url) == before


def test_deactivation_from_panel_revokes_operator_session(
    client: TestClient, migrated_database_url: str
) -> None:
    operator_token = client.post(
        "/auth/login", json={"email": OPERATOR_EMAIL, "password": PASSWORD}
    ).json()["access_token"]
    reference = scalar(
        migrated_database_url,
        "SELECT id FROM identities WHERE email = :email",
        {"email": OPERATOR_EMAIL},
    )
    sign_in(client)

    response = client.post(
        f"/admin/operators/{reference}/deactivate",
        data={"csrftoken": csrf_token(client, "/admin/operators")},
        follow_redirects=False,
    )

    assert response.status_code == HTTPStatus.SEE_OTHER
    assert "deactivated" in client.get(response.headers["location"]).text
    assert (
        client.get("/auth/me", headers={"Authorization": f"Bearer {operator_token}"}).status_code
        == HTTPStatus.UNAUTHORIZED
    )


def test_anonymous_deactivation_changes_nothing(
    client: TestClient, migrated_database_url: str
) -> None:
    reference = scalar(
        migrated_database_url,
        "SELECT id FROM identities WHERE email = :email",
        {"email": OPERATOR_EMAIL},
    )

    response = client.post(
        f"/admin/operators/{reference}/deactivate",
        data={"csrftoken": csrf_token(client, "/admin/login")},
        follow_redirects=False,
    )

    assert response.status_code == HTTPStatus.SEE_OTHER
    assert "/admin/login" in response.headers["location"]
    assert (
        scalar(
            migrated_database_url,
            "SELECT status FROM identities WHERE email = :email",
            {"email": OPERATOR_EMAIL},
        )
        == "active"
    )


def test_reloading_after_creation_does_not_resubmit(client: TestClient) -> None:
    sign_in(client)
    created = create_from_form(client, NEW_OPERATOR)

    reloaded = client.get(created.headers["location"])
    reloaded_again = client.get(created.headers["location"])

    assert reloaded.status_code == HTTPStatus.OK
    assert "already exists" not in reloaded_again.text
