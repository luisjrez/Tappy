import os
import socket
import subprocess
import sys

from pydantic import SecretStr

from tappy.platform.config import Settings

VALID_SECRET = "synthetic-secret-key-for-tests-0123456789"
UNREACHABLE_DATABASE_PASSWORD = "synthetic-unreachable-password"
UNREACHABLE_DATABASE_URL = (
    f"postgresql+psycopg://tappy:{UNREACHABLE_DATABASE_PASSWORD}@127.0.0.1:1/tappy"
)
TAPPY_COMMAND = (sys.executable, "-m", "tappy")


def build_settings(
    environment: str = "test", database_url: str = UNREACHABLE_DATABASE_URL
) -> Settings:
    return Settings(
        environment=environment,
        secret_key=SecretStr(VALID_SECRET),
        database_url=SecretStr(database_url),
    )


def isolated_environment(environment: dict[str, str]) -> dict[str, str]:
    inherited = {key: value for key, value in os.environ.items() if not key.startswith("TAPPY_")}
    return {**inherited, **environment}


def run_tappy(environment: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        TAPPY_COMMAND,
        env=isolated_environment(environment),
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )


def spawn_tappy(environment: dict[str, str]) -> subprocess.Popen[bytes]:
    return subprocess.Popen(
        TAPPY_COMMAND,
        env=isolated_environment(environment),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port: int = probe.getsockname()[1]
        return port
