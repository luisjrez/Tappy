# Evidencia — B02 Levantar Postgres y aplicar primera migración

Ticket: [#10](https://github.com/luisjrez/Tappy/issues/10) · Historia: [H1 #1](https://github.com/luisjrez/Tappy/issues/1) · Protocolo: [TICKET_QUALITY_PROTOCOL](../planning/TICKET_QUALITY_PROTOCOL.md) · Plantilla: [EVIDENCE_COMPARISON_TEMPLATE](../planning/EVIDENCE_COMPARISON_TEMPLATE.md)

## Revisiones y escenario

- Ticket, UC/AC/TC y comprobación: B02-UC01–UC03, B02-AC01–AC03, B02-TC01–TC03, B02-VC01.
- Modalidad: **resultado inicial** para `GET /ready`, Compose y migraciones (superficies nuevas). `GET /health` (B01) no cambia de contrato: su regresión se cubre con los tests de B01, que siguen en verde.
- Aplicabilidad: API sí (`/ready`); comandos sí (Compose, Alembic, psql); panel **no aplica** (sin vistas).
- Base: rama B01 `a59c02c` (PR #51). Revisión evaluada: commit candidato de B02 (SHA en el PR y en la tabla de review).
- Entorno: macOS (Darwin 25.6), Colima + Docker Compose 5.0.2, `postgres:18.6-alpine`, Python 3.14.8, SQLAlchemy 2.1.9, Alembic 1.20.1, psycopg 3.3.9, resto como B01. Fecha: 2026-11-20. Ejecutor: sesión local de desarrollo del autor del PR.
- Actor: Desarrollador. Datos: contraseñas y filas sintéticas (`synthetic-…`).

## Diseño

- `apps/backend/compose.yaml`: `db` (volumen `db-data`, healthcheck `pg_isready`, solo `127.0.0.1`) y `test-db` (servidor separado en `tmpfs`). Contraseñas obligatorias desde `.env`, sin valores en el repo.
- `TAPPY_DATABASE_URL` es `SecretStr`: la URL con contraseña no se imprime en errores de configuración.
- `Database` por instancia de app: engine con `pool_pre_ping` y `connect_timeout=2`; `transaction()` abre una sesión y una transacción por uso; `dispose()` en el `lifespan`.
- `SessionDependency`: una sesión transaccional por petición (commit al terminar, rollback ante excepción).
- Alembic empaquetado como `tappy:migrations`; `0001_baseline` es la primera revisión. `/ready` = Postgres alcanzable **y** esquema en head; si no, `503 {"status":"unavailable"}` sin detalles.
- Tests: cada test que necesita DB crea y borra su propia base `tappy_test_<uuid>` en `test-db`; el `conftest` aborta si `TAPPY_TEST_DATABASE_URL` apunta al mismo host:puerto que `TAPPY_DATABASE_URL`.

## Trazabilidad UC → AC → TC → test

| UC | AC | TC | Test real | Resultado |
| --- | --- | --- | --- | --- |
| B02-UC01 | B02-AC01 | B02-TC01 | `tests/test_readiness.py::test_readiness_turns_ready_after_migrating_an_empty_database` (base vacía: 503 → `upgrade head` → 200) | PASS |
| B02-UC02 | B02-AC02 | B02-TC02 | `tests/test_readiness.py::test_readiness_reports_unavailable_database_without_internal_details` (sin contraseña ni nombre de excepción en la respuesta) | PASS |
| B02-UC03 | B02-AC03 | B02-TC03 | `tests/test_persistence.py::test_local_data_survives_database_restart_and_stays_out_of_test_database` (proyecto Compose desechable con volumen: dato + migración sobreviven a `restart`; la base de tests no contiene ni la tabla ni la base local) | PASS |
| Refactor del ticket | — | adicional | `tests/test_sessions.py::test_each_request_uses_its_own_transaction` (sesión distinta por petición; commit en éxito, rollback en error) | PASS |

## TDD

| Comportamiento | Red observado | Green |
| --- | --- | --- |
| Readiness con DB caída | `assert 404 == 503` (sin ruta) | `Database.is_ready()` + `GET /ready` con 503 |
| Readiness tras migrar base vacía | Readiness respondía 200 con base sin migrar: `assert 200 == 503` | Alembic `tappy:migrations`, `0001_baseline`, `is_schema_current` (revisión actual == head) |
| Persistencia tras reinicio | Mutación de control: `db` en `tmpfs` en lugar de volumen → `psql … SELECT label FROM persistence_probe` falla tras `restart` (exit 1). Restaurado el volumen → PASS. (Una mutación con volumen anónimo no detecta nada porque `restart` conserva el contenedor; descartada.) | Volumen `db-data` |
| Sesión transaccional por petición | Stub sin ciclo de transacción: `assert [] == ['accepted']` | `Database.transaction()` (`session.begin()`) y `get_session` |

Refactor: ciclo de sesión/transacción centralizado en `Database.transaction()`; ninguna sesión se comparte entre peticiones. `free_port` movido a `tests/support.py`.

## Checks

| Comando | Resultado | Código |
| --- | --- | --- |
| `uv run ruff format --check .` | `23 files already formatted` | 0 |
| `uv run ruff check .` | `All checks passed!` | 0 |
| `uv run mypy` | `Success: no issues found in 22 source files` | 0 |
| `uv run pytest` | `10 passed` | 0 |

Exención nueva acotada: `tests/test_persistence.py` → `S603`/`S607` (invoca el CLI `docker compose` con argumentos fijos).

## API — resultado inicial

`GET /ready`, proceso real `python -m tappy` contra `db` de Compose (volumen recién creado):

| Escenario | Status | JSON |
| --- | --- | --- |
| Base vacía sin migrar | 503 | `{"status":"unavailable"}` |
| Tras `alembic upgrade head` | 200 | `{"status":"ready"}` |
| `docker compose stop db` | 503 (`content-type: application/json`, `content-length: 24`) | `{"status":"unavailable"}` |
| Tras volver a arrancar `db` | 200 | `{"status":"ready"}` |

Contrato: `ReadinessStatus {status: "ready" | "unavailable"}`; 503 documentado en OpenAPI. El log del servidor durante la prueba no contiene `password` ni `Traceback` (`grep -ci` = 0).

## Comandos — resultado inicial

```text
$ uv run alembic upgrade head
INFO [alembic.runtime.migration] Running upgrade  -> 0001_baseline
exit=0
$ uv run alembic current
0001_baseline (head)
exit=0
$ docker compose exec -T db psql … "CREATE TABLE vc01_probe …; INSERT … 'synthetic-vc01'"
$ docker compose stop db && docker compose up -d --wait db
$ docker compose exec -T db psql … "SELECT label FROM vc01_probe"
synthetic-vc01
```

La tabla de comprobación se eliminó al terminar.

## Back office

Sin UI afectada.

## Diferencias y decisión

| TC / AC | Diferencia | Clasificación | Motivo | Evidencia | Resolución |
| --- | --- | --- | --- | --- | --- |
| B02-TC01–TC03 | Resultado inicial | No aplica diff | Superficies nuevas | Tests y salidas | Conforme |
| B01 `/health` | Sin cambio de contrato | Sin diferencia | `Settings` exige ahora `TAPPY_DATABASE_URL` (variable nueva obligatoria) | Tests B01 en verde | Esperada |

- Estado VC01: **PASS**. Diferencias inesperadas: ninguna. Nueva base propuesta tras aprobación humana.

## Umbral

AC PASS / AC aplicables = 3/3 = **100%**. Checks 100% verdes; sin defectos conocidos de secretos o integridad.

## Review Standards/Spec

Pendiente de completar con el resultado del review del commit candidato.
