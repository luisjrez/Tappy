import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response

from tappy.identity.models import IdentityStatus, Role
from tappy.identity.provisioning import IdentitySummary
from tappy.platform.database import Database
from tappy.sales.service import SaleRequest, create_sale
from tests.sales.support import (
    ADMIN,
    AMOUNT,
    BLOCKED_MISSING,
    DEFAULT_MAXIMUM,
    IDEMPOTENCY_HEADER,
    OPERATOR_A,
    OPERATOR_B,
    bearer,
    configure,
    create_sale_with_key,
    merchant_of,
    ready_merchant,
    reference_of,
    sale_count,
)
from tests.support import build_settings, execute, scalar, wait_until_blocked_on_a_lock

KEY = "7f9c2a4e-5b1d-4c8e-9a3f-0d6b8e2c1a57"
OTHER_AMOUNT = 45000
CONFLICT = "Idempotency key already used with different content"
RACED_AT = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)


def key_count(database_url: str) -> object:
    return scalar(database_url, "SELECT count(*) FROM idempotency_requests")


def test_repeating_a_creation_returns_the_same_sale(
    client: TestClient, migrated_database_url: str
) -> None:
    merchant_a = ready_merchant(client, migrated_database_url, "Tienda Demo A", OPERATOR_A)
    operator_a = bearer(client, OPERATOR_A)

    first = create_sale_with_key(
        client, operator_a, merchant_a, KEY, amount_cents=AMOUNT, concept="Pan dulce"
    )
    repeated = create_sale_with_key(
        client, operator_a, merchant_a, KEY, amount_cents=AMOUNT, concept="Pan dulce"
    )

    assert first.status_code == HTTPStatus.CREATED
    assert repeated.status_code == HTTPStatus.OK
    assert repeated.json() == first.json()
    assert sale_count(migrated_database_url) == 1
    assert key_count(migrated_database_url) == 1


def test_repetition_returns_the_sale_even_after_the_receiver_is_disabled(
    client: TestClient, migrated_database_url: str
) -> None:
    merchant_a = ready_merchant(client, migrated_database_url, "Tienda Demo A", OPERATOR_A)
    operator_a = bearer(client, OPERATOR_A)
    first = create_sale_with_key(client, operator_a, merchant_a, KEY, amount_cents=AMOUNT)

    configure(client, merchant_a, enabled=False)
    repeated = create_sale_with_key(client, operator_a, merchant_a, KEY, amount_cents=AMOUNT)

    assert repeated.status_code == HTTPStatus.OK
    assert repeated.json() == first.json()
    assert sale_count(migrated_database_url) == 1


def test_keys_belong_to_the_identity_that_used_them(
    client: TestClient, migrated_database_url: str
) -> None:
    merchant_a = ready_merchant(client, migrated_database_url, "Tienda Demo A", OPERATOR_A)
    admin = bearer(client, ADMIN)
    client.post(
        f"/merchants/{merchant_a}/members",
        json={"operator_reference": reference_of(migrated_database_url, OPERATOR_B)},
        headers=admin,
    )

    first = create_sale_with_key(
        client, bearer(client, OPERATOR_A), merchant_a, KEY, amount_cents=AMOUNT
    )
    other = create_sale_with_key(
        client, bearer(client, OPERATOR_B), merchant_a, KEY, amount_cents=AMOUNT
    )

    assert first.status_code == HTTPStatus.CREATED
    assert other.status_code == HTTPStatus.CREATED
    assert other.json()["id"] != first.json()["id"]
    assert sale_count(migrated_database_url) == len([first, other])


@pytest.mark.parametrize(
    "changes",
    [
        {"amount_cents": OTHER_AMOUNT},
        {"amount_cents": AMOUNT, "concept": "Otro concepto"},
    ],
)
def test_reusing_a_key_with_other_content_conflicts_without_touching_the_sale(
    client: TestClient, migrated_database_url: str, changes: dict[str, object]
) -> None:
    merchant_a = ready_merchant(client, migrated_database_url, "Tienda Demo A", OPERATOR_A)
    operator_a = bearer(client, OPERATOR_A)
    original = create_sale_with_key(client, operator_a, merchant_a, KEY, amount_cents=AMOUNT)

    reused = create_sale_with_key(client, operator_a, merchant_a, KEY, **changes)

    assert reused.status_code == HTTPStatus.CONFLICT
    assert reused.json() == {"detail": CONFLICT}
    assert sale_count(migrated_database_url) == 1
    stored = client.get(f"/sales/{original.json()['id']}", headers=operator_a)
    assert stored.json() == original.json()
    assert stored.json()["amount_cents"] == AMOUNT


def test_reusing_a_key_for_another_merchant_conflicts(
    client: TestClient, migrated_database_url: str
) -> None:
    merchant_a = ready_merchant(client, migrated_database_url, "Tienda Demo A", OPERATOR_A)
    operator_a = bearer(client, OPERATOR_A)
    second = merchant_of(client, migrated_database_url, "Tienda Demo A2", OPERATOR_A)
    configure(client, second, provider_account_id="bank-account-demo-a2")
    create_sale_with_key(client, operator_a, merchant_a, KEY, amount_cents=AMOUNT)

    reused = create_sale_with_key(client, operator_a, second, KEY, amount_cents=AMOUNT)

    assert reused.status_code == HTTPStatus.CONFLICT
    assert sale_count(migrated_database_url) == 1


def test_failed_creation_does_not_consume_the_key(
    client: TestClient, migrated_database_url: str
) -> None:
    merchant_a = merchant_of(client, migrated_database_url, "Tienda Demo A", OPERATOR_A)
    operator_a = bearer(client, OPERATOR_A)

    blocked = create_sale_with_key(client, operator_a, merchant_a, KEY, amount_cents=AMOUNT)
    invalid = create_sale_with_key(
        client, operator_a, merchant_a, KEY, amount_cents=DEFAULT_MAXIMUM + 1
    )
    configure(client, merchant_a)
    created = create_sale_with_key(client, operator_a, merchant_a, KEY, amount_cents=AMOUNT)

    assert blocked.json() == {"detail": BLOCKED_MISSING}
    assert invalid.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
    assert created.status_code == HTTPStatus.CREATED
    assert sale_count(migrated_database_url) == 1


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {IDEMPOTENCY_HEADER: ""},
        {IDEMPOTENCY_HEADER: "short"},
        {IDEMPOTENCY_HEADER: "with spaces inside the key"},
        {IDEMPOTENCY_HEADER: "k" * 129},
    ],
)
def test_creation_requires_a_well_formed_key(
    client: TestClient, migrated_database_url: str, headers: dict[str, str]
) -> None:
    merchant_a = ready_merchant(client, migrated_database_url, "Tienda Demo A", OPERATOR_A)

    response = client.post(
        "/sales",
        json={"merchant_id": merchant_a, "amount_cents": AMOUNT},
        headers={**bearer(client, OPERATOR_A), **headers},
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
    assert response.json()["detail"][0]["loc"] == ["header", "idempotency-key"]
    assert sale_count(migrated_database_url) == 0
    assert key_count(migrated_database_url) == 0


def race(
    client: TestClient, database_url: str, merchant_a: str, **fields: object
) -> tuple[Response, uuid.UUID]:
    operator_a = bearer(client, OPERATOR_A)
    actor = client.get("/auth/me", headers=operator_a).json()
    summary = IdentitySummary(
        actor["reference"], actor["email"], Role(actor["role"]), IdentityStatus(actor["status"])
    )
    database = Database.from_settings(build_settings(database_url=database_url))
    try:
        with database.session_factory() as racing, racing.begin():
            request = SaleRequest(summary, uuid.UUID(merchant_a), AMOUNT, None, KEY)
            held = create_sale(racing, request, DEFAULT_MAXIMUM, RACED_AT)
            with ThreadPoolExecutor(max_workers=1) as pool:
                attempt = pool.submit(
                    create_sale_with_key, client, operator_a, merchant_a, KEY, **fields
                )
                wait_until_blocked_on_a_lock(database_url)
                racing.commit()
                return attempt.result(timeout=10), uuid.UUID(held.sale.id)
    finally:
        database.dispose()


def test_concurrent_repetition_waits_and_returns_the_single_sale(
    client: TestClient, migrated_database_url: str
) -> None:
    merchant_a = ready_merchant(client, migrated_database_url, "Tienda Demo A", OPERATOR_A)

    response, held_id = race(client, migrated_database_url, merchant_a, amount_cents=AMOUNT)

    assert response.status_code == HTTPStatus.OK
    assert response.json()["id"] == str(held_id)
    assert sale_count(migrated_database_url) == 1
    read = client.get(f"/sales/{held_id}", headers=bearer(client, OPERATOR_A))
    assert read.json()["amount_cents"] == AMOUNT


def test_concurrent_reuse_with_other_content_conflicts(
    client: TestClient, migrated_database_url: str
) -> None:
    merchant_a = ready_merchant(client, migrated_database_url, "Tienda Demo A", OPERATOR_A)

    response, _ = race(client, migrated_database_url, merchant_a, amount_cents=OTHER_AMOUNT)

    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json() == {"detail": CONFLICT}
    assert sale_count(migrated_database_url) == 1


def test_repetition_after_losing_the_membership_reveals_nothing(
    client: TestClient, migrated_database_url: str
) -> None:
    merchant_a = ready_merchant(client, migrated_database_url, "Tienda Demo A", OPERATOR_A)
    operator_a = bearer(client, OPERATOR_A)
    create_sale_with_key(client, operator_a, merchant_a, KEY, amount_cents=AMOUNT)
    execute(migrated_database_url, "DELETE FROM memberships")

    repeated = create_sale_with_key(client, operator_a, merchant_a, KEY, amount_cents=AMOUNT)

    assert repeated.status_code == HTTPStatus.NOT_FOUND
    assert repeated.json() == {"detail": "Merchant not found"}


def test_whitespace_only_differences_in_the_concept_are_the_same_request(
    client: TestClient, migrated_database_url: str
) -> None:
    merchant_a = ready_merchant(client, migrated_database_url, "Tienda Demo A", OPERATOR_A)
    operator_a = bearer(client, OPERATOR_A)

    first = create_sale_with_key(
        client, operator_a, merchant_a, KEY, amount_cents=AMOUNT, concept="Pan dulce"
    )
    repeated = create_sale_with_key(
        client, operator_a, merchant_a, KEY, amount_cents=AMOUNT, concept="  Pan   dulce "
    )

    assert repeated.status_code == HTTPStatus.OK
    assert repeated.json() == first.json()
