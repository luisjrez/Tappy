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

## First administrator

There is no public sign-up and no default password. Provision the first administrator from a trusted shell; the password is read only from standard input (hidden and confirmed when typed in a terminal), never from arguments or environment variables:

```sh
uv run python -m tappy.identity bootstrap-admin --email admin@example.com
uv run python -m tappy.identity show --email admin@example.com
```

Passwords are normalized with Unicode NFKC, need 12 to 128 characters and are rejected when they appear in a short list of common passwords; they are stored as Argon2id hashes. Running the command again for an existing email (compared case-insensitively) changes nothing and exits with an error.

## Session policy

`POST /auth/login` returns an opaque bearer token; only its SHA-256 digest is stored. `GET /auth/me` returns the identity that owns the token. Every rejected login (unknown email, wrong password, inactive identity) gets the same `401 Invalid email or password`.

| Setting | Default | Ticket |
| --- | --- | --- |
| `TAPPY_ACCESS_TOKEN_TTL_SECONDS` | `900` (15 minutes, minimum 60) | B05 |
| Renewal with atomic rotation | — | B06 |
| Absolute session lifetime | 30 days | B06 |

Logout and identity deactivation revoke access immediately (B06); a token of an inactive identity is already rejected.

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
