from collections.abc import Iterator
from contextlib import contextmanager
from uuid import uuid4

from sqlalchemy import create_engine, make_url, text

DISPOSABLE_PREFIX = "tappy_test_"


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
