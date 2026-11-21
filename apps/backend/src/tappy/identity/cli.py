import argparse
import getpass
import sys
from collections.abc import Callable, Sequence

from tappy.identity.errors import IdentityError, PasswordPolicyError
from tappy.identity.provisioning import (
    IdentitySummary,
    find_identity,
    normalize_email,
    provision_admin,
)
from tappy.platform.config import ConfigurationError, load_settings
from tappy.platform.database import Database

Handler = Callable[[Database, str], str]


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


def bootstrap_admin(database: Database, email: str) -> str:
    normalized_email = normalize_email(email)
    password = read_password()
    with database.transaction() as session:
        summary = provision_admin(session, normalized_email, password)
    return "Administrator provisioned\n" + describe(summary)


def show(database: Database, email: str) -> str:
    with database.transaction() as session:
        return describe(find_identity(session, email))


COMMANDS: dict[str, Handler] = {"bootstrap-admin": bootstrap_admin, "show": show}


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
        database = Database.from_settings(load_settings())
    except ConfigurationError as error:
        print(error, file=sys.stderr)
        return 1
    try:
        print(handler(database, options.email))
    except IdentityError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    finally:
        database.dispose()
    return 0
