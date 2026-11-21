import re
from collections.abc import Iterator
from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response

from tappy.identity.models import Role
from tappy.main import create_app
from tests.support import build_settings, create_identity, scalar

ADMIN = "admin@tappy.example"
OPERATOR = "operadora@tappy.example"
PASSWORD = "panel interno seguro 2026"
CSRF_FIELD = re.compile(r'name="csrftoken" value="([^"]+)"')


@pytest.fixture
def client(migrated_database_url: str) -> Iterator[TestClient]:
    create_identity(migrated_database_url, ADMIN, PASSWORD, role=Role.ADMIN)
    create_identity(migrated_database_url, OPERATOR, PASSWORD)
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
            "username": ADMIN,
            "password": PASSWORD,
            "csrftoken": csrf_token(client, "/admin/login"),
        },
    )


def test_admin_creates_merchant_and_assigns_operator_from_panel(
    client: TestClient, migrated_database_url: str
) -> None:
    sign_in(client)
    created = client.post(
        "/admin/merchants/create",
        data={"name": "Tienda Demo A", "csrftoken": csrf_token(client, "/admin/merchants")},
        follow_redirects=False,
    )
    merchant_id = scalar(migrated_database_url, "SELECT id FROM merchants")
    operator_id = scalar(
        migrated_database_url, "SELECT id FROM identities WHERE email = :e", {"e": OPERATOR}
    )

    assigned = client.post(
        f"/admin/merchants/{merchant_id}/members",
        data={
            "operator_reference": str(operator_id),
            "csrftoken": csrf_token(client, "/admin/merchants"),
        },
        follow_redirects=False,
    )
    repeated = client.post(
        f"/admin/merchants/{merchant_id}/members",
        data={
            "operator_reference": str(operator_id),
            "csrftoken": csrf_token(client, "/admin/merchants"),
        },
        follow_redirects=False,
    )
    listing = client.get("/admin/merchants")

    assert created.status_code == HTTPStatus.SEE_OTHER
    assert assigned.status_code == HTTPStatus.SEE_OTHER
    assert repeated.status_code == HTTPStatus.SEE_OTHER
    assert "Tienda Demo A" in listing.text
    assert OPERATOR in listing.text
    assert "already a member" in listing.text
    assert scalar(migrated_database_url, "SELECT count(*) FROM memberships") == 1


def test_merchant_form_requires_csrf_and_an_admin(
    client: TestClient, migrated_database_url: str
) -> None:
    anonymous = client.post(
        "/admin/merchants/create",
        data={"name": "Intruso", "csrftoken": csrf_token(client, "/admin/login")},
        follow_redirects=False,
    )
    sign_in(client)
    without_csrf = client.post(
        "/admin/merchants/create", data={"name": "Sin CSRF"}, follow_redirects=False
    )

    assert anonymous.status_code == HTTPStatus.SEE_OTHER
    assert "/admin/login" in anonymous.headers["location"]
    assert without_csrf.status_code == HTTPStatus.FORBIDDEN
    assert scalar(migrated_database_url, "SELECT count(*) FROM merchants") == 0


@pytest.mark.parametrize("name", ["   ", "N" * 121])
def test_panel_rejects_blank_or_overlong_names_without_creating(
    client: TestClient, migrated_database_url: str, name: str
) -> None:
    sign_in(client)

    response = client.post(
        "/admin/merchants/create",
        data={"name": name, "csrftoken": csrf_token(client, "/admin/merchants")},
        follow_redirects=False,
    )
    listing = client.get("/admin/merchants")

    assert response.status_code == HTTPStatus.SEE_OTHER
    assert "Merchant name must have between 1 and 120 characters" in listing.text
    assert scalar(migrated_database_url, "SELECT count(*) FROM merchants") == 0


CLABE = "012180000123456782"


def configure_receiver(client: TestClient, merchant_id: object, form: dict[str, str]) -> Response:
    return client.post(
        f"/admin/merchants/{merchant_id}/receiver",
        data={**form, "csrftoken": csrf_token(client, "/admin/merchants")},
        follow_redirects=False,
    )


def test_admin_configures_and_disables_receiver_from_panel(
    client: TestClient, migrated_database_url: str
) -> None:
    sign_in(client)
    client.post(
        "/admin/merchants/create",
        data={"name": "Tienda Demo A", "csrftoken": csrf_token(client, "/admin/merchants")},
    )
    merchant_id = scalar(migrated_database_url, "SELECT id FROM merchants")
    receiver = {
        "provider_account_id": "bank-account-demo-a",
        "beneficiary_name": "Tienda Demo A SA de CV",
        "clabe": CLABE,
    }

    enabled = configure_receiver(client, merchant_id, {**receiver, "enabled": "on"})
    enabled_page = client.get("/admin/merchants").text
    disabled = configure_receiver(client, merchant_id, receiver)
    disabled_page = client.get("/admin/merchants").text

    assert enabled.status_code == HTTPStatus.SEE_OTHER
    assert "Receiving account saved" in enabled_page
    assert "Tienda Demo A SA de CV" in enabled_page
    assert "**************6782" in enabled_page
    assert "Enabled" in enabled_page
    assert CLABE not in enabled_page
    assert disabled.status_code == HTTPStatus.SEE_OTHER
    assert "new charges are blocked until it is enabled" in disabled_page
    assert scalar(migrated_database_url, "SELECT enabled FROM receiving_accounts") is False


def test_panel_rejects_invalid_receiver_without_echoing_the_account(
    client: TestClient, migrated_database_url: str
) -> None:
    sign_in(client)
    client.post(
        "/admin/merchants/create",
        data={"name": "Tienda Demo A", "csrftoken": csrf_token(client, "/admin/merchants")},
    )
    merchant_id = scalar(migrated_database_url, "SELECT id FROM merchants")
    invalid_clabe = "012180000123456781"

    response = configure_receiver(
        client,
        merchant_id,
        {
            "provider_account_id": "bank-account-demo-a",
            "beneficiary_name": "Tienda Demo A SA de CV",
            "clabe": invalid_clabe,
        },
    )
    page = client.get("/admin/merchants").text
    without_csrf = client.post(
        f"/admin/merchants/{merchant_id}/receiver",
        data={"provider_account_id": "x", "beneficiary_name": "x", "clabe": CLABE},
        follow_redirects=False,
    )

    assert response.status_code == HTTPStatus.SEE_OTHER
    assert "CLABE must have 18 digits and a valid check digit" in page
    assert invalid_clabe not in page
    assert without_csrf.status_code == HTTPStatus.FORBIDDEN
    assert scalar(migrated_database_url, "SELECT count(*) FROM receiving_accounts") == 0
