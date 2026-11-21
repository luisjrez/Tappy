import re
from collections.abc import Iterator
from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response

from tappy.identity.models import Role
from tappy.main import create_app
from tests.support import build_settings, create_identity, execute, scalar

ADMIN_EMAIL = "admin@tappy.example"
OPERATOR_EMAIL = "operadora@tappy.example"
PASSWORD = "panel interno seguro 2026"
CSRF_FIELD = re.compile(r'name="csrftoken" value="([^"]+)"')


@pytest.fixture
def client(migrated_database_url: str) -> Iterator[TestClient]:
    create_identity(migrated_database_url, ADMIN_EMAIL, PASSWORD, role=Role.ADMIN)
    create_identity(migrated_database_url, OPERATOR_EMAIL, PASSWORD)
    app = create_app(build_settings(database_url=migrated_database_url))
    with TestClient(app, base_url="https://testserver") as client:
        yield client


def csrf_token(client: TestClient, path: str = "/admin/login") -> str:
    match = CSRF_FIELD.search(client.get(path).text)
    assert match is not None
    return match.group(1)


def panel_login(client: TestClient, email: str) -> Response:
    return client.post(
        "/admin/login",
        data={"username": email, "password": PASSWORD, "csrftoken": csrf_token(client)},
        follow_redirects=False,
    )


def panel_status(client: TestClient) -> int:
    return client.get("/admin/", follow_redirects=False).status_code


def test_admin_enters_panel_and_logout_revokes_access(
    client: TestClient, migrated_database_url: str
) -> None:
    login = panel_login(client, ADMIN_EMAIL)
    inside = client.get("/admin/", follow_redirects=False)
    token = csrf_token(client, "/admin/")

    logout = client.post("/admin/logout", data={"csrftoken": token}, follow_redirects=False)

    assert login.status_code == HTTPStatus.SEE_OTHER
    assert inside.status_code == HTTPStatus.OK
    assert ADMIN_EMAIL in inside.text
    assert logout.status_code == HTTPStatus.SEE_OTHER
    assert panel_status(client) != HTTPStatus.OK
    assert (
        scalar(
            migrated_database_url, "SELECT count(*) FROM access_sessions WHERE revoked_at IS NULL"
        )
        == 0
    )


def test_anonymous_visitor_is_sent_to_login(client: TestClient) -> None:
    response = client.get("/admin/", follow_redirects=False)

    assert response.status_code in {HTTPStatus.FOUND, HTTPStatus.SEE_OTHER}
    assert "/admin/login" in response.headers["location"]


def test_operator_cannot_enter_panel(client: TestClient) -> None:
    login = panel_login(client, OPERATOR_EMAIL)

    assert login.status_code == HTTPStatus.BAD_REQUEST
    assert "Invalid email or password" in login.text
    assert panel_status(client) != HTTPStatus.OK
    assert OPERATOR_EMAIL not in client.get("/admin/").text


def test_api_bearer_token_does_not_open_panel(client: TestClient) -> None:
    token = client.post("/auth/login", json={"email": ADMIN_EMAIL, "password": PASSWORD}).json()[
        "access_token"
    ]

    response = client.get(
        "/admin/", headers={"Authorization": f"Bearer {token}"}, follow_redirects=False
    )

    assert response.status_code != HTTPStatus.OK


def test_revoked_panel_session_loses_access(client: TestClient, migrated_database_url: str) -> None:
    panel_login(client, ADMIN_EMAIL)
    assert panel_status(client) == HTTPStatus.OK

    execute(migrated_database_url, "UPDATE access_sessions SET revoked_at = now()")

    assert panel_status(client) != HTTPStatus.OK


@pytest.mark.parametrize("submitted", [None, "forged-token", "tampered"])
def test_logout_without_valid_csrf_is_rejected_without_changes(
    client: TestClient, migrated_database_url: str, submitted: str | None
) -> None:
    panel_login(client, ADMIN_EMAIL)
    valid = csrf_token(client, "/admin/")
    data = (
        {}
        if submitted is None
        else {"csrftoken": valid[:-2] + "xx" if submitted == "tampered" else submitted}
    )

    response = client.post("/admin/logout", data=data, follow_redirects=False)

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert panel_status(client) == HTTPStatus.OK
    assert (
        scalar(
            migrated_database_url, "SELECT count(*) FROM access_sessions WHERE revoked_at IS NULL"
        )
        == 1
    )


def test_login_without_csrf_is_rejected(client: TestClient, migrated_database_url: str) -> None:
    client.get("/admin/login")

    response = client.post(
        "/admin/login",
        data={"username": ADMIN_EMAIL, "password": PASSWORD},
        follow_redirects=False,
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert scalar(migrated_database_url, "SELECT count(*) FROM access_sessions") == 0


@pytest.mark.parametrize("secure", [True, False])
def test_panel_cookie_flags_follow_environment(migrated_database_url: str, secure: bool) -> None:
    create_identity(migrated_database_url, ADMIN_EMAIL, PASSWORD, role=Role.ADMIN)
    settings = build_settings(database_url=migrated_database_url).model_copy(
        update={"admin_secure_cookies": secure}
    )
    with TestClient(create_app(settings), base_url="https://testserver") as client:
        login = panel_login(client, ADMIN_EMAIL)

    session_cookie = next(
        header
        for header in login.headers.get_list("set-cookie")
        if header.startswith("tappy_admin_session=")
    ).lower()
    assert "httponly" in session_cookie
    assert "samesite=strict" in session_cookie
    assert ("secure" in session_cookie.split("; ")) is secure
