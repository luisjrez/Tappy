import argparse
import sys
from collections.abc import Sequence

from tappy.notifications.outbox import DeliveryReport, deliver_due
from tappy.notifications.sealing import Sealer
from tappy.notifications.transport import MailTransport, SmtpTransport
from tappy.platform.clock import SystemClock
from tappy.platform.config import ConfigurationError, Settings, load_settings
from tappy.platform.database import Database


def deliver_pending(settings: Settings, transport: MailTransport | None = None) -> DeliveryReport:
    database = Database.from_settings(settings)
    try:
        return deliver_due(
            database,
            transport or SmtpTransport(settings),
            Sealer.from_settings(settings),
            SystemClock().now(),
            settings.delivery_max_attempts,
        )
    finally:
        database.dispose()


def main(arguments: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m tappy.notifications")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("deliver", help="Send due emails from the outbox")
    parser.parse_args(arguments)
    try:
        settings = load_settings()
    except ConfigurationError as error:
        print(error, file=sys.stderr)
        return 1
    report = deliver_pending(settings)
    print(f"sent={report.sent} retried={report.retried} failed={report.failed}")
    return 0
