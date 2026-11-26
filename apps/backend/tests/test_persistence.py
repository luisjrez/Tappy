from http import HTTPStatus

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from tappy.main import create_app
from tappy.platform.schema import upgrade_to_head
from tests.compose_support import ComposeProject
from tests.support import build_settings

PROBE_DATUM = "synthetic-persisted-datum"


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
