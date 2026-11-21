import re
from collections.abc import Iterator
from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient

from tappy.main import create_app
from tests.support import build_settings, create_identity, scalar

OPERATOR_EMAIL = "operadora@tappy.example"
PASSWORD = "mostrador seguro 2026"
GENERIC = "If the account exists, a recovery email may be sent"
CSRF_FIELD = re.compile(r'name="csrftoken" value="([^"]+)"')


@pytest.fixture
def client(migrated_database_url: str) -> Iterator[TestClient]:
    create_identity(migrated_database_url, OPERATOR_EMAIL, PASSWORD)
    app = create_app(build_settings(database_url=migrated_database_url))
    with TestClient(app, base_url="https://testserver") as client:
        yield client


def csrf_token(client: TestClient, path: str) -> str:
    match = CSRF_FIELD.search(client.get(path).text)
    assert match is not None
    return match.group(1)


def test_login_page_links_to_public_recovery_form(client: TestClient) -> None:
    login = client.get("/admin/login")
    form = client.get("/admin/forgot-password", follow_redirects=False)

    assert 'href="https://testserver/admin/forgot-password"' in login.text
    assert form.status_code == HTTPStatus.OK
    assert 'name="email"' in form.text


@pytest.mark.parametrize("email", [OPERATOR_EMAIL, "nadie@tappy.example"])
def test_recovery_form_answers_generically_for_any_account(
    client: TestClient, migrated_database_url: str, email: str
) -> None:
    response = client.post(
        "/admin/forgot-password",
        data={"email": email, "csrftoken": csrf_token(client, "/admin/forgot-password")},
        follow_redirects=False,
    )

    assert response.status_code == HTTPStatus.OK
    assert GENERIC in response.text
    assert scalar(migrated_database_url, "SELECT count(*) FROM recovery_jobs") == 1


def test_recovery_form_requires_csrf(client: TestClient, migrated_database_url: str) -> None:
    client.get("/admin/forgot-password")

    response = client.post(
        "/admin/forgot-password", data={"email": OPERATOR_EMAIL}, follow_redirects=False
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert scalar(migrated_database_url, "SELECT count(*) FROM recovery_jobs") == 0
