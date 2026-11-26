import uuid
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response

from tappy.identity.models import Role
from tappy.main import create_app
from tappy.merchants.receivers import ReceiverSettings, configure_receiver
from tappy.platform.database import Database
from tests.support import build_settings, create_identity, scalar, wait_until_blocked_on_a_lock

ADMIN = "admin@tappy.example"
OPERATOR_A = "operadora.a@tappy.example"
OPERATOR_B = "operador.b@tappy.example"
PASSWORD = "credencial operativa 2026"
CLABE_A = "012180000123456782"
CLABE_B = "072180000999900017"
CONFIGURED_AT = datetime(2026, 11, 21, 12, 0, tzinfo=UTC)
BLOCKED_DISABLED = "The receiving account is disabled; new charges are blocked until it is enabled"
RECEIVER_A: dict[str, object] = {
    "provider_account_id": "bank-account-demo-a",
    "beneficiary_name": "Tienda Demo A SA de CV",
    "clabe": CLABE_A,
    "enabled": True,
}
BLOCKED_MISSING = "No receiving account is configured; new charges are blocked"


@pytest.fixture
def client(migrated_database_url: str) -> Iterator[TestClient]:
    create_identity(migrated_database_url, ADMIN, PASSWORD, role=Role.ADMIN)
    create_identity(migrated_database_url, OPERATOR_A, PASSWORD)
    create_identity(migrated_database_url, OPERATOR_B, PASSWORD)
    with TestClient(create_app(build_settings(database_url=migrated_database_url))) as client:
        yield client


def bearer(client: TestClient, email: str) -> dict[str, str]:
    tokens = client.post("/auth/login", json={"email": email, "password": PASSWORD}).json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def reference(database_url: str, email: str) -> str:
    return str(scalar(database_url, "SELECT id FROM identities WHERE email = :e", {"e": email}))


def merchant_with_operator(
    client: TestClient, database_url: str, admin: dict[str, str], name: str, operator: str
) -> str:
    merchant_id: str = client.post("/merchants", json={"name": name}, headers=admin).json()["id"]
    client.post(
        f"/merchants/{merchant_id}/members",
        json={"operator_reference": reference(database_url, operator)},
        headers=admin,
    )
    return merchant_id


def configure(
    client: TestClient, headers: dict[str, str], merchant_id: str, **changes: object
) -> Response:
    payload = {**RECEIVER_A, **changes}
    return client.put(f"/merchants/{merchant_id}/receiver", json=payload, headers=headers)


def issuance_check(client: TestClient, headers: dict[str, str], merchant_id: str) -> Response:
    return client.post(f"/merchants/{merchant_id}/issuance-check", json={}, headers=headers)


def test_operator_reads_beneficiary_and_masked_account_of_own_receiver(
    client: TestClient, migrated_database_url: str
) -> None:
    admin = bearer(client, ADMIN)
    merchant_a = merchant_with_operator(
        client, migrated_database_url, admin, "Tienda Demo A", OPERATOR_A
    )

    configured = configure(client, admin, merchant_a)
    receiver = client.get(f"/merchants/{merchant_a}/receiver", headers=bearer(client, OPERATOR_A))
    check = issuance_check(client, bearer(client, OPERATOR_A), merchant_a)

    expected = {
        "beneficiary_name": "Tienda Demo A SA de CV",
        "masked_account": "**************6782",
        "enabled": True,
        "can_issue": True,
        "blocked_reason": None,
    }
    assert configured.status_code == HTTPStatus.OK
    assert configured.json() == expected
    assert receiver.status_code == HTTPStatus.OK
    assert receiver.json() == expected
    assert check.status_code == HTTPStatus.OK
    assert check.json() == expected
    assert CLABE_A not in receiver.text
    assert "bank-account-demo-a" not in receiver.text
    assert scalar(migrated_database_url, "SELECT count(*) FROM receiving_accounts") == 1
    assert (
        scalar(
            migrated_database_url,
            "SELECT count(*) FROM receiving_accounts WHERE account_last4 = '6782'",
        )
        == 1
    )


def test_full_account_number_is_never_stored(
    client: TestClient, migrated_database_url: str
) -> None:
    admin = bearer(client, ADMIN)
    merchant_a = merchant_with_operator(
        client, migrated_database_url, admin, "Tienda Demo A", OPERATOR_A
    )

    configure(client, admin, merchant_a)
    stored = scalar(
        migrated_database_url,
        "SELECT row_to_json(receiving_accounts)::text FROM receiving_accounts",
    )

    assert CLABE_A not in str(stored)


@pytest.mark.parametrize(
    "field_values",
    [
        {"clabe": "012180000123456781"},
        {"clabe": "01218000012345678"},
        {"clabe": "01218000012345678a"},
        {"beneficiary_name": "   "},
        {"provider_account_id": ""},
        {"provider_account_id": "has spaces"},
    ],
)
def test_invalid_receiver_configuration_is_rejected(
    client: TestClient, migrated_database_url: str, field_values: dict[str, str]
) -> None:
    admin = bearer(client, ADMIN)
    merchant_a = merchant_with_operator(
        client, migrated_database_url, admin, "Tienda Demo A", OPERATOR_A
    )

    response = configure(client, admin, merchant_a, **field_values)

    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
    assert str(field_values.get("clabe", CLABE_A)) not in response.text
    assert scalar(migrated_database_url, "SELECT count(*) FROM receiving_accounts") == 0


def test_only_administrators_configure_receivers(
    client: TestClient, migrated_database_url: str
) -> None:
    admin = bearer(client, ADMIN)
    merchant_a = merchant_with_operator(
        client, migrated_database_url, admin, "Tienda Demo A", OPERATOR_A
    )

    by_operator = configure(client, bearer(client, OPERATOR_A), merchant_a)
    anonymous = configure(client, {}, merchant_a)

    assert by_operator.status_code == HTTPStatus.FORBIDDEN
    assert anonymous.status_code == HTTPStatus.UNAUTHORIZED
    assert scalar(migrated_database_url, "SELECT count(*) FROM receiving_accounts") == 0


def test_disabled_receiver_blocks_issuance_with_an_explanation(
    client: TestClient, migrated_database_url: str
) -> None:
    admin = bearer(client, ADMIN)
    merchant_a = merchant_with_operator(
        client, migrated_database_url, admin, "Tienda Demo A", OPERATOR_A
    )
    configure(client, admin, merchant_a, enabled=False)
    operator_a = bearer(client, OPERATOR_A)

    check = issuance_check(client, operator_a, merchant_a)
    receiver = client.get(f"/merchants/{merchant_a}/receiver", headers=operator_a)

    assert check.status_code == HTTPStatus.CONFLICT
    assert check.json() == {"detail": BLOCKED_DISABLED}
    assert receiver.json()["enabled"] is False
    assert receiver.json()["can_issue"] is False
    assert receiver.json()["blocked_reason"] == BLOCKED_DISABLED


def test_merchant_without_receiver_cannot_issue(
    client: TestClient, migrated_database_url: str
) -> None:
    admin = bearer(client, ADMIN)
    merchant_a = merchant_with_operator(
        client, migrated_database_url, admin, "Tienda Demo A", OPERATOR_A
    )
    operator_a = bearer(client, OPERATOR_A)

    check = issuance_check(client, operator_a, merchant_a)
    receiver = client.get(f"/merchants/{merchant_a}/receiver", headers=operator_a)

    assert check.status_code == HTTPStatus.CONFLICT
    assert check.json() == {"detail": BLOCKED_MISSING}
    assert receiver.status_code == HTTPStatus.NOT_FOUND
    assert receiver.json() == {"detail": "Receiving account not configured"}


def test_requests_cannot_choose_a_foreign_receiver(
    client: TestClient, migrated_database_url: str
) -> None:
    admin = bearer(client, ADMIN)
    merchant_a = merchant_with_operator(
        client, migrated_database_url, admin, "Tienda Demo A", OPERATOR_A
    )
    merchant_b = merchant_with_operator(
        client, migrated_database_url, admin, "Tienda Demo B", OPERATOR_B
    )
    configure(client, admin, merchant_a, enabled=False)
    configure(
        client,
        admin,
        merchant_b,
        provider_account_id="bank-account-demo-b",
        beneficiary_name="Tienda Demo B",
        clabe=CLABE_B,
    )
    operator_a = bearer(client, OPERATOR_A)

    smuggled = client.post(
        f"/merchants/{merchant_a}/issuance-check",
        json={"provider_account_id": "bank-account-demo-b"},
        headers=operator_a,
    )
    foreign_check = issuance_check(client, operator_a, merchant_b)
    foreign_read = client.get(f"/merchants/{merchant_b}/receiver", headers=operator_a)
    reused = configure(client, admin, merchant_a, provider_account_id="bank-account-demo-b")

    assert smuggled.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
    assert "Tienda Demo B" not in smuggled.text
    assert foreign_check.status_code == HTTPStatus.NOT_FOUND
    assert foreign_read.status_code == HTTPStatus.NOT_FOUND
    assert reused.status_code == HTTPStatus.CONFLICT
    assert reused.json() == {"detail": "That receiving account belongs to another merchant"}
    assert (
        scalar(
            migrated_database_url,
            "SELECT provider_account_id FROM receiving_accounts WHERE merchant_id = :id",
            {"id": merchant_a},
        )
        == "bank-account-demo-a"
    )


def test_disabling_keeps_the_receiver_and_merchant_records(
    client: TestClient, migrated_database_url: str
) -> None:
    admin = bearer(client, ADMIN)
    merchant_a = merchant_with_operator(
        client, migrated_database_url, admin, "Tienda Demo A", OPERATOR_A
    )
    configure(client, admin, merchant_a)
    receiver_id = scalar(migrated_database_url, "SELECT id FROM receiving_accounts")
    operator_a = bearer(client, OPERATOR_A)

    disabled = configure(client, admin, merchant_a, enabled=False)
    merchant = client.get(f"/merchants/{merchant_a}", headers=operator_a)
    blocked = issuance_check(client, operator_a, merchant_a)
    enabled = configure(client, admin, merchant_a, enabled=True)
    allowed = issuance_check(client, operator_a, merchant_a)

    assert disabled.json()["blocked_reason"] == BLOCKED_DISABLED
    assert disabled.json()["masked_account"] == "**************6782"
    assert merchant.status_code == HTTPStatus.OK
    assert [member["email"] for member in merchant.json()["members"]] == [OPERATOR_A]
    assert blocked.status_code == HTTPStatus.CONFLICT
    assert enabled.json()["can_issue"] is True
    assert allowed.status_code == HTTPStatus.OK
    assert scalar(migrated_database_url, "SELECT id FROM receiving_accounts") == receiver_id
    assert scalar(migrated_database_url, "SELECT count(*) FROM receiving_accounts") == 1


def test_unknown_merchant_has_no_receiver(client: TestClient) -> None:
    admin = bearer(client, ADMIN)
    missing = "00000000-0000-0000-0000-000000000000"

    configured = configure(client, admin, missing)
    read = client.get(f"/merchants/{missing}/receiver", headers=admin)

    assert configured.status_code == HTTPStatus.NOT_FOUND
    assert read.status_code == HTTPStatus.NOT_FOUND


def test_racing_first_configurations_keep_one_receiver(
    client: TestClient, migrated_database_url: str
) -> None:
    admin = bearer(client, ADMIN)
    merchant_a = merchant_with_operator(
        client, migrated_database_url, admin, "Tienda Demo A", OPERATOR_A
    )
    first = ReceiverSettings("bank-account-demo-a", "Primera configuracion", CLABE_A, True)
    database = Database.from_settings(build_settings(database_url=migrated_database_url))
    try:
        with database.session_factory() as racing, racing.begin():
            configure_receiver(racing, uuid.UUID(merchant_a), first, CONFIGURED_AT)
            with ThreadPoolExecutor(max_workers=1) as pool:
                attempt = pool.submit(configure, client, admin, merchant_a)
                wait_until_blocked_on_a_lock(migrated_database_url)
                racing.commit()
                response = attempt.result(timeout=10)
    finally:
        database.dispose()

    assert response.status_code == HTTPStatus.OK
    assert response.json()["beneficiary_name"] == "Tienda Demo A SA de CV"
    assert scalar(migrated_database_url, "SELECT count(*) FROM receiving_accounts") == 1


@pytest.mark.parametrize(
    "payload",
    [
        {"provider_account_id": "bank-account-demo-a", "beneficiary_name": "A", "clabe": CLABE_A},
        {**RECEIVER_A, "clabe": int(CLABE_A)},
        {**RECEIVER_A, "enabled": "maybe"},
    ],
)
def test_malformed_bodies_never_echo_the_account(
    client: TestClient, migrated_database_url: str, payload: dict[str, object]
) -> None:
    admin = bearer(client, ADMIN)
    merchant_a = merchant_with_operator(
        client, migrated_database_url, admin, "Tienda Demo A", OPERATOR_A
    )

    response = client.put(f"/merchants/{merchant_a}/receiver", json=payload, headers=admin)

    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
    assert CLABE_A.lstrip("0") not in response.text
    assert all(set(issue) == {"type", "loc", "msg"} for issue in response.json()["detail"])
