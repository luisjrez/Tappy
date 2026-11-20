import argparse
import getpass
import sys
from collections.abc import Sequence

from tappy.identity.passwords import PasswordPolicyError
from tappy.identity.provisioning import (
    IdentitySummary,
    ProvisioningError,
    find_identity,
    provision_admin,
)
from tappy.platform.config import ConfigurationError, load_settings
from tappy.platform.database import Database


def read_password() -> str:
    if sys.stdin.isatty():
        password = getpass.getpass("Password: ")
        if getpass.getpass("Repeat password: ") != password:
            raise ProvisioningError("Passwords do not match")
        return password
    return sys.stdin.readline().rstrip("\n")


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
    password = read_password()
    with database.transaction() as session:
        summary = provision_admin(session, email, password)
    return "Administrator provisioned\n" + describe(summary)


def show(database: Database, email: str) -> str:
    with database.transaction() as session:
        summary = find_identity(session, email)
    if summary is None:
        raise ProvisioningError("No identity with this email")
    return describe(summary)


def parse(arguments: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m tappy.identity")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("bootstrap-admin", "show"):
        command = commands.add_parser(name)
        command.add_argument("--email", required=True)
    return parser.parse_args(arguments)


def main(arguments: Sequence[str]) -> int:
    options = parse(arguments)
    try:
        database = Database.from_settings(load_settings())
    except ConfigurationError as error:
        print(error, file=sys.stderr)
        return 1
    try:
        if options.command == "bootstrap-admin":
            print(bootstrap_admin(database, options.email))
        else:
            print(show(database, options.email))
    except (ProvisioningError, PasswordPolicyError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    finally:
        database.dispose()
    return 0
