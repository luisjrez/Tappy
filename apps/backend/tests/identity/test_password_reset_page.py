import re
from collections.abc import Iterator
from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient

from tappy.main import create_app
from tappy.platform.config import Settings
from tests.support import build_settings, create_identity, scalar
from tests.support import recovery_token as shared_recovery_token

OPERATOR_EMAIL = "operadora@tappy.example"
OLD_PASSWORD = "mostrador seguro 2026"
NEW_PASSWORD = "nueva frase muy segura 2026"


@pytest.fixture
def settings(migrated_database_url: str) -> Settings:
    return build_settings(database_url=migrated_database_url)


@pytest.fixture
def client(settings: Settings, migrated_database_url: str) -> Iterator[TestClient]:
    create_identity(migrated_database_url, OPERATOR_EMAIL, OLD_PASSWORD)
    with TestClient(create_app(settings)) as client:
        yield client


def recovery_token(client: TestClient, settings: Settings) -> str:
    return shared_recovery_token(client, settings, OPERATOR_EMAIL)


def test_reset_page_is_self_contained_and_never_leaks_the_link(client: TestClient) -> None:
    page = client.get("/password-reset")

    assert page.status_code == HTTPStatus.OK
    assert page.headers["referrer-policy"] == "no-referrer"
    assert "no-store" in page.headers["cache-control"]
    assert "default-src 'none'" in page.headers["content-security-policy"]
    assert re.search(r'(src|href)="https?://', page.text) is None
    assert 'name="new_password"' in page.text
    assert 'name="confirm_password"' in page.text


def test_opening_the_page_does_not_consume_the_link(
    client: TestClient, settings: Settings, migrated_database_url: str
) -> None:
    token = recovery_token(client, settings)

    client.get("/password-reset")
    client.get(f"/password-reset?token={token}")

    assert scalar(migrated_database_url, "SELECT consumed_at FROM password_reset_requests") is None


def test_form_changes_password_and_points_back_to_sign_in(
    client: TestClient, settings: Settings
) -> None:
    token = recovery_token(client, settings)

    response = client.post(
        "/password-reset",
        data={"token": token, "new_password": NEW_PASSWORD, "confirm_password": NEW_PASSWORD},
    )

    assert response.status_code == HTTPStatus.OK
    assert "Your password was changed" in response.text
    assert 'href="/admin/login"' in response.text
    assert "set-cookie" not in response.headers
    login = client.post("/auth/login", json={"email": OPERATOR_EMAIL, "password": NEW_PASSWORD})
    assert login.status_code == HTTPStatus.OK


FORM_ERRORS = {
    "mismatch": ("different frase 2026 xx", "", "Passwords do not match"),
    "tampered": (NEW_PASSWORD, "tampered", "This link is invalid or has expired"),
}


@pytest.mark.parametrize("case", FORM_ERRORS)
def test_form_errors_are_safe_and_change_nothing(
    client: TestClient, settings: Settings, migrated_database_url: str, case: str
) -> None:
    confirmation, token_suffix, message = FORM_ERRORS[case]
    token = recovery_token(client, settings)

    response = client.post(
        "/password-reset",
        data={
            "token": token + token_suffix,
            "new_password": NEW_PASSWORD,
            "confirm_password": confirmation,
        },
    )

    assert response.status_code in {HTTPStatus.BAD_REQUEST, HTTPStatus.UNPROCESSABLE_CONTENT}
    assert message in response.text
    assert token not in response.text
    assert NEW_PASSWORD not in response.text
    assert scalar(migrated_database_url, "SELECT consumed_at FROM password_reset_requests") is None


def test_invalid_link_clears_the_stored_token(client: TestClient, settings: Settings) -> None:
    response = client.post(
        "/password-reset",
        data={"token": "unknown", "new_password": NEW_PASSWORD, "confirm_password": NEW_PASSWORD},
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert 'sessionStorage.removeItem("tappy-reset-token")' in response.text


def test_foreign_origin_cannot_submit_the_form(
    client: TestClient, settings: Settings, migrated_database_url: str
) -> None:
    token = recovery_token(client, settings)

    response = client.post(
        "/password-reset",
        data={"token": token, "new_password": NEW_PASSWORD, "confirm_password": NEW_PASSWORD},
        headers={"Origin": "https://evil.example"},
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert scalar(migrated_database_url, "SELECT consumed_at FROM password_reset_requests") is None


def test_oversized_form_fields_are_rejected(client: TestClient, settings: Settings) -> None:
    response = client.post(
        "/password-reset",
        data={"token": "x" * 300, "new_password": NEW_PASSWORD, "confirm_password": NEW_PASSWORD},
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
    assert "x" * 300 not in response.text
