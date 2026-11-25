import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response

from tappy.payments.provider import IssuedQr, ProviderUnavailableError, QrOrder, UncertainReason
from tappy.payments.simulator import SimulatedQrProvider
from tappy.platform.config import PROVIDER_TIMEOUT_PHASES, Settings
from tappy.platform.database import Database
from tappy.sales.attempts import AttemptRequest, recover_interrupted, reserve_attempt
from tappy.sales.models import AttemptMethod, JobReason
from tests.sales.support import (
    AMOUNT,
    AMPLE_QUOTA,
    IDEMPOTENCY_HEADER,
    OPERATOR_A,
    actor_of,
    app_client,
    bearer,
    create_sale,
    ready_merchant,
    start_client,
)
from tests.support import build_settings, execute, run_sales, scalar

RESERVED_AT = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)


class LostResponseProvider(SimulatedQrProvider):
    def __init__(self, reason: UncertainReason = UncertainReason.TIMEOUT) -> None:
        super().__init__()
        self.reason = reason
        self.orders: list[QrOrder] = []

    def create_qr(self, order: QrOrder) -> IssuedQr:
        self.orders.append(order)
        super().create_qr(order)
        raise ProviderUnavailableError(self.reason)


@pytest.fixture
def provider() -> LostResponseProvider:
    return LostResponseProvider()


@pytest.fixture
def client(migrated_database_url: str, provider: LostResponseProvider) -> Iterator[TestClient]:
    settings = build_settings(database_url=migrated_database_url)
    with start_client(settings, migrated_database_url, provider) as client:
        yield client


def open_sale(client: TestClient, database_url: str) -> tuple[str, dict[str, str]]:
    merchant_a = ready_merchant(client, database_url, "Tienda Demo A", OPERATOR_A)
    operator_a = bearer(client, OPERATOR_A)
    sale = create_sale(client, operator_a, merchant_a, amount_cents=AMOUNT).json()
    return sale["id"], operator_a


def create_qr(
    client: TestClient, headers: dict[str, str], sale_id: str, key: str | None = None
) -> Response:
    return client.post(
        f"/sales/{sale_id}/attempts",
        json={"method": "qr"},
        headers={**headers, IDEMPOTENCY_HEADER: key or str(uuid.uuid4())},
    )


def job_of(database_url: str) -> object:
    return scalar(
        database_url,
        "SELECT reason || ':' || status || ':' || attempt_id FROM reconciliation_jobs",
    )


def test_lost_response_leaves_the_attempt_reconciling_with_a_durable_job(
    client: TestClient, migrated_database_url: str, provider: LostResponseProvider
) -> None:
    sale_id, operator_a = open_sale(client, migrated_database_url)

    created = create_qr(client, operator_a, sale_id)
    sale = client.get(f"/sales/{sale_id}", headers=operator_a).json()

    assert created.status_code == HTTPStatus.ACCEPTED
    attempt = created.json()
    assert attempt["status"] == "reconciling"
    assert attempt["sale_reference"] == sale["reference"]
    assert attempt["provider_request_id"] is None
    assert attempt["failure_code"] is None
    assert sale["attempts"] == [attempt]
    assert sale["status"] == "open"
    assert len(provider.orders) == 1
    assert job_of(migrated_database_url) == f"timeout:pending:{attempt['id']}"


def test_retry_with_the_same_key_recovers_the_attempt_without_a_second_request(
    client: TestClient, migrated_database_url: str, provider: LostResponseProvider
) -> None:
    sale_id, operator_a = open_sale(client, migrated_database_url)
    key = str(uuid.uuid4())
    first = create_qr(client, operator_a, sale_id, key=key).json()

    retried = create_qr(client, operator_a, sale_id, key=key)
    other_key = create_qr(client, operator_a, sale_id)

    assert retried.status_code == HTTPStatus.OK
    assert retried.json() == first
    assert other_key.status_code == HTTPStatus.CONFLICT
    assert len(provider.orders) == 1
    assert scalar(migrated_database_url, "SELECT count(*) FROM payment_attempts") == 1
    assert scalar(migrated_database_url, "SELECT count(*) FROM reconciliation_jobs") == 1


def test_uncertainty_and_job_survive_a_restart_and_show_in_the_operations_command(
    client: TestClient, migrated_database_url: str
) -> None:
    sale_id, operator_a = open_sale(client, migrated_database_url)
    attempt = create_qr(client, operator_a, sale_id).json()

    with app_client(build_settings(database_url=migrated_database_url)) as restarted:
        sale = restarted.get(f"/sales/{sale_id}", headers=operator_a).json()
    listed = run_sales(migrated_database_url, "reconciliations")

    assert sale["attempts"][0]["status"] == "reconciling"
    assert listed.returncode == 0, listed.stderr
    assert attempt["id"] in listed.stdout
    assert attempt["sale_reference"] in listed.stdout
    assert "reason: timeout" in listed.stdout
    assert "status: pending" in listed.stdout
    assert "failed" not in listed.stdout


@pytest.mark.parametrize(
    "reason",
    [UncertainReason.SERVER_ERROR, UncertainReason.INVALID_RESPONSE, UncertainReason.CONNECTION],
)
def test_every_uncertain_outcome_is_kept_for_reconciliation(
    migrated_database_url: str, reason: UncertainReason
) -> None:
    settings = build_settings(database_url=migrated_database_url)
    with start_client(settings, migrated_database_url, LostResponseProvider(reason)) as client:
        sale_id, operator_a = open_sale(client, migrated_database_url)

        created = create_qr(client, operator_a, sale_id)

    assert created.status_code == HTTPStatus.ACCEPTED
    assert created.json()["status"] == "reconciling"
    assert job_of(migrated_database_url) == f"{reason}:pending:{created.json()['id']}"


def interrupted_attempt(client: TestClient, database_url: str) -> str:
    sale_id, operator_a = open_sale(client, database_url)
    database = Database.from_settings(build_settings(database_url=database_url))
    try:
        with database.transaction() as session:
            request = AttemptRequest(
                actor_of(client, operator_a),
                uuid.UUID(sale_id),
                AttemptMethod.QR,
                "k" * 16,
                AMPLE_QUOTA,
            )
            reserved = reserve_attempt(session, request, SimulatedQrProvider(), RESERVED_AT)
    finally:
        database.dispose()
    return reserved.attempt.id


def test_interrupted_creations_are_moved_to_reconciliation_by_the_operations_command(
    client: TestClient, migrated_database_url: str
) -> None:
    stale = interrupted_attempt(client, migrated_database_url)
    execute(
        migrated_database_url,
        "UPDATE payment_attempts SET updated_at = now() - interval '10 minutes'",
    )

    recovered = run_sales(migrated_database_url, "recover-interrupted")

    assert recovered.returncode == 0, recovered.stderr
    assert "1 interrupted attempt moved to reconciliation" in recovered.stdout
    assert scalar(migrated_database_url, "SELECT status FROM payment_attempts") == "reconciling"
    assert job_of(migrated_database_url) == f"interrupted_creation:pending:{stale}"


def test_recent_creations_are_left_alone(client: TestClient, migrated_database_url: str) -> None:
    interrupted_attempt(client, migrated_database_url)
    execute(migrated_database_url, "UPDATE payment_attempts SET updated_at = now()")

    recovered = run_sales(migrated_database_url, "recover-interrupted")

    assert recovered.returncode == 0, recovered.stderr
    assert "0 interrupted attempts moved to reconciliation" in recovered.stdout
    assert scalar(migrated_database_url, "SELECT status FROM payment_attempts") == "creating"
    assert scalar(migrated_database_url, "SELECT count(*) FROM reconciliation_jobs") == 0


def test_recovery_runs_are_idempotent(client: TestClient, migrated_database_url: str) -> None:
    interrupted_attempt(client, migrated_database_url)
    execute(
        migrated_database_url,
        "UPDATE payment_attempts SET updated_at = now() - interval '10 minutes'",
    )

    run_sales(migrated_database_url, "recover-interrupted")
    second = run_sales(migrated_database_url, "recover-interrupted")

    assert "0 interrupted attempts moved to reconciliation" in second.stdout
    assert scalar(migrated_database_url, "SELECT count(*) FROM reconciliation_jobs") == 1


class RecoveredDuringCallProvider(SimulatedQrProvider):
    def __init__(self, database_url: str) -> None:
        super().__init__(id_factory=lambda: "LATE-QR-1")
        self.database_url = database_url

    def create_qr(self, order: QrOrder) -> IssuedQr:
        database = Database.from_settings(build_settings(database_url=self.database_url))
        try:
            with database.transaction() as session:
                recover_interrupted(session, datetime.now(UTC) + timedelta(minutes=1), RESERVED_AT)
        finally:
            database.dispose()
        return super().create_qr(order)


def test_a_late_qr_for_a_recovered_attempt_is_kept_as_evidence(
    migrated_database_url: str,
) -> None:
    settings = build_settings(database_url=migrated_database_url)
    provider = RecoveredDuringCallProvider(migrated_database_url)
    with start_client(settings, migrated_database_url, provider) as client:
        sale_id, operator_a = open_sale(client, migrated_database_url)

        created = create_qr(client, operator_a, sale_id)

    assert created.status_code == HTTPStatus.ACCEPTED
    attempt = created.json()
    assert attempt["status"] == "reconciling"
    assert attempt["provider_request_id"] == "LATE-QR-1"
    assert attempt["qr_payload"].startswith("SIMULATED-CODI-QR|")
    assert job_of(migrated_database_url) == f"interrupted_creation:pending:{attempt['id']}"


def test_creation_timeout_must_outlast_every_provider_timeout_phase() -> None:
    base = build_settings().model_dump()

    with pytest.raises(ValueError, match="TAPPY_ATTEMPT_CREATION_TIMEOUT_SECONDS"):
        Settings.model_validate(
            {**base, "pey_timeout_seconds": 20, "attempt_creation_timeout_seconds": 60}
        )

    accepted = Settings.model_validate(
        {**base, "pey_timeout_seconds": 10, "attempt_creation_timeout_seconds": 41}
    )
    assert (
        accepted.attempt_creation_timeout_seconds
        > PROVIDER_TIMEOUT_PHASES * accepted.pey_timeout_seconds
    )


@pytest.mark.parametrize("reason", list(UncertainReason))
def test_every_uncertain_reason_has_a_job_reason(reason: UncertainReason) -> None:
    assert JobReason(reason.value).value == reason.value


def test_the_job_lease_must_outlast_a_bounded_query_only_with_pey() -> None:
    base = {**build_settings().model_dump(), "pey_api_key": "test-pey-secret-0123456789abcdef"}
    pey = {**base, "payment_provider": "pey", "pey_timeout_seconds": 10}
    longest_query = 400
    short_lease = 30

    with pytest.raises(ValueError, match="TAPPY_JOB_LEASE_SECONDS"):
        Settings.model_validate({**pey, "job_lease_seconds": longest_query})
    with pytest.raises(ValueError, match="TAPPY_JOB_BACKOFF_MAX_SECONDS"):
        Settings.model_validate({**base, "job_backoff_seconds": 120, "job_backoff_max_seconds": 60})

    accepted = Settings.model_validate({**pey, "job_lease_seconds": longest_query + 1})
    simulated = Settings.model_validate({**base, "job_lease_seconds": short_lease})
    assert accepted.job_lease_seconds > longest_query
    assert simulated.job_lease_seconds == short_lease
