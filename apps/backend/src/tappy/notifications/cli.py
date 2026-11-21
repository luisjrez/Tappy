import argparse
import sys
from collections.abc import Sequence

from tappy.identity.recovery import RecoveryService
from tappy.notifications.outbox import DeliveryContext, DeliveryReport, deliver_due
from tappy.notifications.sealing import Sealer
from tappy.notifications.transport import MailTransport, SmtpTransport
from tappy.platform.clock import SystemClock
from tappy.platform.config import ConfigurationError, Settings, load_settings
from tappy.platform.database import Database


def deliver_pending(settings: Settings, transport: MailTransport | None = None) -> DeliveryReport:
    database = Database.from_settings(settings)
    now = SystemClock().now()
    try:
        RecoveryService.from_settings(settings).process_jobs(database, now)
        context = DeliveryContext(
            database=database,
            transport=transport or SmtpTransport(settings),
            sealer=Sealer.from_settings(settings),
            max_attempts=settings.delivery_max_attempts,
        )
        return deliver_due(context, now)
    finally:
        database.dispose()


def main(arguments: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m tappy.notifications")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("deliver", help="Resolve recovery requests and send due emails")
    parser.parse_args(arguments)
    try:
        settings = load_settings()
    except ConfigurationError as error:
        print(error, file=sys.stderr)
        return 1
    report = deliver_pending(settings)
    print(f"sent={report.sent} retried={report.retried} failed={report.failed}")
    return 0
