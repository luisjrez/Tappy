import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Any

import pytest
from alembic import command
from fastapi.testclient import TestClient
from httpx2 import Response

from tappy.payments.events import ReceivedEvent, store_event
from tappy.payments.provider import (
    IssuedQr,
    ProviderName,
    ProviderUnavailableError,
    QrOrder,
    QrPayment,
    UncertainReason,
)
from tappy.platform.clock import SystemClock
from tappy.platform.database import Database
from tappy.platform.schema import alembic_config
from tappy.sales.attempts import record_issued_qr
from tappy.sales.receptions import process_stored
from tests.payments.webhook_support import settings_for
from tests.sales.support import (
    AMOUNT,
    IDEMPOTENCY_HEADER,
    OPERATOR_A,
    bearer,
    create_sale,
    ready_merchant,
    start_client,
)
from tests.support import build_settings, execute, scalar, wait_until_blocked_on_a_lock

QR_ID = "AB12CD34EF"
PAYLOAD = '{"TYP":1,"v":"01","ic":0,"IDC":"AB12CD34EF"}'
PAID_AT = 1795000000


def payment_event(
    order: QrOrder, *, with_metadata: bool, codi_qr_id: str = QR_ID, short_by: int = 0
) -> dict[str, object]:
    event: dict[str, object] = {
        "type": "codi.qr.payment_received",
        "amount": (order.amount_cents - short_by) / 100,
        "bankAccountId": order.receiver_account,
        "codiQrId": codi_qr_id,
        "datePaid": PAID_AT,
        "transactionId": "TX-EARLY",
    }
    if with_metadata:
        event["metadata"] = {"tappy_attempt_id": str(order.attempt_id)}
    return event


def receive(database_url: str, event: dict[str, object]) -> object:
    received = ReceivedEvent(
        provider=ProviderName.PEY,
        environment="test",
        message_id="msg_early",
        event_type="codi.qr.payment_received",
        body=json.dumps(event).encode(),
        signed_at=datetime.now(UTC),
    )
    database = Database.from_settings(build_settings(database_url=database_url))
    try:
        with database.transaction() as session:
            store_event(session, received, datetime.now(UTC))
        return process_stored(database, received, SystemClock())
    finally:
        database.dispose()


@dataclass(frozen=True)
class Scenario:
    with_metadata: bool
    early: bool = True
    short_by: int = 0
    then_times_out: bool = False
    issued_id: str = QR_ID


class EarlyPaymentProvider:
    name = ProviderName.PEY
    simulated = False

    def __init__(self, database_url: str, scenario: Scenario) -> None:
        self.database_url = database_url
        self.scenario = scenario
        self.orders: list[QrOrder] = []
        self.status_before_response: object = None

    def create_qr(self, order: QrOrder) -> IssuedQr:
        self.orders.append(order)
        if self.scenario.early:
            event = payment_event(
                order, with_metadata=self.scenario.with_metadata, short_by=self.scenario.short_by
            )
            receive(self.database_url, event)
        self.status_before_response = scalar(
            self.database_url, "SELECT status FROM payment_attempts"
        )
        if self.scenario.then_times_out:
            raise ProviderUnavailableError(UncertainReason.TIMEOUT)
        return IssuedQr(self.scenario.issued_id, PAYLOAD)

    def qr_payments(self, provider_request_id: str) -> list[QrPayment]:
        return []


def client_with(database_url: str, provider: EarlyPaymentProvider) -> TestClient:
    return start_client(settings_for(database_url), database_url, provider)


def request_qr(
    client: TestClient, database_url: str
) -> tuple[Response, dict[str, Any], dict[str, str]]:
    merchant_a = ready_merchant(client, database_url, "Tienda Demo A", OPERATOR_A)
    operator_a = bearer(client, OPERATOR_A)
    sale = create_sale(client, operator_a, merchant_a, amount_cents=AMOUNT).json()
    response = client.post(
        f"/sales/{sale['id']}/attempts",
        json={"method": "qr"},
        headers={**operator_a, IDEMPOTENCY_HEADER: str(uuid.uuid4())},
    )
    return response, client.get(f"/sales/{sale['id']}", headers=operator_a).json(), operator_a


def create_qr(client: TestClient, database_url: str) -> tuple[dict[str, Any], dict[str, str]]:
    _, sale, operator_a = request_qr(client, database_url)
    return sale, operator_a


def event_status(database_url: str) -> object:
    return scalar(database_url, "SELECT status FROM webhook_events")


def test_a_payment_event_before_the_creation_response_ends_confirmed(
    migrated_database_url: str,
) -> None:
    provider = EarlyPaymentProvider(migrated_database_url, Scenario(with_metadata=True))
    with client_with(migrated_database_url, provider) as client:
        sale, _ = create_qr(client, migrated_database_url)

    attempt = sale["attempts"][0]
    assert sale["status"] == "paid"
    assert sale["confirmed_amount_cents"] == AMOUNT
    assert attempt["status"] == "paid"
    assert attempt["provider_request_id"] == QR_ID
    assert attempt["qr_payload"] == PAYLOAD
    assert sale["exceptions"] == []
    assert event_status(migrated_database_url) == "applied"
    assert scalar(migrated_database_url, "SELECT count(*) FROM transactions") == 1


def test_a_late_pending_response_never_degrades_a_paid_attempt(
    migrated_database_url: str,
) -> None:
    provider = EarlyPaymentProvider(migrated_database_url, Scenario(with_metadata=True))
    with client_with(migrated_database_url, provider) as client:
        response, sale, _ = request_qr(client, migrated_database_url)

    assert provider.status_before_response == "paid"
    assert response.status_code == HTTPStatus.CREATED
    assert response.json()["status"] == "paid"
    assert response.json()["qr_payload"] == PAYLOAD
    assert sale["attempts"][0]["status"] == "paid"
    assert sale["status"] == "paid"


def test_a_late_response_with_another_qr_never_re_associates_a_paid_attempt(
    migrated_database_url: str,
) -> None:
    provider = EarlyPaymentProvider(migrated_database_url, Scenario(with_metadata=True))
    with client_with(migrated_database_url, provider) as client:
        sale, operator_a = create_qr(client, migrated_database_url)
        attempt_id = uuid.UUID(sale["attempts"][0]["id"])
        database = Database.from_settings(build_settings(database_url=migrated_database_url))
        try:
            with (
                pytest.raises(ProviderUnavailableError) as raised,
                database.transaction() as session,
            ):
                record_issued_qr(
                    session, attempt_id, IssuedQr("OTHER-QR", "late"), datetime.now(UTC)
                )
        finally:
            database.dispose()
        read = client.get(f"/sales/{sale['id']}", headers=operator_a).json()

    assert raised.value.reason is UncertainReason.DUPLICATE_PROVIDER_ID
    assert read["attempts"][0]["status"] == "paid"
    assert read["attempts"][0]["provider_request_id"] == QR_ID
    assert read["attempts"][0]["qr_payload"] == PAYLOAD
    assert read["status"] == "paid"


def test_a_response_with_another_qr_than_the_adopted_one_goes_to_reconciliation(
    migrated_database_url: str,
) -> None:
    provider = EarlyPaymentProvider(
        migrated_database_url, Scenario(with_metadata=True, short_by=100, issued_id="ZZ99YY88XX")
    )
    with client_with(migrated_database_url, provider) as client:
        response, sale, _ = request_qr(client, migrated_database_url)

    attempt = sale["attempts"][0]
    assert response.status_code == HTTPStatus.ACCEPTED
    assert attempt["status"] == "reconciling"
    assert attempt["provider_request_id"] == QR_ID
    assert attempt["qr_payload"] is None
    assert scalar(migrated_database_url, "SELECT reason FROM reconciliation_jobs") == (
        "duplicate_provider_id"
    )


def test_a_failed_attempt_never_adopts_an_event(migrated_database_url: str) -> None:
    provider = EarlyPaymentProvider(
        migrated_database_url, Scenario(with_metadata=True, early=False)
    )
    with client_with(migrated_database_url, provider) as client:
        sale, operator_a = create_qr(client, migrated_database_url)
        execute(
            migrated_database_url,
            "UPDATE payment_attempts SET status = 'failed', provider_request_id = NULL, "
            "qr_payload = NULL",
        )
        status = receive(
            migrated_database_url, payment_event(provider.orders[0], with_metadata=True)
        )
        read = client.get(f"/sales/{sale['id']}", headers=operator_a).json()

    assert status == "review"
    assert read["status"] == "open"
    assert read["attempts"][0]["status"] == "failed"
    assert read["attempts"][0]["provider_request_id"] is None
    assert scalar(migrated_database_url, "SELECT count(*) FROM transactions") == 0


def test_waiting_references_are_backfilled_for_existing_exceptions(
    empty_database_url: str,
) -> None:
    command.upgrade(alembic_config(empty_database_url), "0016_payment_exceptions")
    for message_id, body in (
        ("msg_waiting", {"type": "codi.qr.payment_received", "codiQrId": QR_ID}),
        ("msg_numeric", {"type": "codi.qr.payment_received", "codiQrId": 7}),
    ):
        execute(
            empty_database_url,
            "INSERT INTO webhook_events (id, provider, environment, provider_event_id, "
            "event_type, payload, payload_digest, signed_at, status, received_at) VALUES "
            "(gen_random_uuid(), 'pey', 'test', :m, 'codi.qr.payment_received', :p, 'd', "
            "now(), 'review', now())",
            {"m": message_id, "p": json.dumps(body).encode()},
        )
    execute(
        empty_database_url,
        "INSERT INTO payment_exceptions (id, webhook_event_id, reason, created_at) "
        "SELECT gen_random_uuid(), id, 'unassociated', now() FROM webhook_events",
    )

    command.upgrade(alembic_config(empty_database_url), "head")

    assert scalar(
        empty_database_url,
        "SELECT array_agg(e.provider_request_id ORDER BY w.provider_event_id) "
        "FROM payment_exceptions e JOIN webhook_events w ON w.id = e.webhook_event_id",
    ) == [None, QR_ID]


def test_an_unassociable_early_event_is_applied_once_the_reference_exists(
    migrated_database_url: str,
) -> None:
    provider = EarlyPaymentProvider(migrated_database_url, Scenario(with_metadata=False))
    with client_with(migrated_database_url, provider) as client:
        sale, _ = create_qr(client, migrated_database_url)

    assert sale["status"] == "paid"
    assert sale["attempts"][0]["status"] == "paid"
    assert sale["confirmed_amount_cents"] == AMOUNT
    assert event_status(migrated_database_url) == "applied"
    assert scalar(migrated_database_url, "SELECT count(*) FROM transactions") == 1
    assert (
        scalar(
            migrated_database_url,
            "SELECT count(*) FROM payment_exceptions WHERE resolved_at IS NULL",
        )
        == 0
    )
    assert (
        scalar(
            migrated_database_url,
            "SELECT reason FROM payment_exceptions WHERE resolved_at IS NOT NULL",
        )
        == "unassociated"
    )


def test_an_early_short_payment_keeps_the_sale_in_review_and_the_qr_is_still_recorded(
    migrated_database_url: str,
) -> None:
    provider = EarlyPaymentProvider(
        migrated_database_url, Scenario(with_metadata=True, short_by=100)
    )
    with client_with(migrated_database_url, provider) as client:
        sale, _ = create_qr(client, migrated_database_url)

    attempt = sale["attempts"][0]
    assert sale["status"] == "review"
    assert sale["confirmed_amount_cents"] == AMOUNT - 100
    assert attempt["status"] == "pending"
    assert attempt["provider_request_id"] == QR_ID
    assert attempt["qr_payload"] == PAYLOAD
    assert [item["reason"] for item in sale["exceptions"]] == ["amount_mismatch"]


def test_an_event_naming_an_attempt_that_has_another_qr_is_never_adopted(
    migrated_database_url: str,
) -> None:
    provider = EarlyPaymentProvider(
        migrated_database_url, Scenario(with_metadata=True, early=False)
    )
    with client_with(migrated_database_url, provider) as client:
        sale, operator_a = create_qr(client, migrated_database_url)
        event = payment_event(provider.orders[0], with_metadata=True, codi_qr_id="ZZ99YY88XX")
        status = receive(migrated_database_url, event)
        read = client.get(f"/sales/{sale['id']}", headers=operator_a).json()

    assert status == "review"
    assert read["status"] == "open"
    assert read["attempts"][0]["provider_request_id"] == QR_ID
    assert read["confirmed_amount_cents"] == 0
    assert (
        scalar(
            migrated_database_url,
            "SELECT reason FROM payment_exceptions WHERE resolved_at IS NULL",
        )
        == "unassociated"
    )


def test_an_event_without_metadata_racing_the_creation_response_is_applied(
    migrated_database_url: str,
) -> None:
    provider = EarlyPaymentProvider(
        migrated_database_url, Scenario(with_metadata=False, early=False)
    )
    with client_with(migrated_database_url, provider) as client:
        sale, operator_a = create_qr(client, migrated_database_url)
        attempt_id = uuid.UUID(sale["attempts"][0]["id"])
        execute(
            migrated_database_url,
            "UPDATE payment_attempts SET status = 'creating', provider_request_id = NULL, "
            "qr_payload = NULL",
        )
        event = payment_event(provider.orders[0], with_metadata=False)
        database = Database.from_settings(build_settings(database_url=migrated_database_url))
        try:
            with database.session_factory() as racing, racing.begin():
                record_issued_qr(racing, attempt_id, IssuedQr(QR_ID, PAYLOAD), datetime.now(UTC))
                with ThreadPoolExecutor(max_workers=1) as pool:
                    processing = pool.submit(receive, migrated_database_url, event)
                    wait_until_blocked_on_a_lock(migrated_database_url)
                    racing.commit()
                    status = processing.result(timeout=10)
        finally:
            database.dispose()
        read = client.get(f"/sales/{sale['id']}", headers=operator_a).json()

    assert status == "applied"
    assert read["status"] == "paid"
    assert read["attempts"][0]["status"] == "paid"
    assert scalar(migrated_database_url, "SELECT count(*) FROM payment_exceptions") == 0


def test_an_attempt_in_reconciliation_without_a_qr_id_adopts_a_later_event(
    migrated_database_url: str,
) -> None:
    provider = EarlyPaymentProvider(
        migrated_database_url, Scenario(with_metadata=True, early=False, then_times_out=True)
    )
    with client_with(migrated_database_url, provider) as client:
        response, sale, operator_a = request_qr(client, migrated_database_url)
        status = receive(
            migrated_database_url, payment_event(provider.orders[0], with_metadata=True)
        )
        read = client.get(f"/sales/{sale['id']}", headers=operator_a).json()

    assert response.status_code == HTTPStatus.ACCEPTED
    assert sale["attempts"][0]["status"] == "reconciling"
    assert status == "applied"
    assert read["status"] == "paid"
    assert read["attempts"][0]["status"] == "paid"
    assert read["attempts"][0]["provider_request_id"] == QR_ID


def test_a_payment_before_a_creation_timeout_is_reported_as_created_and_paid(
    migrated_database_url: str,
) -> None:
    provider = EarlyPaymentProvider(
        migrated_database_url, Scenario(with_metadata=True, then_times_out=True)
    )
    with client_with(migrated_database_url, provider) as client:
        response, sale, _ = request_qr(client, migrated_database_url)

    assert response.status_code == HTTPStatus.CREATED
    assert response.json()["status"] == "paid"
    assert sale["status"] == "paid"
    assert scalar(migrated_database_url, "SELECT count(*) FROM reconciliation_jobs") == 0
