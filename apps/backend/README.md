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

Requires the Compose services running and the variables from `.env` exported (the persistence test also drives `docker compose`).

```sh
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest
```
