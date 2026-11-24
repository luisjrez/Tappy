import os
import socket
import subprocess
import sys
import time
from datetime import datetime, timedelta

import pytest
from pydantic import SecretStr
from sqlalchemy import create_engine, text

from tappy.identity.models import IdentityStatus, Role
from tappy.identity.passwords import hash_password
from tappy.platform.config import Settings

VALID_SECRET = "synthetic-secret-key-for-tests-0123456789"
UNREACHABLE_DATABASE_PASSWORD = "synthetic-unreachable-password"
UNREACHABLE_DATABASE_URL = (
    f"postgresql+psycopg://tappy:{UNREACHABLE_DATABASE_PASSWORD}@127.0.0.1:1/tappy"
)
TAPPY_COMMAND = (sys.executable, "-m", "tappy")
IDENTITY_COMMAND = (sys.executable, "-m", "tappy.identity")


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


def app_environment(database_url: str) -> dict[str, str]:
    return {
        "TAPPY_ENVIRONMENT": "test",
        "TAPPY_SECRET_KEY": VALID_SECRET,
        "TAPPY_DATABASE_URL": database_url,
    }


def run_identity(
    database_url: str, *arguments: str, stdin: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [*IDENTITY_COMMAND, *arguments],
        env=isolated_environment(app_environment(database_url)),
        input=stdin,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def execute(database_url: str, sql: str, parameters: dict[str, object] | None = None) -> None:
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(text(sql), parameters or {})
    finally:
        engine.dispose()


def scalar(database_url: str, sql: str, parameters: dict[str, object] | None = None) -> object:
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            return connection.execute(text(sql), parameters or {}).scalar_one()
    finally:
        engine.dispose()


def create_identity(
    database_url: str,
    email: str,
    password: str,
    *,
    role: Role = Role.OPERATOR,
    status: IdentityStatus = IdentityStatus.ACTIVE,
) -> str:
    return str(
        scalar(
            database_url,
            "INSERT INTO identities (id, email, password_hash, role, status) "
            "VALUES (gen_random_uuid(), :email, :hash, :role, :status) RETURNING id",
            {"email": email, "hash": hash_password(password), "role": role, "status": status},
        )
    )


def wait_until_blocked_on_a_lock(database_url: str) -> None:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        waiting = scalar(
            database_url,
            "SELECT count(*) FROM pg_stat_activity "
            "WHERE datname = current_database() AND wait_event_type = 'Lock'",
        )
        if waiting:
            return
        time.sleep(0.01)
    pytest.fail("the request never waited for a row lock")


class MovableClock:
    def __init__(self, start: datetime) -> None:
        self.current = start

    def now(self) -> datetime:
        return self.current

    def advance(self, delta: timedelta) -> None:
        self.current += delta
