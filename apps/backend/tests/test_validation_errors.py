from collections.abc import Iterator
from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient

from tappy.main import create_app
from tests.support import build_settings

PASSWORD = "frase sintetica privada 2026"


@pytest.fixture
def client(migrated_database_url: str) -> Iterator[TestClient]:
    with TestClient(create_app(build_settings(database_url=migrated_database_url))) as client:
        yield client


def test_validation_errors_do_not_echo_submitted_values(client: TestClient) -> None:
    missing_email = client.post("/auth/login", json={"password": PASSWORD})
    extra_field = client.post(
        "/auth/login", json={"email": "a@tappy.example", "password": "x", "token": PASSWORD}
    )

    for response in (missing_email, extra_field):
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
        assert PASSWORD not in response.text
        assert all(set(issue) == {"type", "loc", "msg"} for issue in response.json()["detail"])
    assert missing_email.json()["detail"] == [
        {"type": "missing", "loc": ["body", "email"], "msg": "Field required"}
    ]
