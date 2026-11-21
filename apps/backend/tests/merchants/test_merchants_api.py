import time
import uuid
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response

from tappy.identity.models import Role
from tappy.identity.operators import deactivate_operator
from tappy.main import create_app
from tappy.platform.database import Database
from tests.support import build_settings, create_identity, execute, scalar

ADMIN = "admin@tappy.example"
OPERATOR_A = "operadora.a@tappy.example"
OPERATOR_B = "operador.b@tappy.example"
PASSWORD = "credencial operativa 2026"


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


def create_merchant(client: TestClient, admin: dict[str, str], name: str) -> str:
    response = client.post("/merchants", json={"name": name}, headers=admin)
    assert response.status_code == HTTPStatus.CREATED
    merchant_id: str = response.json()["id"]
    return merchant_id


def assign(client: TestClient, admin: dict[str, str], merchant: str, operator: str) -> Response:
    return client.post(
        f"/merchants/{merchant}/members", json={"operator_reference": operator}, headers=admin
    )


def test_operator_sees_only_the_merchant_it_belongs_to(
    client: TestClient, migrated_database_url: str
) -> None:
    admin = bearer(client, ADMIN)
    merchant_a = create_merchant(client, admin, "Tienda Demo A")
    create_merchant(client, admin, "Tienda Demo B")

    assigned = assign(client, admin, merchant_a, reference(migrated_database_url, OPERATOR_A))
    listing = client.get("/merchants", headers=bearer(client, OPERATOR_A))

    assert assigned.status_code == HTTPStatus.CREATED
    assert [merchant["name"] for merchant in listing.json()] == ["Tienda Demo A"]
    assert listing.json()[0]["members"] == [
        {"reference": reference(migrated_database_url, OPERATOR_A), "email": OPERATOR_A}
    ]


def test_operator_cannot_read_or_modify_a_foreign_merchant(
    client: TestClient, migrated_database_url: str
) -> None:
    admin = bearer(client, ADMIN)
    merchant_a = create_merchant(client, admin, "Tienda Demo A")
    merchant_b = create_merchant(client, admin, "Tienda Demo B")
    assign(client, admin, merchant_a, reference(migrated_database_url, OPERATOR_A))
    assign(client, admin, merchant_b, reference(migrated_database_url, OPERATOR_B))
    operator_a = bearer(client, OPERATOR_A)

    read_b = client.get(f"/merchants/{merchant_b}", headers=operator_a)
    join_b = assign(client, operator_a, merchant_b, reference(migrated_database_url, OPERATOR_A))
    smuggled = client.post(
        f"/merchants/{merchant_a}/members",
        json={
            "operator_reference": reference(migrated_database_url, OPERATOR_A),
            "merchant_id": merchant_b,
        },
        headers=bearer(client, ADMIN),
    )
    listing = client.get("/merchants", params={"merchant_id": merchant_b}, headers=operator_a)

    assert read_b.status_code == HTTPStatus.NOT_FOUND
    assert join_b.status_code == HTTPStatus.FORBIDDEN
    assert smuggled.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
    assert [merchant["id"] for merchant in listing.json()] == [merchant_a]
    assert (
        scalar(
            migrated_database_url, "SELECT name FROM merchants WHERE id = :id", {"id": merchant_b}
        )
        == "Tienda Demo B"
    )
    assert (
        scalar(
            migrated_database_url,
            "SELECT count(*) FROM memberships WHERE merchant_id = :id",
            {"id": merchant_b},
        )
        == 1
    )


def test_own_merchant_is_readable_and_anonymous_gets_nothing(
    client: TestClient, migrated_database_url: str
) -> None:
    admin = bearer(client, ADMIN)
    merchant_a = create_merchant(client, admin, "Tienda Demo A")
    assign(client, admin, merchant_a, reference(migrated_database_url, OPERATOR_A))

    own = client.get(f"/merchants/{merchant_a}", headers=bearer(client, OPERATOR_A))
    anonymous = client.get("/merchants")
    operator_create = client.post(
        "/merchants", json={"name": "Propia"}, headers=bearer(client, OPERATOR_A)
    )
    anonymous_create = client.post("/merchants", json={"name": "Anonima"})

    assert own.status_code == HTTPStatus.OK
    assert own.json()["name"] == "Tienda Demo A"
    assert anonymous.status_code == HTTPStatus.UNAUTHORIZED
    assert operator_create.status_code == HTTPStatus.FORBIDDEN
    assert anonymous_create.status_code == HTTPStatus.UNAUTHORIZED
    assert scalar(migrated_database_url, "SELECT count(*) FROM merchants") == 1


def test_repeated_assignment_keeps_one_original_membership(
    client: TestClient, migrated_database_url: str
) -> None:
    admin = bearer(client, ADMIN)
    merchant_a = create_merchant(client, admin, "Tienda Demo A")
    operator = reference(migrated_database_url, OPERATOR_A)
    first = assign(client, admin, merchant_a, operator)
    original = scalar(migrated_database_url, "SELECT created_at FROM memberships")

    repeated = assign(client, admin, merchant_a, operator)
    listing = client.get("/merchants", headers=admin)

    assert first.status_code == HTTPStatus.CREATED
    assert repeated.status_code == HTTPStatus.OK
    assert repeated.json()["members"] == first.json()["members"]
    assert scalar(migrated_database_url, "SELECT count(*) FROM memberships") == 1
    assert scalar(migrated_database_url, "SELECT created_at FROM memberships") == original
    assert [len(merchant["members"]) for merchant in listing.json()] == [1]


def test_only_active_operators_can_be_assigned(
    client: TestClient, migrated_database_url: str
) -> None:
    admin = bearer(client, ADMIN)
    merchant_a = create_merchant(client, admin, "Tienda Demo A")

    admin_member = assign(client, admin, merchant_a, reference(migrated_database_url, ADMIN))
    execute(
        migrated_database_url,
        "UPDATE identities SET status = 'inactive' WHERE email = :e",
        {"e": OPERATOR_B},
    )
    inactive_member = assign(
        client, admin, merchant_a, reference(migrated_database_url, OPERATOR_B)
    )

    assert admin_member.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
    assert inactive_member.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
    assert scalar(migrated_database_url, "SELECT count(*) FROM memberships") == 0


def test_concurrent_assignments_keep_a_single_membership(
    client: TestClient, migrated_database_url: str
) -> None:
    admin = bearer(client, ADMIN)
    merchant_a = create_merchant(client, admin, "Tienda Demo A")
    operator = reference(migrated_database_url, OPERATOR_A)

    with ThreadPoolExecutor(max_workers=4) as pool:
        statuses = list(
            pool.map(lambda _: assign(client, admin, merchant_a, operator).status_code, range(4))
        )

    assert statuses.count(HTTPStatus.CREATED) == 1
    assert statuses.count(HTTPStatus.OK) == len(statuses) - 1
    assert scalar(migrated_database_url, "SELECT count(*) FROM memberships") == 1


def test_assignment_racing_a_deactivation_never_links_an_inactive_operator(
    client: TestClient, migrated_database_url: str
) -> None:
    admin = bearer(client, ADMIN)
    merchant_a = create_merchant(client, admin, "Tienda Demo A")
    operator = reference(migrated_database_url, OPERATOR_A)
    database = Database.from_settings(build_settings(database_url=migrated_database_url))
    deactivation = database.session_factory()
    deactivation.begin()
    deactivate_operator(deactivation, uuid.UUID(operator), datetime.now(UTC))

    with ThreadPoolExecutor(max_workers=1) as pool:
        attempt = pool.submit(assign, client, admin, merchant_a, operator)
        time.sleep(0.5)
        deactivation.commit()
        status = attempt.result(timeout=10).status_code
    deactivation.close()
    database.dispose()

    assert status == HTTPStatus.UNPROCESSABLE_CONTENT
    assert scalar(migrated_database_url, "SELECT count(*) FROM memberships") == 0
