import subprocess
from collections.abc import Iterator
from http import HTTPStatus
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from tappy.main import create_app
from tappy.platform.schema import upgrade_to_head
from tests.support import build_settings, free_port, isolated_environment

COMPOSE_FILE = Path(__file__).resolve().parents[1] / "compose.yaml"
PROBE_DATUM = "synthetic-persisted-datum"
LOCAL_PASSWORD = "synthetic-persistence-password"


class ComposeProject:
    def __init__(self) -> None:
        self.name = f"tappy-persistence-{uuid4().hex[:12]}"
        self.port = free_port()
        self.environment = isolated_environment(
            {
                "TAPPY_POSTGRES_PASSWORD": LOCAL_PASSWORD,
                "TAPPY_POSTGRES_PORT": str(self.port),
                "TAPPY_TEST_POSTGRES_PASSWORD": LOCAL_PASSWORD,
            }
        )

    @property
    def database_url(self) -> str:
        return f"postgresql+psycopg://tappy:{LOCAL_PASSWORD}@127.0.0.1:{self.port}/tappy"

    def compose(self, *arguments: str) -> str:
        result = subprocess.run(
            ["docker", "compose", "-f", str(COMPOSE_FILE), "-p", self.name, *arguments],
            env=self.environment,
            capture_output=True,
            text=True,
            timeout=180,
            check=True,
        )
        return result.stdout

    def start_database(self) -> None:
        self.compose("up", "--detach", "--wait", "db")

    def recreate_database(self) -> None:
        self.compose("down")
        self.start_database()

    def stop_database(self) -> None:
        self.compose("stop", "db")

    def query(self, sql: str) -> str:
        return self.compose(
            "exec", "-T", "db", "psql", "-U", "tappy", "-d", "tappy", "-tAc", sql
        ).strip()


@pytest.fixture
def local_compose() -> Iterator[ComposeProject]:
    project = ComposeProject()
    project.start_database()
    try:
        yield project
    finally:
        project.compose("down", "--volumes")


def store_probe(database_url: str) -> None:
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE persistence_probe (label text NOT NULL)"))
            connection.execute(
                text("INSERT INTO persistence_probe VALUES (:label)"), {"label": PROBE_DATUM}
            )
    finally:
        engine.dispose()


def database_names(database_url: str) -> set[str]:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            return set(connection.execute(text("SELECT datname FROM pg_database")).scalars())
    finally:
        engine.dispose()


def readiness(database_url: str) -> tuple[int, object]:
    with TestClient(create_app(build_settings(database_url=database_url))) as client:
        response = client.get("/ready")
        return response.status_code, response.json()


def test_local_data_survives_database_recreation_and_stays_out_of_test_server(
    local_compose: ComposeProject, empty_database_url: str
) -> None:
    upgrade_to_head(local_compose.database_url)
    store_probe(local_compose.database_url)

    local_compose.recreate_database()

    assert local_compose.query("SELECT label FROM persistence_probe") == PROBE_DATUM
    assert readiness(local_compose.database_url) == (HTTPStatus.OK, {"status": "ready"})
    assert "tappy" not in database_names(empty_database_url)


def test_readiness_turns_unavailable_when_local_postgres_stops(
    local_compose: ComposeProject,
) -> None:
    upgrade_to_head(local_compose.database_url)
    while_running = readiness(local_compose.database_url)

    local_compose.stop_database()

    assert while_running == (HTTPStatus.OK, {"status": "ready"})
    assert readiness(local_compose.database_url) == (
        HTTPStatus.SERVICE_UNAVAILABLE,
        {"status": "unavailable"},
    )
