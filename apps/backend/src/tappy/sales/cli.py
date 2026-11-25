import argparse
import sys
from collections.abc import Callable, Sequence
from datetime import timedelta

from tappy.platform.clock import SystemClock
from tappy.platform.config import ConfigurationError, Settings, load_settings
from tappy.platform.database import Database
from tappy.sales.attempts import PendingReconciliation, pending_reconciliations, recover_interrupted

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


COMMANDS: dict[str, Handler] = {
    "reconciliations": reconciliations,
    "recover-interrupted": recover,
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
