import os
from collections.abc import Iterator
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, make_url, text

TEST_SERVER_VARIABLE = "TAPPY_TEST_DATABASE_URL"
LOCAL_DATABASE_VARIABLE = "TAPPY_DATABASE_URL"
TEST_DATABASE_PREFIX = "tappy_test_"


@pytest.fixture(scope="session")
def test_server_url() -> str:
    url = os.environ.get(TEST_SERVER_VARIABLE)
    if not url:
        pytest.fail(f"{TEST_SERVER_VARIABLE} must point to the disposable test Postgres server")
    local_url = os.environ.get(LOCAL_DATABASE_VARIABLE)
    if local_url and same_server(url, local_url):
        pytest.fail(f"{TEST_SERVER_VARIABLE} must not point to the local development server")
    return url


def same_server(first: str, second: str) -> bool:
    first_url, second_url = make_url(first), make_url(second)
    return (first_url.host, first_url.port) == (second_url.host, second_url.port)


@pytest.fixture
def empty_database_url(test_server_url: str) -> Iterator[str]:
    server = make_url(test_server_url)
    name = f"{TEST_DATABASE_PREFIX}{uuid4().hex}"
    admin = create_engine(server, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{name}"'))
    try:
        yield server.set(database=name).render_as_string(hide_password=False)
    finally:
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
        admin.dispose()
