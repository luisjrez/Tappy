import argparse
import sys
from collections.abc import Callable, Sequence
from datetime import timedelta

from tappy.payments.events import WebhookEvent, WebhookEventConflict, event_conflicts
from tappy.platform.clock import SystemClock
from tappy.platform.config import ConfigurationError, Settings, load_settings
from tappy.platform.database import Database
from tappy.sales.attempts import PendingReconciliation, pending_reconciliations, recover_interrupted
from tappy.sales.payment_exceptions import OpenException, open_exceptions
from tappy.sales.receptions import process_received_events

Handler = Callable[[Database, Settings], str]


def describe(pending: PendingReconciliation) -> str:
    return "\n".join(
        [
            f"attempt: {pending.attempt.id}",
            f"sale reference: {pending.attempt.sale_reference}",
            f"attempt status: {pending.attempt.status}",
            f"reason: {pending.reason}",
            f"status: {pending.status}",
            f"run at: {pending.run_at.isoformat()}",
        ]
    )


def reconciliations(database: Database, _: Settings) -> str:
    with database.transaction() as session:
        pending = pending_reconciliations(session)
    if not pending:
        return "No pending reconciliations"
    return "\n\n".join(describe(item) for item in pending)


def recover(database: Database, settings: Settings) -> str:
    now = SystemClock().now()
    cutoff = now - timedelta(seconds=settings.attempt_creation_timeout_seconds)
    with database.transaction() as session:
        moved = recover_interrupted(session, cutoff, now)
    noun = "attempt" if moved == 1 else "attempts"
    return f"{moved} interrupted {noun} moved to reconciliation"


def process_events(database: Database, _: Settings) -> str:
    summary = process_received_events(database, SystemClock())
    noun = "event" if summary.applied == 1 else "events"
    duplicates = "duplicate" if summary.duplicates == 1 else "duplicates"
    return (
        f"{summary.applied} {noun} applied, {summary.unmatched} unmatched, "
        f"{summary.in_review} in review, {summary.duplicates} {duplicates}, "
        f"{summary.failed} failed"
    )


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


def exceptions(database: Database, _: Settings) -> str:
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


def conflicts(database: Database, _: Settings) -> str:
    with database.transaction() as session:
        found = [describe_conflict(event, conflict) for event, conflict in event_conflicts(session)]
    return "\n\n".join(found) if found else "No event conflicts"


COMMANDS: dict[str, Handler] = {
    "reconciliations": reconciliations,
    "recover-interrupted": recover,
    "process-events": process_events,
    "event-conflicts": conflicts,
    "exceptions": exceptions,
}


def parse(arguments: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m tappy.sales")
    commands = parser.add_subparsers(dest="command", required=True)
    for name, handler in COMMANDS.items():
        commands.add_parser(name).set_defaults(handler=handler)
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
        print(command(database, settings))
    finally:
        database.dispose()
    return 0
