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

## Merchants

Every merchant query is scoped by membership: administrators see every merchant, operators only the merchants they belong to. A merchant outside the caller's scope answers `404` (its existence is not revealed).

| Method and path | Who | Result |
| --- | --- | --- |
| `GET /merchants` · `GET /merchants/{id}` | Any active identity | Merchants within scope, with their operators |
| `POST /merchants {"name"}` | Administrators | Create a merchant |
| `POST /merchants/{id}/members {"operator_reference"}` | Administrators | `201` assigns an active operator; repeating it answers `200` and keeps the original membership |

The back office has a **Merchants** page to create merchants and assign operators.

### Receiving accounts

Each merchant has at most one receiving account: an account already authorized at the provider, registered by an administrator. Tappy never opens bank accounts and offers no public sign-up for them.

| Method and path | Who | Result |
| --- | --- | --- |
| `PUT /merchants/{id}/receiver {"provider_account_id", "beneficiary_name", "clabe", "enabled"}` | Administrators | Creates or replaces the receiving account. The CLABE needs 18 digits and a valid check digit; only its last 4 digits are stored. A provider account ID used by another merchant answers `409` |
| `GET /merchants/{id}/receiver` | Any active identity within scope | Beneficiary, masked account (`**************1234`), `enabled`, `can_issue` and `blocked_reason`; `404` when none is configured |
| `POST /merchants/{id}/issuance-check {}` | Any active identity within scope | `200` with the receiver new charges will use, or `409` with the reason they are blocked (no receiver, or receiver disabled). The body accepts no fields: callers cannot choose a receiver |

Disabling a receiving account only blocks new charges; the account and the merchant's records stay. The same rule decides availability in the API, the issuance check and the back office, where the **Merchants** page shows and edits each receiving account.

## Sales

A sale is the commercial obligation to receive a fixed amount. Creating one does not request money from the bank and does not mean anything was paid.

| Method and path | Who | Result |
| --- | --- | --- |
| `POST /sales {"merchant_id", "amount_cents", "concept"?}` with `Idempotency-Key` | Operators of that merchant | `201` with the sale; `200` with the same sale when the key is repeated with the same content; `409` when the key was used with other content; `404` for a merchant outside the caller's memberships; `409` with the reason when the merchant has no enabled receiving account; `403` for administrators |
| `GET /sales/{id}` | Operators of the sale's merchant and administrators | The stored sale; `404` for unknown sales or sales of other merchants |
| `POST /sales/{id}/attempts {"method": "qr" \| "phone" \| "link"}` with `Idempotency-Key` | Operators of the sale's merchant | `201` reserves a payment attempt in `creating`; `200` with the same attempt when the key is repeated; `409` when the sale already has an active attempt, is not `open`, its merchant cannot issue charges, or the key was used with other content |

- `amount_cents` is a JSON integer of MXN centavos between 1 and `TAPPY_SALE_MAX_AMOUNT_CENTS` (default and upper bound 100000000, the provider's documented maximum). Decimals, strings and booleans are rejected; nothing is rounded.
- `concept` is optional, collapses whitespace and has at most 40 characters (the provider's limit for the text shown to the payer).
- Every sale gets a unique 10-character `reference`, starts as `open` and keeps a snapshot of the beneficiary and masked account it was created for, so later receiver changes do not rewrite it. The body accepts no receiver, currency, status or reference.
- `Idempotency-Key` is required (8–128 letters, digits, `-` or `_`; a UUID works). Generate one when the operator confirms the sale and resend it on every retry. Keys belong to the identity that used them and are stored in Postgres, so repeats are recognised across restarts, processes and concurrent requests: a concurrent repeat waits for the first request and then returns its sale. A request that fails (validation, blocked receiver) does not consume its key.
- A sale has at most one active payment attempt (`creating`, `pending` or `reconciling`), enforced by a partial unique index; `expired` and `failed` attempts allow a new one. Reserving locks the sale row only for that short transaction and never calls the provider, so an interrupted process leaves the attempt in `creating`, visible in `GET /sales/{id}` under `attempts`. Reserving an attempt does not request money yet.
- A `qr` attempt asks the configured QR provider for the QR after the reservation commits, then stores the provider's request ID and the exact QR payload and moves the attempt to `pending`. Repeating the request (same key) or reading the sale again never asks the provider for another QR. `pending` only means the QR exists: it never means money was received. `phone` and `link` attempts stay reserved until their channels exist.
- The provider is chosen with `TAPPY_PAYMENT_PROVIDER`:
  - `simulated` (default): a local simulator whose attempts carry `"simulated": true` and whose payloads start with `SIMULATED-CODI-QR` (they cannot be paid).
  - `pey`: calls `POST /codi/qr` of the pey CoDi API (contract `2026-10-20`) with `TAPPY_PEY_API_KEY` as a server-side bearer token, `TAPPY_PEY_BASE_URL` (default `https://api.pey.mx`; plain `http://` only for `127.0.0.1`/`localhost`) and `TAPPY_PEY_TIMEOUT_SECONDS` (default 10). Centavos are sent as exact pesos, the QR goes to the receiving account snapshotted on the sale (`bankAccountId`), and the attempt keeps pey's `id` and `qrString` exactly. A rejection (400/429) fails the attempt with pey's error type (`failure_code`, API `502`); a timeout, connection failure, server error or invalid answer keeps the attempt `creating` (API `503`) and never invents an ID. The key never appears in responses or logs. Real delivery against pey has not been exercised yet. A QR is refused with `409` when the merchant's receiving account changed after the sale was created, so the payer never sees a beneficiary different from the sale's.
- A QR is usable for `TAPPY_QR_EXPIRATION_SECONDS` (default 900, at least pey's minimum of 360, at most one day). The window is sent to pey as `expiration` and the attempt shows `expires_at`, counted from just before the provider call, so it never outlasts pey's own window. Expiration uses the server clock only: reading the sale (`GET /sales/{id}`) or the `run-jobs` batch moves a `pending` attempt past `expires_at` to `expired`; client clocks, `Date` headers or parameters never change it. `expired` means the display window ended, not that the bank revoked or rejected anything: the sale stays `open`, no `failure_code` is set and an authentic late payment still confirms it. `paid` attempts never expire, and `reconciling` attempts are not expired by their window. Each attempt carries a `next_action`: `wait_for_qr` (creating), `show_qr` (pending), `wait_for_verification` (reconciling), `verify_before_retry` (expired, then `new_attempt` once verified unpaid), `new_attempt` (failed) or `none` (paid).
- `covered` is `true` once an attempt received the exact amount. When an attempt covers the sale, the other active attempts are withdrawn (`withdrawn_at`, `next_action: hide_qr`): their QR should no longer be shown, but nothing is cancelled at the bank, and a payment that still arrives through them is recorded as a double reception. An authentic late payment to an old `expired` attempt covers the sale the same way. On a sale that is no longer `open`, attempts that were not paid suggest `none`.
- `GET /sales` lists the sales the caller may see (operators: their merchants; administrators: all), one row per sale, newest first (`created_at`, then id). Each row has the amount, status, `covered`, `confirmed_amount_cents`, `attempt_count` and the receiver snapshot. Filters: `merchant_id` (`404` for a merchant the caller cannot access), `status` (`open` = pending, `paid`, `review`; a `review` sale may already be `covered`), `created_from` / `created_to` (timestamps with a time zone, `from` inclusive and `to` exclusive). `limit` is 1–50 (default 20; the architecture's page maximum); the response's `next_cursor` is passed back as `cursor` for the next page, and rows created meanwhile never shift or repeat later pages. Invalid or unknown filters, limits or cursors answer `422`. Sales keep showing their receiver snapshot even after the receiver is disabled.
- `GET /sales/{id}/receipt` returns the data of a receipt, without generating a PDF, only for a sale with a confirmed reception: the exact transfer of a `paid` attempt (the first one when there are more). It contains the sale reference, merchant name, beneficiary and masked account snapshot, amount, currency, concept, pey's transaction id, payment and reception times, `simulated` and `under_review` (a double reception keeps the sale in review). Payer data, raw provider payloads, account identifiers and credentials are never included. A pending sale or one with only a different amount answers `404` "The sale has no confirmed reception"; another merchant's sale answers `404` "Sale not found".
- `GET /merchants/{id}/summary/daily?date=YYYY-MM-DD` summarizes one business day of a merchant the caller may see (`404` otherwise). The day runs from local midnight to midnight in `TAPPY_TIMEZONE` (default `America/Mexico_City`, any IANA zone); without `date` it is today on the server clock. Money received is the sum of the recorded transfers paid that day (pey's payment time), so pending sales count nothing and a repeated notification never adds twice. It reports `received_amount_cents`, `transfer_count`, `covered_sale_count` (sales whose covering transfer, the first exact one, was paid that day: a second transfer adds money but never another covered sale, on any day), `review_sale_count` (sales in review with transfers that day) and `open_exception_count` (the merchant's open exceptions opened that day, with or without a transfer). A day without transfers reports zeros.
- `GET /merchants/{id}/summary?period=day|week|month&date=YYYY-MM-DD` reports the local day, the Monday-to-Sunday week or the calendar month containing `date` (today on the server clock without it), with explicit `start` and `end` dates and a daily breakdown (`days`, including days without transfers). Totals follow the same rules as the daily summary, which is the `day` period. A transfer is dated by pey's payment time; a valid reception whose evidence carries no `datePaid` is recorded and dated by its reception time instead, shown as `dated_by: reception` (with `occurred_at: null`) on the sale and the receipt and counted in `reception_dated_transfer_count`. A present but invalid `datePaid` is still incomplete evidence. A month-end payment notified the next month counts in its bank month, once, also when reconciliation finds it again; when later evidence for the same transaction brings the bank time of a reception-dated transfer, that bank time is filled in once (the only change the database allows on a recorded transfer) and the transfer moves to its bank period without changing the money. Unknown periods or parameters answer `422`.
- A new attempt on the same sale is a retry: it keeps the sale, amount and reference and links the previous attempt (`previous_attempt_id`; each attempt can be retried once). It is refused with `409` while an attempt is active or uncertain (`creating`, `pending`, `reconciling`) and while the latest attempt is `expired` but not yet verified. Expiring an attempt enqueues a verification job; when `run-jobs` (or `reconcile`) finds no payment for the expired QR, the attempt gets `verified_at` and a retry is allowed; a payment found instead confirms the sale. `failed` attempts can be retried at once. `late_payment_possible` is `true` on a retry whose previous attempt issued a QR, because that QR may still receive a late payment.
- Amount, currency, concept, merchant, reference and receiver snapshot cannot change after creation: there is no update route and the database rejects such updates.

## Provider webhooks

`POST /webhooks/pey` receives pey events signed with [Standard Webhooks](https://github.com/standard-webhooks/standard-webhooks/blob/main/spec/standard-webhooks.md). It answers `204` only after the event is stored in Postgres; verification and storage happen before any effect on sales (applying events is a later step).

- `TAPPY_PEY_WEBHOOK_SECRET` (`whsec_…`, from the pey portal) is required; without it the endpoint answers `503`.
- The signature is checked over the original bytes (`webhook-id`, `webhook-timestamp`, body) with HMAC-SHA256; any `v1` entry of a space-separated `webhook-signature` list may match (secret rotation). Timestamps outside `TAPPY_WEBHOOK_TOLERANCE_SECONDS` (default 300) are rejected. Invalid signatures or timestamps answer `401`, bodies over `TAPPY_WEBHOOK_MAX_BODY_BYTES` (default 262144) `413`, signed events whose JSON object lacks a `type` `400` (pey events are flat objects such as `codi.qr.payment_received` with `amount`, `codiQrId`, `transactionId` and `metadata`).
- After storing it, the event is applied right away; if that fails it stays `received` and `uv run python -m tappy.sales process-events` applies it later. A `codi.qr.payment_received` event confirms a payment only when everything matches the attempt: the QR id (`codiQrId`), the attempt id in `metadata.tappy_attempt_id` (if present), the receiving account (`bankAccountId`, which must be the account the QR was issued for), the exact amount in pesos (no rounding) and a `transactionId`. Then, in one transaction, the transfer is recorded, the attempt becomes `paid` and the sale `paid`; `GET /sales/{id}` shows `confirmed_amount_cents` and `transfers` (provider transaction id, amount, payment date, reception time and the verified beneficiary and masked account). Recorded transfers cannot be changed.
- Doubtful evidence never covers a sale; it opens a payment exception (`payment_exceptions`) and marks the event `review`:
  - `amount_mismatch`: money reached the merchant's account for this QR but the amount differs. The real transfer is kept (it counts in `confirmed_amount_cents`), the sale becomes `review` and accepts no new attempts.
  - `double_reception`: another distinct verified transfer of the merchant's own account arrives for a sale that already received money (the same QR paid twice, an old expired QR paid after a retry, or the exact amount after a short one). The transfer is kept and counts in `confirmed_amount_cents` (two transfers of 300.00 show 600.00), an attempt paid with the exact amount becomes `paid`, and the sale becomes `review` with `covered: true`.
  - `receiver_mismatch` (another or no `bankAccountId`), `incomplete_evidence` (no transaction id or amount, or a payment date that is present but invalid), `conflicting_transfer` (a transaction id already recorded with other data) and `sale_not_open` (an attempt that can no longer receive money): nothing is added to the merchant.
  - `unassociated`: the QR or attempt cannot be identified with certainty; no sale is touched and nothing is associated by approximation.
  `GET /sales/{id}` lists the sale's exceptions; `uv run python -m tappy.sales exceptions` lists all open ones. Reprocessing an event never opens the same exception twice. Events that are not payment evidence stay `unmatched`.
- Events may arrive before the QR creation response is stored. An event whose `metadata.tappy_attempt_id` names an attempt of the same provider that has no QR id yet (still `creating`, or `reconciling` after an uncertain creation) adopts its `codiQrId` and is applied normally; an attempt that already has another QR id (or that `failed` or `expired`) is never re-associated, and a creation response whose QR id differs from the adopted one leaves the attempt for reconciliation (`duplicate_provider_id`). An event without that metadata stays `unassociated` until the QR id is recorded; recording it applies the waiting events and resolves their `unassociated` exceptions, also when both happen at the same time. Attempt statuses follow one transition table (`tappy.sales.transitions`, the allowed exits of the architecture's attempt states; `failed` → `paid` is left to late-payment handling with an exception): a late creation response, rejection or timeout never moves a `paid` attempt back, and an attempt request whose payment arrived first answers `201` with the attempt `paid`.
- The raw body, its SHA-256 digest, the event id and type and the signed timestamp are stored in `webhook_events`, unique per provider, environment (`TAPPY_ENVIRONMENT`) and `webhook-id`. A repeated delivery with the same content is acknowledged without a second record or effect. A delivery with an id already stored but **different content** is also acknowledged, but the original is kept untouched and the variant is stored in `webhook_event_conflicts` for review (`uv run python -m tappy.sales event-conflicts`).
- Another event for a transfer that is already recorded (same provider, environment and `transactionId`) is marked `duplicate`: the transfer is counted once, also when events and other evidence for it are processed at the same time. If storage is unavailable the answer is `503`, so the provider retries.
- When a notification is missing, `uv run python -m tappy.sales reconcile <attempt-id>` asks the configured provider for the payments of that attempt's QR (pey `GET /transaction/codi/qr/{id}`, following `nextToken` for at most 10 pages of 20) and applies each `PAID` transaction through the same confirmation as webhooks. pey's answer carries no `bankAccountId`, so the receiving account is the one the QR was issued for, and the QR id must be the attempt's own. A transfer already recorded by a webhook (or by an earlier reconciliation) is a `duplicate` and is never counted twice. No transactions, only `PENDING` ones, a 404, a rate limit, a server error, a timeout or an unbounded number of pages never fail or expire the attempt: the payment stays unconfirmed and the command says why. A confirmation closes the attempt's pending reconciliation jobs. Attempts without a QR id cannot be queried by id. The simulated provider never reports payments.
- `uv run python -m tappy.sales run-jobs` runs one batch and is meant to be scheduled (for example every minute with cron); there is no external queue. A batch applies up to `TAPPY_JOB_BATCH_SIZE` stored webhook events still `received` (an event persisted before a crash is applied by the next batch), moves `creating` attempts older than `TAPPY_ATTEMPT_CREATION_TIMEOUT_SECONDS` to reconciliation, and claims up to `TAPPY_JOB_BATCH_SIZE` (default 20) due reconciliation jobs with a lease of `TAPPY_JOB_LEASE_SECONDS` (default 600; with pey it must exceed 40 times `TAPPY_PEY_TIMEOUT_SECONDS`, the longest bounded query). Claims use `FOR UPDATE SKIP LOCKED` and a lease owner: while a lease is live no other runner takes the job, and a runner whose lease expired can no longer finish or reschedule it. Every claim counts as a try. A confirmed or reviewed job is `done`, and every batch also closes the jobs of attempts already paid by a webhook. An attempt without a QR id (an interrupted creation) cannot be queried by id, so its job becomes `exhausted` at once for an operator; a later webhook can still confirm it. Any other result (no evidence, provider problem) is rescheduled after `TAPPY_JOB_BACKOFF_SECONDS` doubled per try up to `TAPPY_JOB_BACKOFF_MAX_SECONDS` (defaults 60 and 3600), or later when pey answers `429` with a `Retry-After` in seconds (bounded to one day). After `TAPPY_JOB_MAX_TRIES` (default 8), including claims whose runner crashed, the job becomes `exhausted` and is no longer retried; the payment stays unconfirmed for an operator. `uv run python -m tappy.sales reconciliations` lists pending and exhausted jobs with tries, lease and last problem. Leases are compared with the runner's clock, so runner hosts must keep their clocks synchronized. Money is never counted twice because every path goes through the same deduplicated confirmation.

## Back office

Starlette Admin is mounted at `/admin`. Only active administrators can sign in; operators and anonymous visitors are sent back to the login page. The panel reuses the API session model: signing in creates the same revocable session as `POST /auth/login`, expired access is renewed with the stored refresh token, and the logout button revokes the session.

- The browser session lives in the `tappy_admin_session` cookie: `HttpOnly`, `SameSite=Strict`, and `Secure` unless `TAPPY_ADMIN_SECURE_COOKIES=false` (only for local HTTP development).
- Every mutating request (sign-in and sign-out included) needs the signed CSRF token rendered in the form; requests without it get `403`. Starlette Admin marks its CSRF cookie `Secure` when the request scheme is HTTPS, so behind a TLS-terminating proxy run Uvicorn with forwarded headers (`--proxy-headers` and `--forwarded-allow-ips`).
- Replaying an old panel cookie whose refresh token was already rotated revokes the whole session, exactly like the API.
- **Operators** page (`/admin/operators`): create an operator with an initial password that the administrator delivers in person (never emailed, never shown again) and deactivate operators; deactivation revokes their sessions immediately. There is no generic CRUD over identities.
- **Sales** pages (`/admin/sales`, `/admin/sales/{id}`): read-only. The list uses the same authorized, keyset-paginated history as `GET /sales` (filters `status`, `merchant_id`, `created_from`, `created_to`, `limit` up to 50, and a *Next page* link carrying the cursor until every sale is shown); invalid filters answer `400` and an unknown merchant or sale `404`. The detail shows the sale with its attempts (status, QR id, expiry, previous attempt), transfers (amount, payment and reception times, masked account) and exceptions. Amounts are shown in pesos from integer centavos. There is no route to create, edit, delete or mark a sale received: other methods answer `405` or `404` and nothing changes. Like `GET /sales/{id}`, opening a detail applies server-side expiry to overdue `pending` attempts; it never touches money or reception. Filters are passed in the URL; the list does not name the merchant yet.
- **Incidents** pages (`/admin/exceptions`, `/admin/exceptions/{id}`) list open incidents and let an administrator add follow-up notes and request a reconciliation. The same use cases are exposed to administrators by the API: `GET /exceptions/{id}`, `POST /exceptions/{id}/notes` (`{"text"}`, 1–1000 characters) and `POST /exceptions/{id}/reconciliation` (`202`). Notes are stored in `exception_notes` with author and time. A reconciliation request reuses the job runner: one `review_requested` job per attempt (the attempt of the incident's transfer, or the sale's latest QR attempt); repeating it while pending is `already_pending`, and a finished or exhausted job is re-armed (`rearmed`, tries reset). Every request is also written as a note. Incidents without a sale can only be noted (`409`). Neither action changes money, resolves the incident or marks a sale received; operators get `403` from the API and are sent to the login page by the panel, and panel forms need the CSRF token.
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
