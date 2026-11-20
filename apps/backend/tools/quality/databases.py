import os
from collections.abc import Iterator
from contextlib import contextmanager
from uuid import uuid4

from sqlalchemy import create_engine, make_url, text

DISPOSABLE_PREFIX = "tappy_test_"
TEST_SERVER_VARIABLE = "TAPPY_TEST_DATABASE_URL"
LOCAL_DATABASE_VARIABLE = "TAPPY_DATABASE_URL"
LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


class IsolationError(Exception):
    pass


def server_address(url: str) -> tuple[str | None, int | None]:
    parsed = make_url(url)
    host = "loopback" if parsed.host in LOOPBACK_HOSTS else parsed.host
    return host, parsed.port


def same_server(first: str, second: str) -> bool:
    return server_address(first) == server_address(second)


def isolated_test_server() -> str:
    url = os.environ.get(TEST_SERVER_VARIABLE)
    if not url:
        raise IsolationError(
            f"{TEST_SERVER_VARIABLE} must point to the disposable test Postgres server"
        )
    local_url = os.environ.get(LOCAL_DATABASE_VARIABLE)
    if local_url and same_server(url, local_url):
        raise IsolationError(
            f"{TEST_SERVER_VARIABLE} must not point to the local development server"
        )
    return url


@contextmanager
def disposable_database(server_url: str) -> Iterator[str]:
    server = make_url(server_url)
    name = f"{DISPOSABLE_PREFIX}{uuid4().hex}"
    admin = create_engine(server, isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{name}"'))
        try:
            yield server.set(database=name).render_as_string(hide_password=False)
        finally:
            with admin.connect() as connection:
                connection.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
    finally:
        admin.dispose()
