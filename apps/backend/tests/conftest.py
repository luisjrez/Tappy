from collections.abc import Iterator

import pytest

from quality.databases import IsolationError, disposable_database, isolated_test_server


@pytest.fixture(scope="session")
def test_server_url() -> str:
    try:
        return isolated_test_server()
    except IsolationError as error:
        pytest.fail(str(error))


@pytest.fixture
def empty_database_url(test_server_url: str) -> Iterator[str]:
    with disposable_database(test_server_url) as url:
        yield url
