import json
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx2
import pytest
from fastapi.testclient import TestClient

from tappy.payments.events import ReceivedEvent, store_event
from tappy.payments.provider import ProviderName, QrProvider
from tappy.platform.database import Database
from tappy.sales.jobs import JobPolicy, claim_jobs, finish_job, run_jobs
from tappy.sales.reconciliation import reconcile_attempt
from tests.payments.pey_support import FakePey
from tests.payments.webhook_support import settings_for
from tests.sales.support import (
    AMOUNT,
    IDEMPOTENCY_HEADER,
    OPERATOR_A,
    RECEIVER_A,
    bearer,
    create_sale,
    ready_merchant,
    start_client,
)
from tests.support import MovableClock, build_settings, execute, run_sales, scalar

START = datetime(2026, 11, 25, 12, 0, tzinfo=UTC)
TRANSACTION = "01M3QR8H0RH0XBCKYYD242YXNV"
PAID_AT = 1795000000
POLICY = JobPolicy(
    lease=timedelta(minutes=10),
    batch_size=20,
    max_tries=3,
    backoff=timedelta(minutes=1),
    backoff_max=timedelta(hours=1),
    creation_timeout=timedelta(minutes=1),
)


def paid_page() -> tuple[int, object]:
    item = {
        "id": TRANSACTION,
        "status": "PAID",
        "amount": AMOUNT / 100,
        "currency": "MXN",
        "paymentMethod": "CODI",
        "dateCreated": PAID_AT,
        "datePaid": PAID_AT,
    }
    return 200, {"items": [item], "nextToken": None}


def empty_page() -> tuple[int, object]:
    return 200, {"items": [], "nextToken": None}


@pytest.fixture
def fake() -> FakePey:
    return FakePey()


@pytest.fixture
def client(migrated_database_url: str, fake: FakePey) -> Iterator[TestClient]:
    settings = settings_for(migrated_database_url)
    with start_client(settings, migrated_database_url, fake.provider()) as started:
        yield started


@pytest.fixture
def database(migrated_database_url: str) -> Iterator[Database]:
    opened = Database.from_settings(build_settings(database_url=migrated_database_url))
    yield opened
    opened.dispose()


def pending_qr(client: TestClient, database_url: str) -> tuple[dict[str, Any], dict[str, str]]:
    merchant_a = ready_merchant(client, database_url, "Tienda Demo A", OPERATOR_A)
    operator_a = bearer(client, OPERATOR_A)
    sale = create_sale(client, operator_a, merchant_a, amount_cents=AMOUNT).json()
    client.post(
        f"/sales/{sale['id']}/attempts",
        json={"method": "qr"},
        headers={**operator_a, IDEMPOTENCY_HEADER: str(uuid.uuid4())},
    )
    return client.get(f"/sales/{sale['id']}", headers=operator_a).json(), operator_a


def waiting_job(database_url: str, run_at: datetime = START) -> None:
    execute(database_url, "UPDATE payment_attempts SET status = 'reconciling'")
    execute(
        database_url,
        "INSERT INTO reconciliation_jobs (id, attempt_id, reason, status, run_at, created_at) "
        "SELECT gen_random_uuid(), id, 'timeout', 'pending', :run_at, :run_at "
        "FROM payment_attempts",
        {"run_at": run_at},
    )


def job(database_url: str) -> tuple[object, ...]:
    row = scalar(
        database_url,
        "SELECT ARRAY[status, tries::text, coalesce(last_problem, ''), "
        "to_char(run_at AT TIME ZONE 'UTC', 'HH24:MI')] FROM reconciliation_jobs",
    )
    assert isinstance(row, list)
    return tuple(row)


def detail(client: TestClient, headers: dict[str, str], sale: dict[str, Any]) -> dict[str, Any]:
    read: dict[str, Any] = client.get(f"/sales/{sale['id']}", headers=headers).json()
    return read


def run(database: Database, provider: QrProvider, clock: MovableClock) -> Any:
    return run_jobs(database, provider, "test", POLICY, clock)


def store_unprocessed_event(database: Database, sale: dict[str, Any]) -> None:
    attempt = sale["attempts"][0]
    event = {
        "type": "codi.qr.payment_received",
        "amount": AMOUNT / 100,
        "bankAccountId": RECEIVER_A["provider_account_id"],
        "codiQrId": attempt["provider_request_id"],
        "datePaid": PAID_AT,
        "transactionId": TRANSACTION,
        "metadata": {"tappy_attempt_id": attempt["id"]},
    }
    received = ReceivedEvent(
        ProviderName.PEY, "test", "msg_stored", event["type"], json.dumps(event).encode(), START
    )
    with database.transaction() as session:
        store_event(session, received, START)


def test_an_event_stored_before_a_crash_is_applied_by_the_next_batch(
    client: TestClient, migrated_database_url: str, database: Database
) -> None:
    sale, operator_a = pending_qr(client, migrated_database_url)
    store_unprocessed_event(database, sale)

    finished = run_sales(migrated_database_url, "run-jobs")
    read = detail(client, operator_a, sale)

    assert finished.returncode == 0
    assert "events: 1 event applied" in finished.stdout
    assert read["status"] == "paid"
    assert read["confirmed_amount_cents"] == AMOUNT
    assert scalar(migrated_database_url, "SELECT status FROM webhook_events") == "applied"


def test_a_due_job_is_reconciled_and_its_result_is_visible(
    client: TestClient, migrated_database_url: str, database: Database, fake: FakePey
) -> None:
    sale, operator_a = pending_qr(client, migrated_database_url)
    waiting_job(migrated_database_url)
    fake.pages = [paid_page()]

    summary = run(database, fake.provider(), MovableClock(START))
    listed = run_sales(migrated_database_url, "reconciliations")

    assert (summary.claimed, summary.confirmed) == (1, 1)
    assert detail(client, operator_a, sale)["status"] == "paid"
    assert job(migrated_database_url)[:2] == ("done", "1")
    assert listed.stdout.strip() == "No pending reconciliations"


def test_an_interrupted_creation_is_recovered_and_reconciled_in_the_same_batch(
    client: TestClient, migrated_database_url: str, database: Database, fake: FakePey
) -> None:
    sale, operator_a = pending_qr(client, migrated_database_url)
    execute(
        migrated_database_url,
        "UPDATE payment_attempts SET status = 'creating', updated_at = :old",
        {"old": START - timedelta(minutes=5)},
    )
    fake.pages = [paid_page()]

    summary = run(database, fake.provider(), MovableClock(START))

    assert (summary.recovered, summary.claimed, summary.confirmed) == (1, 1, 1)
    assert detail(client, operator_a, sale)["status"] == "paid"


def test_a_live_lease_has_a_single_claimant(
    client: TestClient, migrated_database_url: str, database: Database
) -> None:
    pending_qr(client, migrated_database_url)
    waiting_job(migrated_database_url)

    with database.transaction() as first:
        claimed = claim_jobs(first, POLICY, START)
        with database.transaction() as racing:
            raced = claim_jobs(racing, POLICY, START)
    with database.transaction() as later:
        within_lease = claim_jobs(later, POLICY, START + timedelta(minutes=9))

    assert len(claimed) == 1
    assert raced == []
    assert within_lease == []


def test_a_claimant_whose_lease_expired_cannot_finish_the_job(
    client: TestClient, migrated_database_url: str, database: Database, fake: FakePey
) -> None:
    sale, operator_a = pending_qr(client, migrated_database_url)
    waiting_job(migrated_database_url)
    with database.transaction() as first:
        (stale,) = claim_jobs(first, POLICY, START)
    with database.transaction() as second:
        (fresh,) = claim_jobs(second, POLICY, START + timedelta(minutes=11))
    with database.transaction() as late:
        stale_finished = finish_job(late, stale)
    fake.pages = [paid_page(), paid_page()]

    clock = MovableClock(START + timedelta(minutes=11))
    reconcile_attempt(database, fresh.attempt_id, fake.provider(), "test", clock)
    reconcile_attempt(database, stale.attempt_id, fake.provider(), "test", clock)

    assert stale.owner != fresh.owner
    assert stale_finished is False
    assert fresh.tries == len([stale, fresh])
    assert detail(client, operator_a, sale)["confirmed_amount_cents"] == AMOUNT
    assert scalar(migrated_database_url, "SELECT count(*) FROM transactions") == 1


def test_a_crash_and_a_rate_limit_are_retried_with_backoff_and_a_limit(
    client: TestClient, migrated_database_url: str, database: Database
) -> None:
    sale, operator_a = pending_qr(client, migrated_database_url)
    waiting_job(migrated_database_url)
    limited = FakePey(pages=[(429, {}), (429, {}), (429, {})])
    clock = MovableClock(START)
    with database.transaction() as crashed:
        claim_jobs(crashed, POLICY, clock.now())

    clock.advance(timedelta(minutes=5))
    during_lease = run(database, limited.provider(), clock)
    clock.advance(timedelta(minutes=6))
    after_lease = run(database, limited.provider(), clock)
    first_wait = job(migrated_database_url)
    clock.advance(timedelta(minutes=1))
    too_early = run(database, limited.provider(), clock)
    clock.advance(timedelta(minutes=1))
    third = run(database, limited.provider(), clock)
    clock.advance(timedelta(days=1))
    after_limit = run(database, limited.provider(), clock)

    assert during_lease.claimed == 0
    assert (after_lease.claimed, after_lease.rescheduled) == (1, 1)
    assert first_wait == ("pending", "2", "rate_limited", "12:13")
    assert too_early.claimed == 0
    assert (third.claimed, third.exhausted) == (1, 1)
    assert job(migrated_database_url)[:3] == ("exhausted", "3", "rate_limited")
    assert after_limit.claimed == 0
    assert len(limited.queries()) == len([after_lease, third])
    assert detail(client, operator_a, sale)["attempts"][0]["status"] == "reconciling"
    assert "status: exhausted" in run_sales(migrated_database_url, "reconciliations").stdout


def test_a_retry_after_longer_than_the_backoff_is_respected(
    client: TestClient, migrated_database_url: str, database: Database
) -> None:
    pending_qr(client, migrated_database_url)
    waiting_job(migrated_database_url)
    limited = FakePey(pages=[httpx2.Response(429, json={}, headers={"Retry-After": "900"})])
    provider = limited.provider()

    run(database, provider, MovableClock(START))

    assert job(migrated_database_url) == ("pending", "1", "rate_limited", "12:15")


def test_a_crash_after_every_claim_still_ends_exhausted(
    client: TestClient, migrated_database_url: str, database: Database, fake: FakePey
) -> None:
    pending_qr(client, migrated_database_url)
    waiting_job(migrated_database_url)
    clock = MovableClock(START)
    for _ in range(POLICY.max_tries):
        with database.transaction() as crashed:
            claim_jobs(crashed, POLICY, clock.now())
        clock.advance(timedelta(minutes=11))
    with database.transaction() as another:
        beyond_limit = claim_jobs(another, POLICY, clock.now())

    summary = run(database, fake.provider(), clock)

    assert beyond_limit == []
    assert (summary.claimed, summary.exhausted) == (0, 1)
    assert job(migrated_database_url)[:3] == ("exhausted", "3", "lease_expired")
    assert fake.queries() == []


def test_no_evidence_waits_with_growing_backoff(
    client: TestClient, migrated_database_url: str, database: Database, fake: FakePey
) -> None:
    pending_qr(client, migrated_database_url)
    waiting_job(migrated_database_url)
    fake.pages = [empty_page(), empty_page()]
    clock = MovableClock(START)

    run(database, fake.provider(), clock)
    first = job(migrated_database_url)
    clock.advance(timedelta(minutes=1))
    run(database, fake.provider(), clock)

    assert first == ("pending", "1", "no_evidence", "12:01")
    assert job(migrated_database_url) == ("pending", "2", "no_evidence", "12:03")
