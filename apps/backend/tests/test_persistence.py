import subprocess
from collections.abc import Iterator
from http import HTTPStatus
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text

from tappy.main import create_app
from tappy.platform.migrations import upgrade_to_head
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

    def restart_database(self) -> None:
        self.compose("restart", "db")
        self.start_database()

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


def test_local_data_survives_database_restart_and_stays_out_of_test_database(
    local_compose: ComposeProject, empty_database_url: str
) -> None:
    upgrade_to_head(local_compose.database_url)
    local_compose.query("CREATE TABLE persistence_probe (label text NOT NULL)")
    local_compose.query("INSERT INTO persistence_probe VALUES ('synthetic-persisted-datum')")

    local_compose.restart_database()

    with TestClient(create_app(build_settings(database_url=local_compose.database_url))) as client:
        readiness = client.get("/ready")
    test_engine = create_engine(empty_database_url)
    with test_engine.connect() as connection:
        test_tables = inspect(connection).get_table_names()
        test_databases = connection.execute(text("SELECT datname FROM pg_database")).scalars()
        test_database_names = set(test_databases)
    test_engine.dispose()

    assert local_compose.query("SELECT label FROM persistence_probe") == PROBE_DATUM
    assert readiness.status_code == HTTPStatus.OK
    assert "persistence_probe" not in test_tables
    assert "tappy" not in test_database_names
