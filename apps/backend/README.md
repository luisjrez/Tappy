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

`POST /auth/login` returns an opaque access token and an opaque refresh token; only their SHA-256 digests are stored. Every rejected login (unknown email, wrong password, inactive identity) gets the same `401 Invalid email or password`. `GET /auth/me` returns the identity that owns the access token.

| Setting | Default |
| --- | --- |
| `TAPPY_ACCESS_TOKEN_TTL_SECONDS` | `900` (15 minutes, minimum 60) |
| `TAPPY_SESSION_MAX_LIFETIME_SECONDS` | `2592000` (30 days, minimum 3600) |

- `POST /auth/refresh {"refresh_token": …}` rotates atomically: it returns a new pair and the previous access and refresh tokens stop working. Renewal never extends the session beyond its absolute lifetime, counted from login.
- Presenting a refresh token that was rotated more than 10 seconds earlier (reuse) fails and revokes the whole session; a concurrent duplicate renewal within that window only fails, so the winning renewal keeps working.
- `POST /auth/logout` with the bearer token (also accepted once expired, never once rotated or revoked) revokes the whole session: neither its access token nor its refresh token work afterwards.
- `uv run python -m tappy.identity deactivate --email …` marks the identity inactive and revokes all its sessions.

## Operators API

Administrator bearer token required (`401` without a valid token, `403` for operators). There is no public sign-up.

| Method and path | Result |
| --- | --- |
| `POST /operators {"email", "initial_password"}` | `201` with `reference`, `email`, `role`, `status`; `409` if the email exists (case-insensitive); `422` for an invalid email or password policy. The password is never echoed. |
| `GET /operators` · `GET /operators/{reference}` | Operator identities only (`404` for administrators or unknown references) |
| `POST /operators/{reference}/deactivate` | Marks the operator inactive and revokes all its sessions |

## Back office

Starlette Admin is mounted at `/admin`. Only active administrators can sign in; operators and anonymous visitors are sent back to the login page. The panel reuses the API session model: signing in creates the same revocable session as `POST /auth/login`, expired access is renewed with the stored refresh token, and the logout button revokes the session.

- The browser session lives in the `tappy_admin_session` cookie: `HttpOnly`, `SameSite=Strict`, and `Secure` unless `TAPPY_ADMIN_SECURE_COOKIES=false` (only for local HTTP development).
- Every mutating request (sign-in and sign-out included) needs the signed CSRF token rendered in the form; requests without it get `403`. Starlette Admin marks its CSRF cookie `Secure` when the request scheme is HTTPS, so behind a TLS-terminating proxy run Uvicorn with forwarded headers (`--proxy-headers` and `--forwarded-allow-ips`).
- Replaying an old panel cookie whose refresh token was already rotated revokes the whole session, exactly like the API.
- **Operators** page (`/admin/operators`): create an operator with an initial password that the administrator delivers in person (never emailed, never shown again) and deactivate operators; deactivation revokes their sessions immediately. There is no generic CRUD over identities.
- Starlette Admin's own logger is limited to errors so sign-in attempts do not write emails to the logs.

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
