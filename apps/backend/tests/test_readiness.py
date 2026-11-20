from http import HTTPStatus

from fastapi.testclient import TestClient

from tappy.main import create_app
from tappy.platform.schema import upgrade_to_head
from tests.support import UNREACHABLE_DATABASE_PASSWORD, build_settings


def test_readiness_reports_unavailable_database_without_internal_details() -> None:
    with TestClient(create_app(build_settings())) as client:
        response = client.get("/ready")

    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert response.json() == {"status": "unavailable"}
    assert UNREACHABLE_DATABASE_PASSWORD not in response.text
    assert "Error" not in response.text


def test_readiness_turns_ready_after_migrating_an_empty_database(empty_database_url: str) -> None:
    with TestClient(create_app(build_settings(database_url=empty_database_url))) as client:
        before_migrations = client.get("/ready")
        upgrade_to_head(empty_database_url)
        after_migrations = client.get("/ready")

    assert before_migrations.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert after_migrations.status_code == HTTPStatus.OK
    assert after_migrations.json() == {"status": "ready"}
