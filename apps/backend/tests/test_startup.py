import json
import os
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from urllib.error import URLError
from urllib.request import urlopen

import pytest

SENSITIVE_SHORT_SECRET = "leaked-if-printed"
VALID_SECRET = "synthetic-secret-key-for-tests-0123456789"


def isolated_environment(environment: dict[str, str]) -> dict[str, str]:
    inherited = {key: value for key, value in os.environ.items() if not key.startswith("TAPPY_")}
    return {**inherited, **environment}


def start_api(environment: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "tappy"],
        env=isolated_environment(environment),
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port: int = probe.getsockname()[1]
        return port


def wait_for_json(url: str, deadline_seconds: float) -> object:
    deadline = time.monotonic() + deadline_seconds
    while True:
        try:
            with urlopen(url, timeout=1) as response:
                return json.load(response)
        except URLError:
            if time.monotonic() > deadline:
                raise
            time.sleep(0.1)


@pytest.fixture
def running_api() -> Iterator[int]:
    port = free_port()
    process = subprocess.Popen(
        [sys.executable, "-m", "tappy"],
        env=isolated_environment(
            {
                "TAPPY_ENVIRONMENT": "local",
                "TAPPY_SECRET_KEY": VALID_SECRET,
                "TAPPY_PORT": str(port),
            }
        ),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
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
    result = start_api({"TAPPY_ENVIRONMENT": "test"})

    assert result.returncode != 0
    assert "TAPPY_SECRET_KEY" in result.stderr
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize(
    "environment",
    [
        {"TAPPY_ENVIRONMENT": "test", "TAPPY_SECRET_KEY": SENSITIVE_SHORT_SECRET},
        {"TAPPY_SECRET_KEY": SENSITIVE_SHORT_SECRET},
    ],
)
def test_startup_failure_does_not_expose_secret_values(environment: dict[str, str]) -> None:
    result = start_api(environment)

    assert result.returncode != 0
    assert "TAPPY_SECRET_KEY" in result.stderr
    assert SENSITIVE_SHORT_SECRET not in result.stderr
    assert SENSITIVE_SHORT_SECRET not in result.stdout
