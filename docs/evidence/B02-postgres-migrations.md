# Evidencia — B02 Levantar Postgres y aplicar primera migración

Ticket: [#10](https://github.com/luisjrez/Tappy/issues/10) · Historia: [H1 #1](https://github.com/luisjrez/Tappy/issues/1) · Protocolo: [TICKET_QUALITY_PROTOCOL](../planning/TICKET_QUALITY_PROTOCOL.md) · Plantilla: [EVIDENCE_COMPARISON_TEMPLATE](../planning/EVIDENCE_COMPARISON_TEMPLATE.md)

## Revisiones y escenario

- Ticket, UC/AC/TC y comprobación: B02-UC01–UC03, B02-AC01–AC03, B02-TC01–TC03, B02-VC01.
- Modalidad: **resultado inicial** para `GET /ready`, Compose y migraciones (superficies nuevas). `GET /health` (B01) no cambia de contrato: su regresión se cubre con los tests de B01, que siguen en verde.
- Aplicabilidad: API sí (`/ready`); comandos sí (Compose, Alembic, psql); panel **no aplica** (sin vistas).
- Base: rama B01 `a59c02c` (PR #51). Revisión evaluada: commit candidato `fe3dc49`; código corregido `fa29dba`; código final `ccf8eed` (ajustes de la re-revisión, solo tests). Tests y checks se repitieron sobre `ccf8eed` (11 passed, ruff/mypy verdes); las salidas de API/comandos se capturaron sobre `fa29dba`, sin cambios de código de producción después. Commits posteriores solo modifican este archivo.
- Entorno: macOS (Darwin 25.6), Colima + Docker Compose 5.0.2, `postgres:18.6-alpine`, Python 3.14.8, SQLAlchemy 2.1.9, Alembic 1.20.1, psycopg 3.3.9, resto como B01. Fecha: 2026-11-20. Ejecutor: sesión local de desarrollo del autor del PR.
- Actor: Desarrollador. Datos: contraseñas y filas sintéticas (`synthetic-…`).

## Diseño

- `apps/backend/compose.yaml`: `db` (volumen `db-data`, healthcheck `pg_isready`, solo `127.0.0.1`) y `test-db` (servidor separado en `tmpfs`). Contraseñas obligatorias desde `.env`, sin valores en el repo.
- `TAPPY_DATABASE_URL` es `SecretStr`: la URL con contraseña no se imprime en errores de configuración.
- `Database` por instancia de app: engine con `pool_pre_ping` y `connect_timeout=2`; `transaction()` abre una sesión y una transacción por uso; `dispose()` en el `lifespan`.
- `SessionDependency`: una sesión transaccional por petición (commit al terminar, rollback ante excepción).
- Alembic empaquetado como `tappy:migrations` (helpers en `tappy.platform.schema`, head cacheado); `0001_baseline` es la primera revisión. `/ready` = Postgres alcanzable **y** esquema en head; si no, `503 {"status":"unavailable"}` sin detalles. Interpretación: el Red del ticket pide que «migración sobre base vacía» falle, y una base sin migrar no está lista para servir; por eso readiness exige el esquema en head además de la conexión.
- Tests: cada test que necesita DB crea y borra su propia base `tappy_test_<uuid>` en `test-db`; el `conftest` aborta si `TAPPY_TEST_DATABASE_URL` apunta al mismo host:puerto que `TAPPY_DATABASE_URL`.

## Trazabilidad UC → AC → TC → test

| UC | AC | TC | Test real | Resultado |
| --- | --- | --- | --- | --- |
| B02-UC01 | B02-AC01 | B02-TC01 | `tests/test_readiness.py::test_readiness_turns_ready_after_migrating_an_empty_database` (base vacía: 503 → `upgrade head` → 200) | PASS |
| B02-UC02 | B02-AC02 | B02-TC02 | `tests/test_persistence.py::test_readiness_turns_unavailable_when_local_postgres_stops` (Postgres de Compose en marcha → 200; `docker compose stop db` → 503); `tests/test_readiness.py::test_readiness_reports_unavailable_database_without_internal_details` (servidor inalcanzable: cuerpo exacto `{"status":"unavailable"}`, sin contraseña) | PASS |
| B02-UC03 | B02-AC03 | B02-TC03 | `tests/test_persistence.py::test_local_data_survives_database_recreation_and_stays_out_of_test_server` (proyecto Compose desechable: dato + revisión sobreviven a `down` + `up` gracias al volumen `db-data`; el servidor de tests no contiene la base `tappy`) + guarda del `conftest` que aborta si ambas URLs comparten host:puerto | PASS |
| Refactor del ticket | — | adicional | `tests/test_sessions.py::test_each_request_uses_its_own_transaction` (sesión distinta por petición; commit en éxito, rollback en error) | PASS |

## TDD

| Comportamiento | Red observado | Green |
| --- | --- | --- |
| Readiness con DB caída | `assert 404 == 503` (sin ruta) | `Database.is_ready()` + `GET /ready` con 503 |
| Readiness tras migrar base vacía | Readiness respondía 200 con base sin migrar: `assert 200 == 503` | Alembic `tappy:migrations`, `0001_baseline`, `is_schema_current` (revisión actual == head) |
| Persistencia tras recrear el servicio | Mutaciones de control: `db` en `tmpfs` y `db` con volumen anónimo → `psql … SELECT label FROM persistence_probe` falla tras `down` + `up` (exit 1). Con `restart` la mutación de volumen anónimo no se detectaba (hallazgo de review), por eso el test recrea el contenedor. Restaurado `db-data` → PASS. | Volumen `db-data` |
| Sesión transaccional por petición | Stub sin ciclo de transacción: `assert [] == ['accepted']` | `Database.transaction()` (`session.begin()`) y `get_session` |

Refactor: ciclo de sesión/transacción centralizado en `Database.transaction()`; ninguna sesión se comparte entre peticiones. `free_port` movido a `tests/support.py`.

## Checks

| Comando | Resultado | Código |
| --- | --- | --- |
| `uv run ruff format --check .` | `23 files already formatted` | 0 |
| `uv run ruff check .` | `All checks passed!` | 0 |
| `uv run mypy` | `Success: no issues found in 22 source files` | 0 |
| `uv run pytest` | `11 passed` | 0 |

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

Volumen `tappy_db-data` recién creado; salida resumida (sin líneas de progreso repetidas):

```text
$ docker compose up -d --wait db            → Volume tappy_db-data Created … Container tappy-db-1 Healthy   exit=0
$ curl /ready                               → {"status":"unavailable"} status=503
$ uv run alembic upgrade head               → Running upgrade  -> 0001_baseline                         exit=0
$ uv run alembic current                    → 0001_baseline (head)                                      exit=0
$ curl /ready                               → {"status":"ready"} status=200
$ docker compose exec -T db psql … "CREATE TABLE vc01_probe …; INSERT … 'synthetic-vc01'"  → CREATE TABLE / INSERT 0 1   exit=0
$ docker compose stop db                    → Container tappy-db-1 Stopped                             exit=0
$ curl -i /ready                            → HTTP/1.1 503 · content-type: application/json · {"status":"unavailable"}
$ docker compose down                       → Container tappy-db-1 Removed                             exit=0
$ docker compose up -d --wait db            → Container tappy-db-1 Healthy                             exit=0
$ docker compose exec -T db psql … "SELECT label FROM vc01_probe"                           → synthetic-vc01   exit=0
$ curl /ready                               → {"status":"ready"} status=200
```

La tabla de comprobación se eliminó al terminar. Log del servidor: 0 coincidencias de `password|traceback`.

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

Review sobre `fe3dc49`; correcciones en `fa29dba`.

| Eje | Hallazgo | Resolución |
| --- | --- | --- |
| Standards / Spec | Evidencia sin SHA exacto | SHAs `fe3dc49`/`fa29dba` registrados |
| Spec | Salidas VC01 sin códigos de salida | Recapturadas con `exit=` por comando |
| Spec | TC02 no detenía un Postgres real | Test automatizado con `docker compose stop db` |
| Spec | TC03 no distinguía volumen con nombre de anónimo (`restart`) | Test recrea el contenedor (`down` + `up`); mutación de volumen anónimo ahora falla |
| Spec | Aserción de aislamiento que no podía fallar (`persistence_probe` en base nueva) | Eliminada; se conserva «sin base `tappy` en el servidor de tests» y la guarda del `conftest` |
| Spec | `/ready` también exige esquema en head | Se conserva; interpretación documentada en Diseño |
| Standards | Literales duplicados de constantes en tests | Usan `UNREACHABLE_DATABASE_PASSWORD`/`PROBE_DATUM` (inserción con parámetro ligado) |
| Standards | `tappy.migrations` vs `tappy.platform.migrations` ambiguos | Helpers renombrados a `tappy.platform.schema` |
| Standards (fuera de eje) | Head releído en cada `/ready`; `dispose` sin `try/finally` | `head_revision` cacheado; `try/finally` en `lifespan` y `env.py` |
| Standards | URL como `str` en helpers de Alembic; `Base` vacío; patrón repetido `get_settings`/`get_database` | Aceptados: frontera de la API de Alembic; `Base` es el destino de metadata de Alembic; dos copias toleradas |

Re-revisión sobre `69fcb2d`: checks verdes, sin hallazgos bloqueantes. No bloqueantes resueltos en `ccf8eed`: TC02 con Postgres detenido ahora afirma el cuerpo exacto `{"status":"unavailable"}`; la guarda del `conftest` trata `localhost`/`127.0.0.1`/`::1` como el mismo servidor (verificado: `TAPPY_TEST_DATABASE_URL=…@localhost:5482` aborta la suite). Aceptado: `free_port()` puede competir por el puerto con otro proceso local (riesgo bajo). Sin hallazgos pendientes.
