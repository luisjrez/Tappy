import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any

from fastapi.testclient import TestClient

from tappy.payments.events import ReceivedEvent, store_event
from tappy.payments.provider import IssuedQr, ProviderName, QrOrder
from tappy.platform.clock import SystemClock
from tappy.platform.database import Database
from tappy.sales.attempts import record_issued_qr
from tappy.sales.models import AttemptStatus
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


class EarlyPaymentProvider:
    name = ProviderName.PEY
    simulated = False

    def __init__(
        self, database_url: str, *, with_metadata: bool, short_by: int = 0, early: bool = True
    ) -> None:
        self.database_url = database_url
        self.with_metadata = with_metadata
        self.short_by = short_by
        self.early = early
        self.orders: list[QrOrder] = []

    def create_qr(self, order: QrOrder) -> IssuedQr:
        self.orders.append(order)
        if self.early:
            event = payment_event(order, with_metadata=self.with_metadata, short_by=self.short_by)
            receive(self.database_url, event)
        return IssuedQr(QR_ID, PAYLOAD)


def client_with(database_url: str, provider: EarlyPaymentProvider) -> TestClient:
    return start_client(settings_for(database_url), database_url, provider)


def create_qr(client: TestClient, database_url: str) -> tuple[dict[str, Any], dict[str, str]]:
    merchant_a = ready_merchant(client, database_url, "Tienda Demo A", OPERATOR_A)
    operator_a = bearer(client, OPERATOR_A)
    sale = create_sale(client, operator_a, merchant_a, amount_cents=AMOUNT).json()
    client.post(
        f"/sales/{sale['id']}/attempts",
        json={"method": "qr"},
        headers={**operator_a, IDEMPOTENCY_HEADER: str(uuid.uuid4())},
    )
    return client.get(f"/sales/{sale['id']}", headers=operator_a).json(), operator_a


def event_status(database_url: str) -> object:
    return scalar(database_url, "SELECT status FROM webhook_events")


def test_a_payment_event_before_the_creation_response_ends_confirmed(
    migrated_database_url: str,
) -> None:
    provider = EarlyPaymentProvider(migrated_database_url, with_metadata=True)
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
    provider = EarlyPaymentProvider(migrated_database_url, with_metadata=True)
    with client_with(migrated_database_url, provider) as client:
        sale, operator_a = create_qr(client, migrated_database_url)
        attempt_id = uuid.UUID(sale["attempts"][0]["id"])
        database = Database.from_settings(build_settings(database_url=migrated_database_url))
        try:
            with database.transaction() as session:
                late = record_issued_qr(
                    session, attempt_id, IssuedQr("OTHER-QR", "late"), datetime.now(UTC)
                )
        finally:
            database.dispose()
        read = client.get(f"/sales/{sale['id']}", headers=operator_a).json()

    assert late.status is AttemptStatus.PAID
    assert read["attempts"][0]["status"] == "paid"
    assert read["attempts"][0]["provider_request_id"] == QR_ID
    assert read["status"] == "paid"


def test_an_unassociable_early_event_is_applied_once_the_reference_exists(
    migrated_database_url: str,
) -> None:
    provider = EarlyPaymentProvider(migrated_database_url, with_metadata=False)
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
    provider = EarlyPaymentProvider(migrated_database_url, with_metadata=True, short_by=100)
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
    provider = EarlyPaymentProvider(migrated_database_url, with_metadata=True, early=False)
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
    provider = EarlyPaymentProvider(migrated_database_url, with_metadata=False, early=False)
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
