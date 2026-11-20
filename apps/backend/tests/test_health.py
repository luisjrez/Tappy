from http import HTTPStatus

from fastapi.testclient import TestClient
from pydantic import SecretStr

from tappy.main import create_app
from tappy.platform.config import Settings
from tests.support import VALID_SECRET


def build_settings(environment: str) -> Settings:
    return Settings(environment=environment, secret_key=SecretStr(VALID_SECRET))


def test_health_reports_healthy_status() -> None:
    with TestClient(create_app(build_settings("test"))) as client:
        response = client.get("/health")

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"status": "ok", "environment": "test"}


def test_independent_app_instances_do_not_share_state() -> None:
    staging_app = create_app(build_settings("staging"))
    test_app = create_app(build_settings("test"))
    staging_app.add_api_route("/staging-only", lambda: {"scope": "staging"})

    with TestClient(staging_app) as staging_client, TestClient(test_app) as test_client:
        staging_health = staging_client.get("/health").json()
        test_health = test_client.get("/health").json()
        staging_only = staging_client.get("/staging-only")
        leaked_route = test_client.get("/staging-only")

    assert staging_health == {"status": "ok", "environment": "staging"}
    assert test_health == {"status": "ok", "environment": "test"}
    assert staging_only.status_code == HTTPStatus.OK
    assert leaked_route.status_code == HTTPStatus.NOT_FOUND
