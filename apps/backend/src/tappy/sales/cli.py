import argparse
import sys
import uuid
from collections.abc import Callable, Sequence
from datetime import timedelta

from tappy.payments.events import WebhookEvent, WebhookEventConflict, event_conflicts
from tappy.payments.factory import provider_from
from tappy.platform.clock import SystemClock
from tappy.platform.config import ConfigurationError, Settings, load_settings
from tappy.platform.database import Database
from tappy.sales.attempts import OpenReconciliation, open_reconciliations, recover_interrupted
from tappy.sales.errors import AttemptNotFoundError
from tappy.sales.jobs import JobPolicy, JobRunner
from tappy.sales.payment_exceptions import OpenException, open_exceptions
from tappy.sales.receptions import ProcessingSummary, process_received_events
from tappy.sales.reconciliation import (
    ReconciliationReport,
    ReconciliationResult,
    reconcile_attempt,
)

Handler = Callable[[Database, Settings, argparse.Namespace], str]


def describe(job: OpenReconciliation) -> str:
    return "\n".join(
        [
            f"attempt: {job.attempt.id}",
            f"sale reference: {job.attempt.sale_reference}",
            f"attempt status: {job.attempt.status}",
            f"reason: {job.reason}",
            f"status: {job.status}",
            f"run at: {job.run_at.isoformat()}",
            f"tries: {job.tries}",
            f"leased until: {job.lease_until.isoformat() if job.lease_until else 'not leased'}",
            f"last problem: {job.last_problem or 'none'}",
        ]
    )


def reconciliations(database: Database, _settings: Settings, _options: argparse.Namespace) -> str:
    with database.transaction() as session:
        listed = open_reconciliations(session)
    if not listed:
        return "No open reconciliations"
    return "\n\n".join(describe(item) for item in listed)


def recover(database: Database, settings: Settings, _options: argparse.Namespace) -> str:
    now = SystemClock().now()
    cutoff = now - timedelta(seconds=settings.attempt_creation_timeout_seconds)
    with database.transaction() as session:
        moved = recover_interrupted(session, cutoff, now)
    noun = "attempt" if moved == 1 else "attempts"
    return f"{moved} interrupted {noun} moved to reconciliation"


def events_line(summary: ProcessingSummary) -> str:
    noun = "event" if summary.applied == 1 else "events"
    duplicates = "duplicate" if summary.duplicates == 1 else "duplicates"
    return (
        f"{summary.applied} {noun} applied, {summary.unmatched} unmatched, "
        f"{summary.in_review} in review, {summary.duplicates} {duplicates}, "
        f"{summary.failed} failed"
    )


def process_events(database: Database, _settings: Settings, _options: argparse.Namespace) -> str:
    return events_line(process_received_events(database, SystemClock()))


def describe_exception(open_exception: OpenException) -> str:
    return "\n".join(
        [
            f"reason: {open_exception.reason}",
            f"sale reference: {open_exception.sale_reference or 'unassociated'}",
            f"event: {open_exception.event_id or 'none'}",
            f"expected amount cents: {open_exception.expected_amount_cents}",
            f"received amount cents: {open_exception.received_amount_cents}",
            f"opened at: {open_exception.created_at.isoformat()}",
        ]
    )


def exceptions(database: Database, _settings: Settings, _options: argparse.Namespace) -> str:
    with database.transaction() as session:
        found = [describe_exception(item) for item in open_exceptions(session)]
    return "\n\n".join(found) if found else "No open payment exceptions"


def describe_conflict(event: WebhookEvent, conflict: WebhookEventConflict) -> str:
    return "\n".join(
        [
            f"event: {event.provider_event_id} ({event.provider}, {event.environment})",
            "problem: conflicting content for an event id already stored",
            f"original digest: {event.payload_digest}",
            f"variant digest: {conflict.payload_digest}",
            f"variant received at: {conflict.received_at.isoformat()}",
        ]
    )


def conflicts(database: Database, _settings: Settings, _options: argparse.Namespace) -> str:
    with database.transaction() as session:
        found = [describe_conflict(event, conflict) for event, conflict in event_conflicts(session)]
    return "\n\n".join(found) if found else "No event conflicts"


RESULT_TEXT = {
    ReconciliationResult.CONFIRMED: "payment confirmed",
    ReconciliationResult.REVIEW: "payment evidence needs review",
    ReconciliationResult.NO_EVIDENCE: "no payment evidence found; the payment stays unconfirmed",
    ReconciliationResult.UNCERTAIN: (
        "provider query failed ({problem}); the payment stays unconfirmed"
    ),
    ReconciliationResult.NOT_QUERYABLE: (
        "the attempt has no QR id for this provider; the payment stays unconfirmed"
    ),
}


def describe_reconciliation(report: ReconciliationReport) -> str:
    return "\n".join(
        [
            f"attempt: {report.attempt.id}",
            f"sale reference: {report.attempt.sale_reference}",
            f"qr: {report.attempt.provider_request_id or 'none'}",
            f"payments found: {report.found}",
            f"applied: {report.applied}, duplicates: {report.duplicates}, "
            f"in review: {report.in_review}",
            f"attempt status: {report.attempt.status}",
            f"sale status: {report.sale_status}",
            f"result: {RESULT_TEXT[report.result].format(problem=report.problem)}",
        ]
    )


def reconcile(database: Database, settings: Settings, options: argparse.Namespace) -> str:
    report = reconcile_attempt(
        database, options.attempt_id, provider_from(settings), settings.environment, SystemClock()
    )
    return describe_reconciliation(report)


def run_jobs(database: Database, settings: Settings, _options: argparse.Namespace) -> str:
    summary = JobRunner(
        database,
        provider_from(settings),
        settings.environment,
        JobPolicy.from_settings(settings),
        SystemClock(),
    ).run()
    return "\n".join(
        [
            f"events: {events_line(summary.events)}",
            f"jobs of paid attempts closed: {summary.closed}",
            f"pending attempts expired: {summary.expired}",
            f"interrupted attempts moved to reconciliation: {summary.recovered}",
            f"jobs claimed: {summary.claimed}",
            f"confirmed: {summary.confirmed}, in review: {summary.in_review}, "
            f"rescheduled: {summary.rescheduled}, exhausted: {summary.exhausted}, "
            f"lease lost: {summary.lease_lost}, failed: {summary.failed}",
        ]
    )


COMMANDS: dict[str, Handler] = {
    "reconciliations": reconciliations,
    "recover-interrupted": recover,
    "process-events": process_events,
    "event-conflicts": conflicts,
    "exceptions": exceptions,
    "run-jobs": run_jobs,
}


def parse(arguments: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m tappy.sales")
    commands = parser.add_subparsers(dest="command", required=True)
    for name, handler in COMMANDS.items():
        commands.add_parser(name).set_defaults(handler=handler)
    reconciling = commands.add_parser("reconcile")
    reconciling.add_argument("attempt_id", type=uuid.UUID)
    reconciling.set_defaults(handler=reconcile)
    return parser.parse_args(arguments)


def main(arguments: Sequence[str]) -> int:
    options = parse(arguments)
    try:
        settings = load_settings()
    except ConfigurationError as error:
        print(error, file=sys.stderr)
        return 1
    database = Database.from_settings(settings)
    try:
        command: Handler = options.handler
        print(command(database, settings, options))
    except AttemptNotFoundError as error:
        print(error, file=sys.stderr)
        return 1
    finally:
        database.dispose()
    return 0
