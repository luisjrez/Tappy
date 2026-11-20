# Tappy backend

FastAPI modular monolith. Python 3.14, dependencies managed with uv inside `apps/backend/.venv`.

## Setup

```sh
cd apps/backend
uv sync
cp .env.example .env
```

Fill `.env` with local, non-production values. `TAPPY_SECRET_KEY` must have at least 32 characters.

## Run

```sh
set -a; source .env; set +a
uv run python -m tappy
curl http://127.0.0.1:8000/health
```

Missing or invalid configuration stops startup with the list of invalid variables; values are never printed.

## Checks

```sh
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest
```
