from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response

from tappy.main import create_app
from tests.support import MovableClock, build_settings, create_identity, run_identity

EMAIL = "operadora@tappy.example"
PASSWORD = "mostrador seguro 2026"
START = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)


@pytest.fixture
def clock() -> MovableClock:
    return MovableClock(START)


@pytest.fixture
def client(migrated_database_url: str, clock: MovableClock) -> Iterator[TestClient]:
    create_identity(migrated_database_url, EMAIL, PASSWORD)
    app = create_app(build_settings(database_url=migrated_database_url), clock=clock)
    with TestClient(app) as client:
        yield client


def log_in(client: TestClient) -> dict[str, str]:
    response = client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert response.status_code == HTTPStatus.OK
    tokens: dict[str, str] = response.json()
    return tokens


def refresh(client: TestClient, refresh_token: str) -> Response:
    return client.post("/auth/refresh", json={"refresh_token": refresh_token})


def me_status(client: TestClient, access_token: str) -> int:
    return client.get("/auth/me", headers={"Authorization": f"Bearer {access_token}"}).status_code


def test_renewal_issues_working_tokens_and_retires_the_previous_pair(client: TestClient) -> None:
    first = log_in(client)

    renewed = client.post("/auth/refresh", json={"refresh_token": first["refresh_token"]})
    second = renewed.json()

    assert renewed.status_code == HTTPStatus.OK
    assert me_status(client, second["access_token"]) == HTTPStatus.OK
    assert me_status(client, first["access_token"]) == HTTPStatus.UNAUTHORIZED
    assert second["refresh_token"] != first["refresh_token"]


def test_expired_access_token_can_be_renewed_within_the_session_lifetime(
    client: TestClient, clock: MovableClock
) -> None:
    first = log_in(client)
    clock.advance(timedelta(minutes=20))

    expired_access = me_status(client, first["access_token"])
    renewed = refresh(client, first["refresh_token"])

    assert expired_access == HTTPStatus.UNAUTHORIZED
    assert renewed.status_code == HTTPStatus.OK
    assert me_status(client, renewed.json()["access_token"]) == HTTPStatus.OK


def test_session_cannot_be_renewed_past_its_absolute_lifetime(
    client: TestClient, clock: MovableClock
) -> None:
    tokens = log_in(client)
    for _ in range(29):
        clock.advance(timedelta(days=1))
        tokens = refresh(client, tokens["refresh_token"]).json()
    assert tokens["refresh_expires_at"] == "2026-12-20T12:00:00Z"

    clock.advance(timedelta(days=1))
    expired = refresh(client, tokens["refresh_token"])

    assert expired.status_code == HTTPStatus.UNAUTHORIZED
    assert expired.json() == {"detail": "Invalid refresh token"}


def test_reused_refresh_token_fails_and_revokes_the_whole_session(client: TestClient) -> None:
    first = log_in(client)
    second = refresh(client, first["refresh_token"]).json()

    reused = refresh(client, first["refresh_token"])

    assert reused.status_code == HTTPStatus.UNAUTHORIZED
    assert me_status(client, second["access_token"]) == HTTPStatus.UNAUTHORIZED
    assert refresh(client, second["refresh_token"]).status_code == HTTPStatus.UNAUTHORIZED


def test_logged_out_session_is_not_revived_by_renewal(client: TestClient) -> None:
    tokens = log_in(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    logout = client.post("/auth/logout", headers=headers)

    assert logout.status_code == HTTPStatus.NO_CONTENT
    assert me_status(client, tokens["access_token"]) == HTTPStatus.UNAUTHORIZED
    assert refresh(client, tokens["refresh_token"]).status_code == HTTPStatus.UNAUTHORIZED


def test_concurrent_renewals_issue_at_most_one_session(client: TestClient) -> None:
    tokens = log_in(client)

    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(lambda _: refresh(client, tokens["refresh_token"]), range(4)))

    successes = [response for response in responses if response.status_code == HTTPStatus.OK]
    assert len(successes) <= 1
    assert all(
        response.status_code in {HTTPStatus.OK, HTTPStatus.UNAUTHORIZED} for response in responses
    )


def test_deactivated_identity_loses_access_and_renewal(
    client: TestClient, migrated_database_url: str
) -> None:
    tokens = log_in(client)

    deactivated = run_identity(migrated_database_url, "deactivate", "--email", EMAIL)

    assert deactivated.returncode == 0, deactivated.stderr
    assert "status: inactive" in deactivated.stdout
    assert me_status(client, tokens["access_token"]) == HTTPStatus.UNAUTHORIZED
    assert refresh(client, tokens["refresh_token"]).status_code == HTTPStatus.UNAUTHORIZED
    relogin = client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert relogin.status_code == HTTPStatus.UNAUTHORIZED
