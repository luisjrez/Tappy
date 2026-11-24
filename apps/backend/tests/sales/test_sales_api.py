import re
import uuid
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

from tappy.identity.models import Role
from tappy.main import create_app
from tappy.merchants.receivers import ReceiverSettings, configure_receiver
from tappy.platform.config import Settings
from tappy.platform.database import Database
from tests.support import build_settings, create_identity, scalar, wait_until_blocked_on_a_lock

ADMIN = "admin@tappy.example"
OPERATOR_A = "operadora.a@tappy.example"
OPERATOR_B = "operador.b@tappy.example"
PASSWORD = "credencial operativa 2026"
CLABE_A = "012180000123456782"
CLABE_B = "072180000999900017"
RECONFIGURED_AT = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
RECEIVER_A: dict[str, object] = {
    "provider_account_id": "bank-account-demo-a",
    "beneficiary_name": "Tienda Demo A SA de CV",
    "clabe": CLABE_A,
    "enabled": True,
}
BLOCKED_DISABLED = "The receiving account is disabled; new charges are blocked until it is enabled"
BLOCKED_MISSING = "No receiving account is configured; new charges are blocked"
REFERENCE = re.compile(r"[0-9A-HJKMNP-TV-Z]{10}")
DEFAULT_MAXIMUM = 100_000_000
AMOUNT = 30000
CONFIGURED_MAXIMUM = 50000


def start_client(settings: Settings, database_url: str) -> TestClient:
    create_identity(database_url, ADMIN, PASSWORD, role=Role.ADMIN)
    create_identity(database_url, OPERATOR_A, PASSWORD)
    create_identity(database_url, OPERATOR_B, PASSWORD)
    return TestClient(create_app(settings))


@pytest.fixture
def client(migrated_database_url: str) -> Iterator[TestClient]:
    settings = build_settings(database_url=migrated_database_url)
    with start_client(settings, migrated_database_url) as client:
        yield client


def bearer(client: TestClient, email: str) -> dict[str, str]:
    tokens = client.post("/auth/login", json={"email": email, "password": PASSWORD}).json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def reference_of(database_url: str, email: str) -> str:
    return str(scalar(database_url, "SELECT id FROM identities WHERE email = :e", {"e": email}))


def merchant_of(client: TestClient, database_url: str, name: str, operator: str) -> str:
    admin = bearer(client, ADMIN)
    merchant_id: str = client.post("/merchants", json={"name": name}, headers=admin).json()["id"]
    client.post(
        f"/merchants/{merchant_id}/members",
        json={"operator_reference": reference_of(database_url, operator)},
        headers=admin,
    )
    return merchant_id


def ready_merchant(client: TestClient, database_url: str, name: str, operator: str) -> str:
    merchant_id = merchant_of(client, database_url, name, operator)
    configure(client, merchant_id)
    return merchant_id


def configure(client: TestClient, merchant_id: str, **changes: object) -> Response:
    payload = {**RECEIVER_A, **changes}
    return client.put(
        f"/merchants/{merchant_id}/receiver", json=payload, headers=bearer(client, ADMIN)
    )


def create_sale(
    client: TestClient, headers: dict[str, str], merchant_id: str, **fields: object
) -> Response:
    return client.post("/sales", json={"merchant_id": merchant_id, **fields}, headers=headers)


def sale_count(database_url: str) -> object:
    return scalar(database_url, "SELECT count(*) FROM sales")


def test_operator_creates_and_reads_sale_with_exact_amount(
    client: TestClient, migrated_database_url: str
) -> None:
    merchant_a = ready_merchant(client, migrated_database_url, "Tienda Demo A", OPERATOR_A)
    operator_a = bearer(client, OPERATOR_A)

    created = create_sale(
        client, operator_a, merchant_a, amount_cents=30000, concept="Dos tacos al pastor"
    )
    read = client.get(f"/sales/{created.json()['id']}", headers=operator_a)

    assert created.status_code == HTTPStatus.CREATED
    body = created.json()
    assert body == {
        "id": body["id"],
        "merchant_id": merchant_a,
        "reference": body["reference"],
        "amount_cents": 30000,
        "currency": "MXN",
        "concept": "Dos tacos al pastor",
        "status": "open",
        "beneficiary_name": "Tienda Demo A SA de CV",
        "masked_account": "**************6782",
        "created_at": body["created_at"],
    }
    assert type(body["amount_cents"]) is int
    assert REFERENCE.fullmatch(body["reference"])
    assert read.status_code == HTTPStatus.OK
    assert read.json() == body
    assert scalar(migrated_database_url, "SELECT amount_cents FROM sales") == AMOUNT
    assert scalar(migrated_database_url, "SELECT created_by FROM sales") == uuid.UUID(
        reference_of(migrated_database_url, OPERATOR_A)
    )


@pytest.mark.parametrize(
    ("fields", "stored"),
    [
        ({}, None),
        ({"concept": None}, None),
        ({"concept": "   "}, None),
        ({"concept": "  Pan \t dulce  "}, "Pan dulce"),
        ({"concept": "C" * 40}, "C" * 40),
    ],
)
def test_concept_is_optional_and_normalized(
    client: TestClient, migrated_database_url: str, fields: dict[str, object], stored: str | None
) -> None:
    merchant_a = ready_merchant(client, migrated_database_url, "Tienda Demo A", OPERATOR_A)

    response = create_sale(
        client, bearer(client, OPERATOR_A), merchant_a, amount_cents=30000, **fields
    )

    assert response.status_code == HTTPStatus.CREATED
    assert response.json()["concept"] == stored


def test_each_sale_gets_its_own_reference(client: TestClient, migrated_database_url: str) -> None:
    merchant_a = ready_merchant(client, migrated_database_url, "Tienda Demo A", OPERATOR_A)
    operator_a = bearer(client, OPERATOR_A)

    first = create_sale(client, operator_a, merchant_a, amount_cents=30000).json()
    second = create_sale(client, operator_a, merchant_a, amount_cents=30000).json()

    assert first["id"] != second["id"]
    assert first["reference"] != second["reference"]


def test_sale_keeps_the_receiver_it_was_created_for(
    client: TestClient, migrated_database_url: str
) -> None:
    merchant_a = ready_merchant(client, migrated_database_url, "Tienda Demo A", OPERATOR_A)
    operator_a = bearer(client, OPERATOR_A)
    sale_id = create_sale(client, operator_a, merchant_a, amount_cents=30000).json()["id"]

    configure(
        client,
        merchant_a,
        provider_account_id="bank-account-demo-a2",
        beneficiary_name="Nueva Razon Social",
        clabe=CLABE_B,
    )
    read = client.get(f"/sales/{sale_id}", headers=operator_a).json()

    assert read["beneficiary_name"] == "Tienda Demo A SA de CV"
    assert read["masked_account"] == "**************6782"


def test_sale_is_blocked_without_an_enabled_receiver(
    client: TestClient, migrated_database_url: str
) -> None:
    merchant_a = merchant_of(client, migrated_database_url, "Tienda Demo A", OPERATOR_A)
    operator_a = bearer(client, OPERATOR_A)

    missing = create_sale(client, operator_a, merchant_a, amount_cents=30000)
    configure(client, merchant_a, enabled=False)
    disabled = create_sale(client, operator_a, merchant_a, amount_cents=30000)

    assert missing.status_code == HTTPStatus.CONFLICT
    assert missing.json() == {"detail": BLOCKED_MISSING}
    assert disabled.status_code == HTTPStatus.CONFLICT
    assert disabled.json() == {"detail": BLOCKED_DISABLED}
    assert sale_count(migrated_database_url) == 0


def test_sale_waits_for_a_concurrent_receiver_change_and_honours_it(
    client: TestClient, migrated_database_url: str
) -> None:
    merchant_a = ready_merchant(client, migrated_database_url, "Tienda Demo A", OPERATOR_A)
    operator_a = bearer(client, OPERATOR_A)
    disable = ReceiverSettings("bank-account-demo-a", "Tienda Demo A SA de CV", CLABE_A, False)
    database = Database.from_settings(build_settings(database_url=migrated_database_url))
    try:
        with database.session_factory() as racing, racing.begin():
            configure_receiver(racing, uuid.UUID(merchant_a), disable, RECONFIGURED_AT)
            racing.flush()
            with ThreadPoolExecutor(max_workers=1) as pool:
                attempt = pool.submit(
                    create_sale, client, operator_a, merchant_a, amount_cents=30000
                )
                wait_until_blocked_on_a_lock(migrated_database_url)
                racing.commit()
                response = attempt.result(timeout=10)
    finally:
        database.dispose()

    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json() == {"detail": BLOCKED_DISABLED}
    assert sale_count(migrated_database_url) == 0


@pytest.mark.parametrize(
    "extra",
    [
        {"provider_account_id": "bank-account-demo-b"},
        {"receiver_id": str(uuid.uuid4())},
        {"currency": "USD"},
        {"status": "PAID"},
        {"reference": "AAAAAAAAAA"},
    ],
)
def test_sale_body_accepts_no_receiver_currency_status_or_reference(
    client: TestClient, migrated_database_url: str, extra: dict[str, object]
) -> None:
    merchant_a = ready_merchant(client, migrated_database_url, "Tienda Demo A", OPERATOR_A)

    response = create_sale(
        client, bearer(client, OPERATOR_A), merchant_a, amount_cents=30000, **extra
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
    assert sale_count(migrated_database_url) == 0


def test_only_operators_create_sales(client: TestClient, migrated_database_url: str) -> None:
    merchant_a = ready_merchant(client, migrated_database_url, "Tienda Demo A", OPERATOR_A)

    as_admin = create_sale(client, bearer(client, ADMIN), merchant_a, amount_cents=30000)
    anonymous = create_sale(client, {}, merchant_a, amount_cents=30000)

    assert as_admin.status_code == HTTPStatus.FORBIDDEN
    assert as_admin.json() == {"detail": "Operator role required"}
    assert anonymous.status_code == HTTPStatus.UNAUTHORIZED
    assert sale_count(migrated_database_url) == 0


@pytest.mark.parametrize(
    "amount",
    [0, -1, 1.5, 30000.0, "30000", True, None, DEFAULT_MAXIMUM + 1, 2**63],
)
def test_invalid_amounts_are_rejected_without_rounding(
    client: TestClient, migrated_database_url: str, amount: object
) -> None:
    merchant_a = ready_merchant(client, migrated_database_url, "Tienda Demo A", OPERATOR_A)

    response = create_sale(client, bearer(client, OPERATOR_A), merchant_a, amount_cents=amount)

    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
    assert "input" not in response.text
    assert sale_count(migrated_database_url) == 0


def test_missing_amount_is_rejected(client: TestClient, migrated_database_url: str) -> None:
    merchant_a = ready_merchant(client, migrated_database_url, "Tienda Demo A", OPERATOR_A)

    response = create_sale(client, bearer(client, OPERATOR_A), merchant_a)

    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
    assert sale_count(migrated_database_url) == 0


def test_amount_range_messages_name_the_limits(
    client: TestClient, migrated_database_url: str
) -> None:
    merchant_a = ready_merchant(client, migrated_database_url, "Tienda Demo A", OPERATOR_A)

    response = create_sale(client, bearer(client, OPERATOR_A), merchant_a, amount_cents=0)

    assert response.json() == {
        "detail": f"Amount must be a whole number of centavos between 1 and {DEFAULT_MAXIMUM}"
    }


def test_bounds_of_the_configured_maximum(migrated_database_url: str) -> None:
    settings = build_settings(database_url=migrated_database_url).model_copy(
        update={"sale_max_amount_cents": 50000}
    )
    with start_client(settings, migrated_database_url) as client:
        merchant_a = ready_merchant(client, migrated_database_url, "Tienda Demo A", OPERATOR_A)
        operator_a = bearer(client, OPERATOR_A)

        smallest = create_sale(client, operator_a, merchant_a, amount_cents=1)
        largest = create_sale(client, operator_a, merchant_a, amount_cents=50000)
        above = create_sale(client, operator_a, merchant_a, amount_cents=50001)

    assert smallest.status_code == HTTPStatus.CREATED
    assert smallest.json()["amount_cents"] == 1
    assert largest.status_code == HTTPStatus.CREATED
    assert largest.json()["amount_cents"] == CONFIGURED_MAXIMUM
    assert above.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
    assert above.json() == {
        "detail": "Amount must be a whole number of centavos between 1 and 50000"
    }
    assert sale_count(migrated_database_url) == len([smallest, largest])


def test_maximum_cannot_exceed_the_provider_limit() -> None:
    with pytest.raises(ValueError, match="less than or equal to 100000000"):
        Settings.model_validate(
            {
                **build_settings().model_dump(),
                "sale_max_amount_cents": DEFAULT_MAXIMUM + 1,
            }
        )


def test_long_concept_is_rejected_without_truncation(
    client: TestClient, migrated_database_url: str
) -> None:
    merchant_a = ready_merchant(client, migrated_database_url, "Tienda Demo A", OPERATOR_A)

    response = create_sale(
        client, bearer(client, OPERATOR_A), merchant_a, amount_cents=30000, concept="C" * 41
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
    assert response.json() == {"detail": "Concept must have at most 40 characters"}
    assert sale_count(migrated_database_url) == 0


def test_other_operator_cannot_read_create_for_or_change_a_sale(
    client: TestClient, migrated_database_url: str
) -> None:
    merchant_a = ready_merchant(client, migrated_database_url, "Tienda Demo A", OPERATOR_A)
    ready_merchant(client, migrated_database_url, "Tienda Demo B", OPERATOR_B)
    sale = create_sale(client, bearer(client, OPERATOR_A), merchant_a, amount_cents=30000).json()
    operator_b = bearer(client, OPERATOR_B)

    read = client.get(f"/sales/{sale['id']}", headers=operator_b)
    patched = client.patch(f"/sales/{sale['id']}", json={"amount_cents": 1}, headers=operator_b)
    replaced = client.put(f"/sales/{sale['id']}", json={"amount_cents": 1}, headers=operator_b)
    foreign = create_sale(client, operator_b, merchant_a, amount_cents=1)

    assert read.status_code == HTTPStatus.NOT_FOUND
    assert read.json() == {"detail": "Sale not found"}
    assert patched.status_code == HTTPStatus.METHOD_NOT_ALLOWED
    assert replaced.status_code == HTTPStatus.METHOD_NOT_ALLOWED
    assert foreign.status_code == HTTPStatus.NOT_FOUND
    assert foreign.json() == {"detail": "Merchant not found"}
    assert sale_count(migrated_database_url) == 1
    assert scalar(migrated_database_url, "SELECT amount_cents FROM sales") == AMOUNT
    assert str(scalar(migrated_database_url, "SELECT merchant_id FROM sales")) == merchant_a
    assert client.get(f"/sales/{sale['id']}", headers=bearer(client, OPERATOR_A)).json() == sale


def test_administrators_can_review_any_sale(client: TestClient, migrated_database_url: str) -> None:
    merchant_a = ready_merchant(client, migrated_database_url, "Tienda Demo A", OPERATOR_A)
    sale = create_sale(client, bearer(client, OPERATOR_A), merchant_a, amount_cents=30000).json()

    read = client.get(f"/sales/{sale['id']}", headers=bearer(client, ADMIN))

    assert read.status_code == HTTPStatus.OK
    assert read.json() == sale


def test_unknown_or_malformed_sale_ids(client: TestClient) -> None:
    operator_a = bearer(client, OPERATOR_A)

    unknown = client.get(f"/sales/{uuid.uuid4()}", headers=operator_a)
    malformed = client.get("/sales/not-a-sale", headers=operator_a)
    anonymous = client.get(f"/sales/{uuid.uuid4()}")

    assert unknown.status_code == HTTPStatus.NOT_FOUND
    assert malformed.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
    assert anonymous.status_code == HTTPStatus.UNAUTHORIZED


@pytest.mark.parametrize(
    "assignment",
    [
        "amount_cents = 1",
        "currency = 'USD'",
        "merchant_id = gen_random_uuid()",
        "reference = 'AAAAAAAAAA'",
        "beneficiary_name = 'Otro'",
        "account_last4 = '0000'",
        "created_by = gen_random_uuid()",
    ],
)
def test_issued_terms_cannot_be_changed_in_the_database(
    client: TestClient, migrated_database_url: str, assignment: str
) -> None:
    merchant_a = ready_merchant(client, migrated_database_url, "Tienda Demo A", OPERATOR_A)
    create_sale(client, bearer(client, OPERATOR_A), merchant_a, amount_cents=30000)
    engine = create_engine(migrated_database_url)
    try:
        with (
            pytest.raises(DBAPIError, match="issued sale terms are immutable"),
            engine.begin() as connection,
        ):
            connection.execute(text(f"UPDATE sales SET {assignment}"))  # noqa: S608
    finally:
        engine.dispose()

    assert scalar(migrated_database_url, "SELECT amount_cents FROM sales") == AMOUNT


@pytest.mark.parametrize("amount", [0, -1])
def test_database_rejects_non_positive_amounts(
    client: TestClient, migrated_database_url: str, amount: int
) -> None:
    merchant_a = ready_merchant(client, migrated_database_url, "Tienda Demo A", OPERATOR_A)
    create_sale(client, bearer(client, OPERATOR_A), merchant_a, amount_cents=30000)
    engine = create_engine(migrated_database_url)
    try:
        with (
            pytest.raises(DBAPIError, match="ck_sales_amount_cents_positive"),
            engine.begin() as connection,
        ):
            connection.execute(
                text(
                    "INSERT INTO sales (id, merchant_id, created_by, amount_cents, currency, "
                    "reference, status, receiving_account_id, beneficiary_name, "
                    "account_last4, created_at) "
                    "SELECT gen_random_uuid(), merchant_id, created_by, :amount, currency, "
                    "'BBBBBBBBBB', status, receiving_account_id, beneficiary_name, "
                    "account_last4, created_at FROM sales"
                ),
                {"amount": amount},
            )
    finally:
        engine.dispose()
