import re
import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from tappy.platform.database import Database
from tappy.sales.backlog import Backlog, Lag, backlog
from tests.sales.support import (
    AMOUNT,
    IDEMPOTENCY_HEADER,
    OPERATOR_A,
    bearer,
    create_sale,
    ready_merchant,
)
from tests.support import build_settings, execute, run_sales

NOW = datetime(2026, 11, 25, 12, 0, tzinfo=UTC)
CREATION_CUTOFF = NOW - timedelta(minutes=1)
ATTEMPTS = 6


def issued_attempts(client: TestClient, database_url: str) -> list[str]:
    merchant_a = ready_merchant(client, database_url, "Tienda Demo A", OPERATOR_A)
    operator_a = bearer(client, OPERATOR_A)
    attempts = []
    for _ in range(ATTEMPTS):
        sale = create_sale(client, operator_a, merchant_a, amount_cents=AMOUNT).json()
        attempt = client.post(
            f"/sales/{sale['id']}/attempts",
            json={"method": "qr"},
            headers={**operator_a, IDEMPOTENCY_HEADER: str(uuid.uuid4())},
        ).json()
        attempts.append(attempt["id"])
    return attempts


def at(minutes: int, now: datetime = NOW) -> datetime:
    return now + timedelta(minutes=minutes)


def seed_every_indicator(database_url: str, attempts: list[str], now: datetime = NOW) -> None:
    stalled, creating, due, live, expired, exhausted = attempts
    for attempt, updated_at in ((stalled, at(-10, now)), (creating, at(0, now))):
        execute(
            database_url,
            "UPDATE payment_attempts SET status = 'creating', provider_request_id = NULL, "
            "qr_payload = NULL, updated_at = :updated WHERE id = :id",
            {"id": attempt, "updated": updated_at},
        )
    for attempt, reason, status, run_at, lease_until in (
        (due, "expired", "pending", at(-5, now), None),
        (due, "timeout", "pending", at(30, now), None),
        (live, "expired", "pending", at(-60, now), at(5, now)),
        (expired, "expired", "pending", at(-120, now), at(-1, now)),
        (exhausted, "expired", "exhausted", at(-240, now), None),
        (exhausted, "timeout", "done", at(-240, now), None),
        (exhausted, "connection", "done", at(-240, now), None),
    ):
        execute(
            database_url,
            "INSERT INTO reconciliation_jobs "
            "(id, attempt_id, reason, status, run_at, created_at, lease_owner, lease_until) "
            "VALUES (gen_random_uuid(), :attempt, :reason, :status, :run_at, :run_at, "
            "CASE WHEN CAST(:lease AS timestamptz) IS NULL THEN NULL ELSE gen_random_uuid() END, "
            ":lease)",
            {
                "attempt": attempt,
                "reason": reason,
                "status": status,
                "run_at": run_at,
                "lease": lease_until,
            },
        )
    for event_id, status, received_at in (
        ("msg_old", "received", at(-3, now)),
        ("msg_new", "received", at(-1, now)),
        ("msg_done", "applied", at(-30, now)),
    ):
        execute(
            database_url,
            "INSERT INTO webhook_events (id, provider, environment, provider_event_id, "
            "event_type, payload, payload_digest, signed_at, status, received_at) VALUES "
            "(gen_random_uuid(), 'pey', 'test', :event, 'codi.qr.payment_received', '\\x7b7d', "
            "'d', :received, :status, :received)",
            {"event": event_id, "status": status, "received": received_at},
        )
    for transaction, resolved_at in (("tx_open", None), ("tx_closed", at(-2, now))):
        execute(
            database_url,
            "INSERT INTO payment_exceptions "
            "(id, reason, provider_transaction_id, created_at, resolved_at) VALUES "
            "(gen_random_uuid(), 'unassociated', :request, :created, :resolved)",
            {"request": transaction, "created": at(-20, now), "resolved": resolved_at},
        )


def test_every_backlog_indicator_counts_only_what_is_waiting(
    client: TestClient, migrated_database_url: str
) -> None:
    seed_every_indicator(migrated_database_url, issued_attempts(client, migrated_database_url))
    database = Database.from_settings(build_settings(database_url=migrated_database_url))
    try:
        with database.transaction() as db:
            found = backlog(db, NOW, CREATION_CUTOFF)
    finally:
        database.dispose()

    assert found == Backlog(
        received_events=Lag(2, at(-3)),
        due_jobs=Lag(2, at(-120)),
        leased_jobs=2,
        expired_leases=1,
        exhausted_jobs=1,
        stalled_creations=Lag(1, at(-10)),
        open_exceptions=1,
    )


def test_the_backlog_command_prints_each_indicator_with_its_age(
    client: TestClient, migrated_database_url: str
) -> None:
    attempts = issued_attempts(client, migrated_database_url)
    seed_every_indicator(migrated_database_url, attempts, datetime.now(UTC))

    lines = run_sales(migrated_database_url, "backlog").stdout.splitlines()

    patterns = [
        r"received webhook events: 2 \(oldest received 18\d s ago\)",
        r"due reconciliation jobs: 2 \(oldest due 72\d\d s ago\)",
        r"leased reconciliation jobs: 2 \(1 with an expired lease\)",
        r"exhausted reconciliation jobs: 1",
        r"attempts creating longer than 60 s: 1 \(oldest updated 6\d\d s ago\)",
        r"open payment exceptions: 1",
    ]
    assert len(lines) == len(patterns)
    for line, pattern in zip(lines, patterns, strict=True):
        assert re.fullmatch(pattern, line), line
