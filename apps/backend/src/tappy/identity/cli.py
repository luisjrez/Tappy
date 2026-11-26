import argparse
import getpass
import logging
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from tappy.identity.errors import IdentityError, PasswordPolicyError
from tappy.identity.lifecycle import deactivate_identity
from tappy.identity.passwords import PasswordPolicy
from tappy.identity.provisioning import (
    IdentitySummary,
    find_identity,
    normalize_email,
    provision_admin,
)
from tappy.platform.clock import SystemClock
from tappy.platform.config import ConfigurationError, load_settings
from tappy.platform.database import Database
from tappy.platform.diagnostics import configure_logging


@dataclass(frozen=True)
class CommandContext:
    database: Database
    policy: PasswordPolicy


Handler = Callable[[CommandContext, str], str]
logger = logging.getLogger(__name__)


def read_password() -> str:
    if sys.stdin.isatty():
        password = getpass.getpass("Password: ")
        if getpass.getpass("Repeat password: ") != password:
            raise PasswordPolicyError("Passwords do not match")
        return password
    return sys.stdin.readline().rstrip("\r\n")


def describe(summary: IdentitySummary) -> str:
    return "\n".join(
        [
            f"reference: {summary.reference}",
            f"email: {summary.email}",
            f"role: {summary.role}",
            f"status: {summary.status}",
        ]
    )


def bootstrap_admin(context: CommandContext, email: str) -> str:
    normalized_email = normalize_email(email)
    password = read_password()
    with context.database.transaction() as session:
        summary = provision_admin(session, normalized_email, password, context.policy)
    return "Administrator provisioned\n" + describe(summary)


def deactivate(context: CommandContext, email: str) -> str:
    with context.database.transaction() as session:
        summary = deactivate_identity(session, email, SystemClock().now())
    return "Identity deactivated; its sessions were revoked\n" + describe(summary)


def show(context: CommandContext, email: str) -> str:
    with context.database.transaction() as session:
        return describe(find_identity(session, email))


COMMANDS: dict[str, Handler] = {
    "bootstrap-admin": bootstrap_admin,
    "deactivate": deactivate,
    "show": show,
}


def parse(arguments: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m tappy.identity")
    commands = parser.add_subparsers(dest="command", required=True)
    for name, handler in COMMANDS.items():
        command = commands.add_parser(name)
        command.add_argument("--email", required=True)
        command.set_defaults(handler=handler)
    return parser.parse_args(arguments)


def main(arguments: Sequence[str]) -> int:
    options = parse(arguments)
    handler: Handler = options.handler
    try:
        settings = load_settings()
    except ConfigurationError as error:
        print(error, file=sys.stderr)
        return 1
    configure_logging(settings)
    database = Database.from_settings(settings)
    try:
        print(
            handler(CommandContext(database, PasswordPolicy.from_settings(settings)), options.email)
        )
    except IdentityError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    except Exception:
        logger.exception("Command %s failed", options.command)
        return 1
    finally:
        database.dispose()
    return 0
