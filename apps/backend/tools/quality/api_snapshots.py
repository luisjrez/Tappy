import argparse
import json
import sys
import tomllib
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Literal

from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict, SecretStr

from quality.api_diff import compare
from quality.databases import disposable_database, isolated_test_server
from tappy.main import create_app
from tappy.platform.config import Settings
from tappy.platform.schema import upgrade_to_head

ALLOWED_HEADERS = ("content-type",)
UNREACHABLE_DATABASE_URL = "postgresql+psycopg://contract:contract@127.0.0.1:1/contract"
CONTRACT_SECRET = SecretStr("contract-synthetic-secret-0123456789abcdef")


class SnapshotCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
    path: str
    database: Literal["migrated", "unreachable"]
    body: dict[str, object] | None = None
    normalize: tuple[str, ...] = ()


class Contracts(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    cases: tuple[SnapshotCase, ...]


@contextmanager
def database_for(case: SnapshotCase) -> Iterator[str]:
    if case.database == "unreachable":
        yield UNREACHABLE_DATABASE_URL
        return
    with disposable_database(isolated_test_server()) as database_url:
        upgrade_to_head(database_url)
        yield database_url


def capture(case: SnapshotCase) -> dict[str, object]:
    with database_for(case) as database_url:
        settings = Settings(
            environment="contract",
            secret_key=CONTRACT_SECRET,
            database_url=SecretStr(database_url),
        )
        with TestClient(create_app(settings)) as client:
            response = client.request(case.method, case.path, json=case.body)
    return {
        "status": int(response.status_code),
        "headers": {name: response.headers.get(name) for name in ALLOWED_HEADERS},
        "body": response.json(),
    }


def check_case(case: SnapshotCase, contracts_dir: Path, reports_dir: Path) -> bool:
    current = capture(case)
    (reports_dir / f"{case.name}.current.json").write_text(json.dumps(current, indent=2) + "\n")
    baseline_path = contracts_dir / "baselines" / f"{case.name}.json"
    if not baseline_path.exists():
        print(f"{case.name}: no approved baseline at {baseline_path}; review the current artifact")
        return False
    baseline = json.loads(baseline_path.read_text())
    revision = baseline.pop("revision", "unknown")
    differences = compare(baseline, current, case.normalize)
    report = "\n".join(str(difference) for difference in differences)
    (reports_dir / f"{case.name}.diff.txt").write_text(f"baseline {revision}\n{report}\n")
    if differences:
        print(f"{case.name}: {len(differences)} differences against {revision}\n{report}")
        return False
    print(f"{case.name}: no differences against {revision}")
    return True


def main(arguments: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog="quality.api_snapshots")
    parser.add_argument("--contracts", type=Path, default=Path("contracts/api"))
    parser.add_argument("--reports", type=Path, default=Path("reports/api"))
    options = parser.parse_args(arguments)
    with (options.contracts / "cases.toml").open("rb") as source:
        contracts = Contracts.model_validate(tomllib.load(source))
    options.reports.mkdir(parents=True, exist_ok=True)
    results = [check_case(case, options.contracts, options.reports) for case in contracts.cases]
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
