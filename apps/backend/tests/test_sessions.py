from http import HTTPStatus

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from tappy.main import create_app
from tappy.platform.dependencies import SessionDependency
from tests.support import build_settings


def test_each_request_uses_its_own_transaction(empty_database_url: str) -> None:
    setup_engine = create_engine(empty_database_url)
    with setup_engine.begin() as connection:
        connection.execute(text("CREATE TABLE session_probe (label text NOT NULL)"))
    sessions: list[Session] = []
    app = create_app(build_settings(database_url=empty_database_url))

    def write(label: str, session: SessionDependency) -> dict[str, str]:
        sessions.append(session)
        session.execute(text("INSERT INTO session_probe VALUES (:label)"), {"label": label})
        if label == "rejected":
            raise HTTPException(status_code=HTTPStatus.CONFLICT)
        return {"label": label}

    app.add_api_route("/probe/{label}", write, methods=["POST"])

    with TestClient(app) as client:
        accepted = client.post("/probe/accepted")
        rejected = client.post("/probe/rejected")
    with setup_engine.connect() as connection:
        stored = connection.execute(text("SELECT label FROM session_probe")).scalars().all()
    setup_engine.dispose()

    assert accepted.status_code == HTTPStatus.OK
    assert rejected.status_code == HTTPStatus.CONFLICT
    assert stored == ["accepted"]
    assert sessions[0] is not sessions[1]
