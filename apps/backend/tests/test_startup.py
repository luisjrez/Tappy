from collections.abc import Iterator

import pytest

from tests.support import (
    UNREACHABLE_DATABASE_PASSWORD,
    UNREACHABLE_DATABASE_URL,
    VALID_SECRET,
    app_environment,
    free_port,
    run_tappy,
    spawn_tappy,
    wait_for_json,
)

SENSITIVE_SHORT_SECRET = "leaked-if-printed"


@pytest.fixture
def running_api() -> Iterator[int]:
    port = free_port()
    process = spawn_tappy(
        {
            **app_environment(UNREACHABLE_DATABASE_URL),
            "TAPPY_ENVIRONMENT": "local",
            "TAPPY_PORT": str(port),
        }
    )
    try:
        yield port
    finally:
        process.terminate()
        process.wait(timeout=10)


def test_started_api_answers_health(running_api: int) -> None:
    health = wait_for_json(f"http://127.0.0.1:{running_api}/health", deadline_seconds=10)

    assert health == {"status": "ok", "environment": "local"}


def test_startup_fails_when_required_variable_is_missing() -> None:
    result = run_tappy(
        {"TAPPY_SECRET_KEY": VALID_SECRET, "TAPPY_DATABASE_URL": UNREACHABLE_DATABASE_URL}
    )

    assert result.returncode != 0
    assert "TAPPY_ENVIRONMENT" in result.stderr
    assert "Traceback" not in result.stderr
    assert VALID_SECRET not in result.stderr + result.stdout
    assert UNREACHABLE_DATABASE_PASSWORD not in result.stderr + result.stdout


@pytest.mark.parametrize(
    "environment",
    [
        {"TAPPY_ENVIRONMENT": "test", "TAPPY_SECRET_KEY": SENSITIVE_SHORT_SECRET},
        {"TAPPY_SECRET_KEY": SENSITIVE_SHORT_SECRET},
    ],
)
def test_startup_failure_does_not_expose_secret_values(environment: dict[str, str]) -> None:
    result = run_tappy(environment)
    output = result.stderr + result.stdout

    assert result.returncode != 0
    assert "TAPPY_SECRET_KEY" in result.stderr
    assert SENSITIVE_SHORT_SECRET not in output
    assert str(len(SENSITIVE_SHORT_SECRET)) not in output
