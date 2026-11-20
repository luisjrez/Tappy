from fastapi.testclient import TestClient
from pydantic import SecretStr

from tappy.main import create_app
from tappy.platform.config import Settings

VALID_SECRET = SecretStr("synthetic-secret-key-for-tests-0123456789")


def build_settings(environment: str) -> Settings:
    return Settings(environment=environment, secret_key=VALID_SECRET)


def test_health_reports_healthy_status() -> None:
    with TestClient(create_app(build_settings("test"))) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "environment": "test"}


def test_independent_app_instances_do_not_share_state() -> None:
    staging_app = create_app(build_settings("staging"))
    test_app = create_app(build_settings("test"))

    with TestClient(staging_app) as staging_client, TestClient(test_app) as test_client:
        staging_health = staging_client.get("/health").json()
        test_health = test_client.get("/health").json()

    assert staging_health == {"status": "ok", "environment": "staging"}
    assert test_health == {"status": "ok", "environment": "test"}
    assert staging_app.state is not test_app.state
