from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from tests.sales.support import start_client
from tests.support import build_settings


@pytest.fixture
def client(migrated_database_url: str) -> Iterator[TestClient]:
    settings = build_settings(database_url=migrated_database_url)
    with start_client(settings, migrated_database_url) as client:
        yield client
