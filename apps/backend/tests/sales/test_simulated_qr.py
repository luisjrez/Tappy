import uuid
from collections.abc import Iterator
from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response

from tappy.payments.provider import IssuedQr, QrOrder
from tappy.payments.simulator import SimulatedQrProvider, provider_from
from tappy.platform.config import Settings
from tests.sales.support import (
    AMOUNT,
    CLABE_B,
    IDEMPOTENCY_HEADER,
    OPERATOR_A,
    PASSWORD,
    bearer,
    configure,
    create_sale,
    ready_merchant,
    start_client,
)
from tests.support import build_settings, scalar

Q1 = "Q1"


@pytest.fixture
def simulator() -> SimulatedQrProvider:
    return SimulatedQrProvider(id_factory=lambda: Q1)


@pytest.fixture
def client(migrated_database_url: str, simulator: SimulatedQrProvider) -> Iterator[TestClient]:
    settings = build_settings(database_url=migrated_database_url)
    with start_client(settings, migrated_database_url, simulator) as client:
        yield client


def create_qr(
    client: TestClient, headers: dict[str, str], sale_id: str, key: str | None = None
) -> Response:
    return client.post(
        f"/sales/{sale_id}/attempts",
        json={"method": "qr"},
        headers={**headers, IDEMPOTENCY_HEADER: key or str(uuid.uuid4())},
    )


def open_sale(client: TestClient, database_url: str) -> tuple[str, dict[str, str]]:
    merchant_a = ready_merchant(client, database_url, "Tienda Demo A", OPERATOR_A)
    operator_a = bearer(client, OPERATOR_A)
    sale = create_sale(
        client, operator_a, merchant_a, amount_cents=AMOUNT, concept="Dos tacos"
    ).json()
    return sale["id"], operator_a


def expected_payload(attempt_id: str) -> str:
    return f"SIMULATED-CODI-QR|attempt={attempt_id}|amount_cents={AMOUNT}|concept=Dos tacos"


def test_creating_a_qr_returns_the_simulated_payload_pending(
    client: TestClient, migrated_database_url: str, simulator: SimulatedQrProvider
) -> None:
    sale_id, operator_a = open_sale(client, migrated_database_url)

    created = create_qr(client, operator_a, sale_id)
    sale = client.get(f"/sales/{sale_id}", headers=operator_a).json()

    assert created.status_code == HTTPStatus.CREATED
    attempt = created.json()
    assert attempt == {
        "id": attempt["id"],
        "sale_id": sale_id,
        "method": "qr",
        "status": "pending",
        "simulated": True,
        "provider_request_id": Q1,
        "qr_payload": expected_payload(attempt["id"]),
        "created_at": attempt["created_at"],
    }
    assert sale["attempts"] == [attempt]
    assert len(simulator.orders) == 1
    order = simulator.orders[0]
    assert order.amount_cents == AMOUNT
    assert order.concept == "Dos tacos"
    assert order.receiver_account == "bank-account-demo-a"
    assert str(order.attempt_id) == attempt["id"]


def test_stored_qr_keeps_the_exact_payload_and_identifier(
    client: TestClient, migrated_database_url: str
) -> None:
    sale_id, operator_a = open_sale(client, migrated_database_url)
    attempt = create_qr(client, operator_a, sale_id).json()

    stored = scalar(
        migrated_database_url,
        "SELECT provider || ':' || provider_request_id || ':' || qr_payload FROM payment_attempts",
    )

    assert stored == f"simulated:{Q1}:{expected_payload(attempt['id'])}"


def test_simulated_acceptance_never_shows_a_payment(
    client: TestClient, migrated_database_url: str
) -> None:
    sale_id, operator_a = open_sale(client, migrated_database_url)
    create_qr(client, operator_a, sale_id)

    detail = client.get(f"/sales/{sale_id}", headers=operator_a)

    body = detail.json()
    assert body["status"] == "open"
    assert [attempt["status"] for attempt in body["attempts"]] == ["pending"]
    assert "paid" not in detail.text
    assert "received" not in detail.text.lower()
    assert "transaction" not in detail.text.lower()


def test_repeating_or_reopening_the_session_reuses_the_same_qr(
    client: TestClient, migrated_database_url: str, simulator: SimulatedQrProvider
) -> None:
    sale_id, operator_a = open_sale(client, migrated_database_url)
    key = str(uuid.uuid4())
    first = create_qr(client, operator_a, sale_id, key=key).json()

    repeated = create_qr(client, operator_a, sale_id, key=key)
    client.post("/auth/logout", headers=operator_a)
    reopened = client.post("/auth/login", json={"email": OPERATOR_A, "password": PASSWORD})
    fresh = {"Authorization": f"Bearer {reopened.json()['access_token']}"}
    read_again = client.get(f"/sales/{sale_id}", headers=fresh).json()
    second_key = create_qr(client, fresh, sale_id)

    assert repeated.status_code == HTTPStatus.OK
    assert repeated.json() == first
    assert read_again["attempts"] == [first]
    assert second_key.status_code == HTTPStatus.CONFLICT
    assert len(simulator.orders) == 1
    assert scalar(migrated_database_url, "SELECT count(*) FROM payment_attempts") == 1


def test_default_simulator_issues_distinct_labelled_identifiers(
    migrated_database_url: str,
) -> None:
    settings = build_settings(database_url=migrated_database_url)
    with start_client(settings, migrated_database_url) as client:
        merchant_a = ready_merchant(client, migrated_database_url, "Tienda Demo A", OPERATOR_A)
        operator_a = bearer(client, OPERATOR_A)
        first_sale = create_sale(client, operator_a, merchant_a, amount_cents=AMOUNT).json()
        second_sale = create_sale(client, operator_a, merchant_a, amount_cents=AMOUNT).json()

        first = create_qr(client, operator_a, first_sale["id"]).json()
        second = create_qr(client, operator_a, second_sale["id"]).json()

    assert first["simulated"] is True
    assert first["provider_request_id"].startswith("SIM-")
    assert first["provider_request_id"] != second["provider_request_id"]


@pytest.mark.parametrize("method", ["phone", "link"])
def test_other_channels_stay_reserved_without_calling_the_qr_provider(
    client: TestClient, migrated_database_url: str, simulator: SimulatedQrProvider, method: str
) -> None:
    sale_id, operator_a = open_sale(client, migrated_database_url)

    reserved = client.post(
        f"/sales/{sale_id}/attempts",
        json={"method": method},
        headers={**operator_a, IDEMPOTENCY_HEADER: str(uuid.uuid4())},
    )

    assert reserved.status_code == HTTPStatus.CREATED
    assert reserved.json()["status"] == "creating"
    assert reserved.json()["qr_payload"] is None
    assert simulator.orders == []


class DatabaseObservingSimulator(SimulatedQrProvider):
    def __init__(self, database_url: str) -> None:
        super().__init__(id_factory=lambda: Q1)
        self.database_url = database_url
        self.seen: list[object] = []

    def create_qr(self, order: QrOrder) -> IssuedQr:
        self.seen.append(
            scalar(
                self.database_url,
                "SELECT status FROM payment_attempts WHERE id = :id",
                {"id": order.attempt_id},
            )
        )
        return super().create_qr(order)


def test_reservation_is_committed_before_the_provider_is_called(
    migrated_database_url: str,
) -> None:
    observing = DatabaseObservingSimulator(migrated_database_url)
    settings = build_settings(database_url=migrated_database_url)
    with start_client(settings, migrated_database_url, observing) as client:
        sale_id, operator_a = open_sale(client, migrated_database_url)

        created = create_qr(client, operator_a, sale_id)

    assert observing.seen == ["creating"]
    assert created.json()["status"] == "pending"


def test_qr_is_refused_when_the_receiver_changed_after_the_sale(
    client: TestClient, migrated_database_url: str, simulator: SimulatedQrProvider
) -> None:
    sale_id, operator_a = open_sale(client, migrated_database_url)
    merchant_id = client.get(f"/sales/{sale_id}", headers=operator_a).json()["merchant_id"]
    configure(client, merchant_id, beneficiary_name="Otra Razon Social", clabe=CLABE_B)

    refused = create_qr(client, operator_a, sale_id)

    assert refused.status_code == HTTPStatus.CONFLICT
    assert refused.json() == {
        "detail": "The receiving account changed after the sale was created; create a new sale"
    }
    assert simulator.orders == []
    assert scalar(migrated_database_url, "SELECT count(*) FROM payment_attempts") == 0


def test_provider_setting_selects_the_simulator_and_rejects_unknown_values() -> None:
    assert build_settings().payment_provider == "simulated"
    assert isinstance(provider_from(build_settings()), SimulatedQrProvider)
    with pytest.raises(ValueError, match="payment_provider"):
        Settings.model_validate({**build_settings().model_dump(), "payment_provider": "other"})
