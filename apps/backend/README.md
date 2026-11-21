# Tappy backend

FastAPI modular monolith. Python 3.14, dependencies managed with uv inside `apps/backend/.venv`.

## Setup

```sh
cd apps/backend
uv sync
cp .env.example .env
```

Fill `.env` with local, non-production values. `TAPPY_SECRET_KEY` must have at least 32 characters.

## Database

```sh
docker compose up -d --wait
set -a; source .env; set +a
uv run alembic upgrade head
```

`db` keeps local data in the `db-data` volume. `test-db` is a separate server on tmpfs used only by pytest: each test creates and drops its own `tappy_test_*` database, and the suite refuses to run when `TAPPY_TEST_DATABASE_URL` points to the same server as `TAPPY_DATABASE_URL`.

## Run

```sh
set -a; source .env; set +a
uv run python -m tappy
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/ready
```

`/ready` answers 200 only when Postgres is reachable and the schema is at the latest migration; otherwise 503 `{"status": "unavailable"}`.

Missing or invalid configuration stops startup with the list of invalid variables; values are never printed.

## Checks

One command runs the whole battery locally and in CI (`.github/workflows/backend.yml`). It needs the Compose services running and the variables from `.env` exported:

```sh
docker compose up -d --wait
set -a; source .env; set +a
uv run python -m quality.check
```

Steps, all executed even after a failure; the command exits non-zero if any fails:

| Step | Command |
| --- | --- |
| format | `ruff format --check .` |
| lint | `ruff check --no-fix .` |
| types | `mypy` (strict) |
| hygiene | `python -m quality.hygiene src tools tests` — flags comments by token, allows only `noqa`, `type: ignore[...]` and `pragma: no cover` directives |
| migrations | `python -m quality.migrations` — disposable database: upgrade, downgrade to base, upgrade, and model drift check |
| tests | `pytest --junitxml=reports/junit.xml` |
| evidence | `python -m quality.evidence ../../docs/evidence --junit=reports/junit.xml` — evaluates each ticket manifest (`docs/evidence/*.toml`): completeness = PASS AC / applicable AC without rounding, ≥97%, every mandatory AC passing, VC01 PASS or justified N/A, zero pending review findings |

`--steps format,lint` runs a subset. `python -m quality.api_diff baseline.json current.json --normalize body.id` compares two API snapshots after declared normalization (relations between normalized values are preserved, list order is significant) and exits 1 on any difference; it never writes the baseline.
