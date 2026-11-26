import subprocess
import uuid
from datetime import UTC, datetime, timedelta
from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient

from tappy.main import create_app
from tappy.platform.database import Database
from tappy.platform.schema import upgrade_to_head
from tappy.sales.jobs import ClaimedJob, JobPolicy, claim_jobs, held_claim
from tests.compose_support import ComposeProject
from tests.sales.support import (
    AMOUNT,
    IDEMPOTENCY_HEADER,
    OPERATOR_A,
    bearer,
    create_sale,
    ready_merchant,
    start_client,
)
from tests.support import build_settings, execute, run_sales, scalar

RESTORED = "tappy_restored"
INTERRUPTED_LEASE = JobPolicy(
    lease=timedelta(minutes=1),
    batch_size=20,
    max_tries=8,
    backoff=timedelta(minutes=1),
    backoff_max=timedelta(hours=1),
    creation_timeout=timedelta(minutes=1),
)


def seed_sale_with_pending_job(database_url: str) -> str:
    upgrade_to_head(database_url)
    with start_client(build_settings(database_url=database_url), database_url) as client:
        merchant_a = ready_merchant(client, database_url, "Tienda Demo A", OPERATOR_A)
        operator_a = bearer(client, OPERATOR_A)
        sale = create_sale(client, operator_a, merchant_a, amount_cents=AMOUNT).json()
        client.post(
            f"/sales/{sale['id']}/attempts",
            json={"method": "qr"},
            headers={**operator_a, IDEMPOTENCY_HEADER: str(uuid.uuid4())},
        )
    execute(
        database_url,
        "UPDATE payment_attempts SET status = 'expired', expires_at = now() - interval '2 hours'",
    )
    execute(
        database_url,
        "INSERT INTO reconciliation_jobs (id, attempt_id, reason, status, run_at, created_at) "
        "SELECT gen_random_uuid(), id, 'expired', 'pending', now() - interval '1 hour', now() "
        "FROM payment_attempts",
    )
    reference: str = sale["reference"]
    return reference


def back_up(project: ComposeProject) -> bytes:
    return project.compose_bytes(
        "exec", "-T", "db", "pg_dump", "--format=custom", "--no-owner", "-U", "tappy", "-d", "tappy"
    )


def restore(project: ComposeProject, dump: bytes, name: str) -> str:
    project.compose("exec", "-T", "db", "createdb", "-U", "tappy", name)
    project.compose_bytes(
        "exec",
        "-T",
        "db",
        "pg_restore",
        "--no-owner",
        "--exit-on-error",
        "--single-transaction",
        "-U",
        "tappy",
        "-d",
        name,
        stdin=dump,
    )
    return project.database_url_for(name)


def readiness(database_url: str) -> int:
    with TestClient(create_app(build_settings(database_url=database_url))) as client:
        return client.get("/ready").status_code


def still_held(database_url: str, job: ClaimedJob) -> bool:
    database = Database.from_settings(build_settings(database_url=database_url))
    try:
        with database.transaction() as db:
            return held_claim(db, job) is not None
    finally:
        database.dispose()


def line_of(output: str, prefix: str) -> str:
    return next(line for line in output.splitlines() if line.startswith(prefix))


def test_a_backup_restores_into_a_new_database_with_the_sale_and_its_pending_job(
    local_compose: ComposeProject,
) -> None:
    source = local_compose.database_url
    reference = seed_sale_with_pending_job(source)

    restored = restore(local_compose, back_up(local_compose), RESTORED)
    listed = run_sales(restored, "reconciliations")
    backlog = run_sales(restored, "backlog")

    assert readiness(restored) == HTTPStatus.OK
    assert scalar(restored, "SELECT reference FROM sales") == reference
    assert scalar(restored, "SELECT status FROM reconciliation_jobs") == "pending"
    assert f"sale reference: {reference}" in listed.stdout
    assert line_of(backlog.stdout, "due reconciliation jobs:").startswith(
        "due reconciliation jobs: 1 (oldest due "
    )
    assert scalar(source, "SELECT count(*) FROM reconciliation_jobs WHERE status = 'pending'") == 1


def test_the_restore_refuses_to_overwrite_an_existing_database(
    local_compose: ComposeProject,
) -> None:
    source = local_compose.database_url
    reference = seed_sale_with_pending_job(source)
    dump = back_up(local_compose)

    with pytest.raises(subprocess.CalledProcessError):
        restore(local_compose, dump, "tappy")

    assert scalar(source, "SELECT reference FROM sales") == reference
    assert scalar(source, "SELECT count(*) FROM reconciliation_jobs") == 1


def test_a_runner_interrupted_after_the_restore_finishes_the_job_once_and_can_be_followed(
    local_compose: ComposeProject,
) -> None:
    reference = seed_sale_with_pending_job(local_compose.database_url)
    restored = restore(local_compose, back_up(local_compose), RESTORED)
    database = Database.from_settings(build_settings(database_url=restored))
    try:
        with database.transaction() as db:
            interrupted = claim_jobs(
                db, INTERRUPTED_LEASE, datetime.now(UTC) - timedelta(minutes=2)
            )
    finally:
        database.dispose()
    before = run_sales(restored, "backlog")

    resumed = run_sales(restored, "run-jobs")
    again = run_sales(restored, "run-jobs")
    after = run_sales(restored, "backlog")

    assert len(interrupted) == 1
    assert still_held(restored, interrupted[0]) is False
    assert line_of(before.stdout, "leased reconciliation jobs:") == (
        "leased reconciliation jobs: 1 (1 with an expired lease)"
    )
    assert resumed.returncode == 0
    assert "jobs claimed: 1" in resumed.stdout
    assert "verified unpaid: 1" in resumed.stdout
    assert f"for sale {reference}" in resumed.stderr
    assert ": verified" in resumed.stderr
    assert "jobs claimed: 0" in again.stdout
    assert f"for sale {reference}" not in again.stderr
    assert scalar(restored, "SELECT status || ' ' || tries FROM reconciliation_jobs") == "done 2"
    assert scalar(restored, "SELECT verified_at IS NOT NULL FROM payment_attempts") is True
    assert line_of(after.stdout, "due reconciliation jobs:") == "due reconciliation jobs: 0"
    assert line_of(after.stdout, "leased reconciliation jobs:") == (
        "leased reconciliation jobs: 0 (0 with an expired lease)"
    )
