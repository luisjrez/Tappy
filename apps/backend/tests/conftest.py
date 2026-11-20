import os
from collections.abc import Iterator

import pytest
from sqlalchemy import make_url

from quality.databases import disposable_database

TEST_SERVER_VARIABLE = "TAPPY_TEST_DATABASE_URL"
LOCAL_DATABASE_VARIABLE = "TAPPY_DATABASE_URL"


@pytest.fixture(scope="session")
def test_server_url() -> str:
    url = os.environ.get(TEST_SERVER_VARIABLE)
    if not url:
        pytest.fail(f"{TEST_SERVER_VARIABLE} must point to the disposable test Postgres server")
    local_url = os.environ.get(LOCAL_DATABASE_VARIABLE)
    if local_url and same_server(url, local_url):
        pytest.fail(f"{TEST_SERVER_VARIABLE} must not point to the local development server")
    return url


LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def server_address(url: str) -> tuple[str | None, int | None]:
    parsed = make_url(url)
    host = "loopback" if parsed.host in LOOPBACK_HOSTS else parsed.host
    return host, parsed.port


def same_server(first: str, second: str) -> bool:
    return server_address(first) == server_address(second)


@pytest.fixture
def empty_database_url(test_server_url: str) -> Iterator[str]:
    with disposable_database(test_server_url) as url:
        yield url
