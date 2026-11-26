import subprocess
from pathlib import Path
from uuid import uuid4

from tests.support import free_port, isolated_environment

COMPOSE_FILE = Path(__file__).resolve().parents[1] / "compose.yaml"
LOCAL_PASSWORD = "synthetic-persistence-password"


class ComposeProject:
    def __init__(self) -> None:
        self.name = f"tappy-compose-{uuid4().hex[:12]}"
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
        return self.database_url_for("tappy")

    def compose(self, *arguments: str) -> str:
        return self.compose_bytes(*arguments).decode()

    def compose_bytes(self, *arguments: str, stdin: bytes = b"") -> bytes:
        result = subprocess.run(
            ["docker", "compose", "-f", str(COMPOSE_FILE), "-p", self.name, *arguments],
            env=self.environment,
            input=stdin,
            capture_output=True,
            timeout=180,
            check=True,
        )
        return result.stdout

    def database_url_for(self, name: str) -> str:
        return f"postgresql+psycopg://tappy:{LOCAL_PASSWORD}@127.0.0.1:{self.port}/{name}"

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
