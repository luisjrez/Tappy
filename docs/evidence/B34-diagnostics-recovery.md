# Evidencia — B34 Diagnosticar y restaurar operación

Ticket: [#42](https://github.com/luisjrez/Tappy/issues/42) · Historia: [H7 #7](https://github.com/luisjrez/Tappy/issues/7) · Protocolo: [TICKET_QUALITY_PROTOCOL](../planning/TICKET_QUALITY_PROTOCOL.md) · Manifiesto: [B34-diagnostics-recovery.toml](B34-diagnostics-recovery.toml)

> Verificado con datos sintéticos, en proyectos Compose desechables y con un proceso real cuya base está caída a propósito. **No se usó la base de desarrollo ni una productiva para restaurar, ni hubo llamadas a pey.**

## Revisiones y escenario

- **Trazabilidad:** B34-UC01–UC03, B34-AC01–AC03 y B34-VC01. Superficie: respuestas HTTP, logs y comandos.
- **Modalidad:**
  - antes/después en las respuestas y los logs;
  - resultado inicial en los comandos: `backlog` y el procedimiento de respaldo son nuevos.
- **Cambios esperados en tests anteriores:**
  - `ComposeProject` pasa de `tests/test_persistence.py` a `tests/compose_support.py`, con su fixture en `conftest.py`;
  - la exención de lint `S603`/`S607` se mueve con él;
  - no cambia ninguna aserción.
- **Base y revisiones:**
  - Base: rama B33 `9133879` ([PR #107](https://github.com/luisjrez/Tappy/pull/107)), stack #68.
  - Candidato: `c23d9bb`.
- **Entorno:** macOS, Colima + Compose (Postgres 18.6 en los contenedores; `pg_dump` y `pg_restore` se ejecutan dentro del contenedor, con la misma versión que el servidor) y Python 3.14.8. Fecha: 2026-11-25 (UTC). Ejecutor: sesión local de desarrollo del autor del PR.

## Diseño

### Referencia correlacionable (`tappy.platform.diagnostics`)

- **`RequestReference`** es un middleware ASGI.
  - Toda respuesta HTTP lleva `X-Request-ID`. Se acepta la del cliente si cumple `[A-Za-z0-9_-]{8,64}`; si no, se genera una de 32 caracteres hexadecimales.
  - La referencia vive en un `ContextVar`, así que también llega a los endpoints que corren en el pool de hilos.
- **Error inesperado:**
  - El cliente recibe `500` con `{"detail": "Internal server error", "reference": …}`; nunca recibe el mensaje interno.
  - Se registra `Unhandled error in <método> <plantilla de ruta>` (por ejemplo `/sales/{sale_id}/attempts`, sin IDs) con su traza y bajo la misma referencia.
  - Los errores esperados conservan su código y su `detail`.
- **`configure_logging`:**
  - El servidor (`python -m tappy`) y `python -m tappy.sales` escriben a stderr con el formato `hora nivel logger [referencia] mensaje`.
  - El handler es idempotente.

### Redacción unificada (`tappy.platform.redaction`)

`RedactingFilter` redacta tanto el mensaje ya formateado como la traza (`exc_text`), y lo hace en todas las líneas:

- **Secretos configurados:** `TAPPY_SECRET_KEY`, `TAPPY_PEY_API_KEY`, `TAPPY_PEY_WEBHOOK_SECRET` y la contraseña de la base → `[redacted]`.
- **Credenciales en texto:** `Bearer …` y `whsec_…` → `[redacted]`.
- **Datos personales y bancarios:**
  - CLABE de 18 dígitos → `**************6789`;
  - teléfono de 10 dígitos → `******5678`;
  - correo → `[email]`.

### Indicadores de atraso (`tappy.sales.backlog`, comando `backlog`)

El comando muestra:

- eventos `received` sin aplicar;
- trabajos reclamables ahora;
- trabajos con arriendo, y cuántos de esos arriendos ya vencieron (un ejecutor que murió);
- trabajos agotados;
- intentos en `creating` que superan `TAPPY_ATTEMPT_CREATION_TIMEOUT_SECONDS`;
- incidencias abiertas.

Cada indicador con algo pendiente muestra, en segundos, cuánto lleva esperando el elemento más antiguo.

Además, cada trabajo que procesa `run-jobs` registra `Reconciliation job <id> for sale <referencia> (attempt <id>): <resultado>`. Así una referencia de venta se puede seguir con `reconciliations`, `run-jobs` y `backlog`.

### Respaldo y restauración (README «Backup and restore»)

```sh
docker compose exec -T db pg_dump --format=custom --no-owner -U tappy -d tappy > tappy.dump
docker compose exec -T db createdb -U tappy tappy_restored
docker compose exec -T db pg_restore --no-owner --exit-on-error -U tappy -d tappy_restored < tappy.dump
```

- **Siempre a una base nueva:** `createdb` rechaza un nombre que ya existe, así que la restauración nunca sobrescribe la base en uso.
- **Comprobación tras restaurar:** `GET /ready`, después `backlog` y `reconciliations`, y por último `run-jobs` para reanudar.
- **Pruebas:** los tests ejecutan exactamente estos comandos contra un proyecto Compose desechable, con nombre y puerto propios.

### Arrastre B17/B18: payloads de webhooks

Decisión registrada en el README:

- Los cuerpos guardados en `webhook_events` y `webhook_event_conflicts` son evidencia de la recepción.
- Nunca se escriben en logs ni se devuelven por la API o el back office; el back office no tiene una vista de eventos.
- Solo se leen con acceso directo a la base.
- Los comandos diagnostican con id, digest, tipo y estado.
- Los respaldos contienen esos cuerpos y se tratan como datos sensibles.
- **Pendiente:** el plazo de retención y cuándo purgar o minimizar es una decisión de producto todavía abierta (arquitectura §11). Mientras tanto se conservan y B34 no purga nada.

## Trazabilidad UC → AC → TC → test

| UC | AC | TC | Test real | Resultado |
| --- | --- | --- | --- | --- |
| B34-UC01 | B34-AC01 | B34-TC01 | `tests/test_diagnostics.py::test_an_unexpected_error_answers_a_reference_and_logs_it_without_sensitive_data`: un proveedor sintético lanza un error con token, CLABE, teléfono y correo. Resultado: `500` con la referencia; el log tiene la referencia y la plantilla de ruta, sin ninguno de los cuatro valores; la respuesta tampoco los contiene. Además `…::test_configured_secrets_never_reach_a_log_line`, `…::test_a_safe_caller_reference_is_kept_and_an_unsafe_one_replaced` y `…::test_every_error_response_carries_its_reference` (`404`, `401`, `422`) | PASS |
| B34-UC02 | B34-AC02 | B34-TC02 | `tests/test_backup_restore.py::test_a_backup_restores_into_a_new_database_with_the_sale_and_its_pending_job`: `pg_dump`, después `createdb` y `pg_restore` en `tappy_restored`; `/ready` da `200`; la misma venta y el trabajo `pending` aparecen en `reconciliations` y `backlog`; el origen no cambia. Además `…::test_the_restore_refuses_to_overwrite_an_existing_database` | PASS |
| B34-UC03 | B34-AC03 | B34-TC03 | `tests/test_backup_restore.py::test_a_runner_interrupted_after_the_restore_finishes_the_job_once_and_can_be_followed`: tras restaurar, un ejecutor reclama y muere; `backlog` muestra el arriendo vencido. El primer `run-jobs` reclama 1 y lo verifica, y el log nombra la venta; el segundo no reclama nada. El trabajo termina `done` con 2 intentos y el `backlog` final queda vacío | PASS |

## TDD

**Red:** los tests se escribieron antes del código.

- **Respaldo**, sobre la base `9133879`: fallan 2 de 3. La restauración ya funcionaba con las herramientas de Postgres; lo que faltaba era el comando `backlog`, y la búsqueda de su línea en la salida da `StopIteration`. `…refuses_to_overwrite…` pasa desde el principio y se conserva como caracterización del procedimiento.
- **Diagnóstico**, sobre `9133879` con un stub de `configure_logging` que no redacta: fallan los 4.

```
FAILED tests/test_backup_restore.py::test_a_backup_restores_into_a_new_database_with_the_sale_and_its_pending_job
FAILED tests/test_backup_restore.py::test_a_runner_interrupted_after_the_restore_finishes_the_job_once_and_can_be_followed
2 failed, 1 passed in 14.46s
FAILED tests/test_diagnostics.py::test_an_unexpected_error_answers_a_reference_and_logs_it_without_sensitive_data
FAILED tests/test_diagnostics.py::test_configured_secrets_never_reach_a_log_line
FAILED tests/test_diagnostics.py::test_a_safe_caller_reference_is_kept_and_an_unsafe_one_replaced
FAILED tests/test_diagnostics.py::test_every_error_response_carries_its_reference
4 failed in 1.78s
```

Motivo de cada fallo (`--tb=line`):

| Test | Motivo en `9133879` |
| --- | --- |
| Error inesperado | La excepción llega sin capturar al cliente de pruebas (sin `500` con referencia) y su mensaje incluye los valores sensibles sin redactar |
| Secretos configurados | `assert 'pey call with key [redacted] …' in 'pey call with key pey-synthetic-api-key-0001 …'` |
| Referencia del cliente y referencia en errores | `KeyError: 'X-Request-ID'` |
| Respaldo y reanudación | `StopIteration`: no existe el comando `backlog` |

**Mutaciones** sobre el candidato, con `tests/test_diagnostics.py` y `tests/test_backup_restore.py`. Cada una se revierte. Debajo de cada mutación se listan los tests que fallan:

```
M1 mensaje sin redactar: 1 failed, 6 passed in 16.09s
    test_configured_secrets_never_reach_a_log_line
M2 traza sin redactar: 1 failed, 6 passed in 16.27s
    test_an_unexpected_error_answers_a_reference_and_logs_it_without_sensitive_data
M3 CLABE sin enmascarar: 1 failed, 6 passed in 16.44s
    test_an_unexpected_error_answers_a_reference_and_logs_it_without_sensitive_data
M4 telefono sin enmascarar: 1 failed, 6 passed in 16.41s
    test_an_unexpected_error_answers_a_reference_and_logs_it_without_sensitive_data
M5 sin secretos configurados: 1 failed, 6 passed in 16.27s
    test_configured_secrets_never_reach_a_log_line
M6 error 500 sin referencia: 1 failed, 6 passed in 16.34s
    test_an_unexpected_error_answers_a_reference_and_logs_it_without_sensitive_data
M7 referencia del cliente sin validar: 1 failed, 6 passed in 16.08s
    test_a_safe_caller_reference_is_kept_and_an_unsafe_one_replaced
M8 ejecutor sin log de referencia: 1 failed, 6 passed in 16.26s
    test_a_runner_interrupted_after_the_restore_finishes_the_job_once_and_can_be_followed
M9 backlog sin arriendos vencidos: 1 failed, 6 passed in 16.92s
    test_a_runner_interrupted_after_the_restore_finishes_the_job_once_and_can_be_followed
```

## Aplicabilidad por superficie

| Superficie | Aplica | Justificación |
| --- | --- | --- |
| API | Sí | `X-Request-ID` en toda respuesta y `500` con referencia. Los contratos existentes no cambian (15 contratos sin diferencias) |
| Logs | Sí | Formato con referencia y redacción |
| Comandos | Sí | `backlog` nuevo, log por trabajo en `run-jobs` y procedimiento de respaldo |
| Panel | No aplica | El back office no cambia |

## B34-VC01 — respuestas, logs y comandos

### A. Respuestas y logs, antes/después

- **Proceso:** `python -m tappy` real con `TAPPY_DATABASE_URL` apuntando a un puerto cerrado (`127.0.0.1:59999`), así que la base está caída a propósito.
- **Datos de la petición, todos sintéticos:**
  - una contraseña que contiene un teléfono;
  - un `Bearer` y una CLABE en el cuerpo;
  - la contraseña de la base va en la URL de configuración.
- **Revisiones:** mismo script en `9133879` (antes) y en `c23d9bb` (después).

#### Antes (`9133879`)

- POST /auth/login con la base caída → 500 · X-Request-ID: `—` · `Internal Server Error`
- PUT /merchants/{id}/receiver con Bearer y CLABE, base caída → sin respuesta: `ReadError: [Errno 54] Connection reset by peer`
- GET /health con X-Request-ID del cliente → 200 · X-Request-ID: `—` · `{"status": "ok", "environment": "vc01"}`

Log: uvicorn registra `Exception in ASGI application` con la traza de `OperationalError`, sin ninguna referencia que la relacione con la respuesta. El cliente no tiene con qué reportar el error.

#### Después (`c23d9bb`)

- POST /auth/login con la base caída → 500 · X-Request-ID: `9b518d1bf6654e18a7b5409102bd3d98` · `{"detail": "Internal server error", "reference": "9b518d1bf6654e18a7b5409102bd3d98"}`
- PUT /merchants/{id}/receiver con Bearer y CLABE, base caída → 500 · X-Request-ID: `92dda5caf13c44fb8d1ca79d07a37aad` · `{"detail": "Internal server error", "reference": "92dda5caf13c44fb8d1ca79d07a37aad"}`
- GET /health con X-Request-ID del cliente → 200 · X-Request-ID: `vc01-caller-ref` · `{"status": "ok", "environment": "vc01"}`

Líneas de error del log, ligadas a cada respuesta por su referencia:

```
ERROR tappy.platform.diagnostics [9b518d1bf6654e18a7b5409102bd3d98] Unhandled error in POST /auth/login
ERROR tappy.platform.diagnostics [92dda5caf13c44fb8d1ca79d07a37aad] Unhandled error in PUT /merchants/{merchant_id}/receiver
sqlalchemy.exc.OperationalError: (psycopg.OperationalError) connection failed: connection to server at "127.0.0.1", port 59999 failed: could not receive data from server: Connection refused
```

**Valores sensibles en el log** (token, CLABE, teléfono, contraseña de la base, secreto): 0 apariciones de cada uno, tanto antes como después. En este escenario los errores de psycopg no incluyen parámetros (`hide_parameters=True`), así que la redacción no tuvo nada que tapar. Que redacta de verdad lo prueban TC01 y las mutaciones M1–M5, con un error cuyo mensaje sí contiene los datos.

### B. Comandos de respaldo, restauración y reanudación (resultado inicial)

- **Antes:** el comando no existía.

  ```
  python -m tappy.sales: error: argument command: invalid choice: 'backlog' (choose from 'reconciliations', 'recover-interrupted', 'process-events', 'event-conflicts', 'exceptions', 'run-jobs', 'reconcile')
  ```

- **Después:** script con los mismos comandos del README, sobre un proyecto Compose desechable que se destruye al terminar:

- Proyecto Compose desechable `tappy-persistence-6c8f2013c4f5` en el puerto 53250; venta sintética `6GKF5KZDHZ` con su intento expirado y un trabajo pendiente.
- `pg_dump --format=custom` → 47773 bytes.
- Restaurar sobre `tappy` (la base en uso) → rechazado por `createdb` (exit 1): `createdb: error: database creation failed: ERROR:  database "tappy" already exists`
- Restaurar en `tappy_restored` → OK; `GET /ready` = 200.
- Venta restaurada: `6GKF5KZDHZ open`; trabajo: `expired pending`.

#### `backlog (recién restaurada)` (exit 0)

```
received webhook events: 0
due reconciliation jobs: 1 (oldest due 3600 s ago)
leased reconciliation jobs: 0 (0 with an expired lease)
exhausted reconciliation jobs: 0
attempts creating longer than 60 s: 0
open payment exceptions: 0
```

#### `reconciliations` (exit 0)

```
attempt: dd5b7d69-7d42-4747-83d3-e3015b34341d
sale reference: 6GKF5KZDHZ
attempt status: expired
reason: expired
status: pending
run at: 2026-11-25T21:53:30.236609+00:00
tries: 0
leased until: not leased
last problem: none
```

- Un ejecutor reclama 1 trabajo y muere sin terminarlo; su arriendo ya venció.

#### `backlog (ejecutor interrumpido)` (exit 0)

```
received webhook events: 0
due reconciliation jobs: 1 (oldest due 3601 s ago)
leased reconciliation jobs: 1 (1 with an expired lease)
exhausted reconciliation jobs: 0
attempts creating longer than 60 s: 0
open payment exceptions: 0
```

#### `run-jobs (reanuda)` (exit 0)

```
events: 0 events applied, 0 unmatched, 0 in review, 0 duplicates, 0 failed
jobs of paid attempts closed: 0
pending attempts expired: 0
interrupted attempts moved to reconciliation: 0
jobs claimed: 1
confirmed: 0, verified unpaid: 1, in review: 0, rescheduled: 0, exhausted: 0, lease lost: 0, failed: 0
--- stderr ---
INFO tappy.sales.jobs [-] Reconciliation job cd6d5727-7e84-47f2-97d7-5015af44ec56 for sale 6GKF5KZDHZ (attempt dd5b7d69-7d42-4747-83d3-e3015b34341d): verified
```

#### `run-jobs (otra vez)` (exit 0)

```
events: 0 events applied, 0 unmatched, 0 in review, 0 duplicates, 0 failed
jobs of paid attempts closed: 0
pending attempts expired: 0
interrupted attempts moved to reconciliation: 0
jobs claimed: 0
confirmed: 0, verified unpaid: 0, in review: 0, rescheduled: 0, exhausted: 0, lease lost: 0, failed: 0
```

#### `backlog (al final)` (exit 0)

```
received webhook events: 0
due reconciliation jobs: 0
leased reconciliation jobs: 0 (0 with an expired lease)
exhausted reconciliation jobs: 0
attempts creating longer than 60 s: 0
open payment exceptions: 0
```

- Trabajo: `done 2`; intento verificado: `True`; base de origen sin cambios: trabajo `pending`.

**Validación:**

- **TC01:**
  - cada `500` trae su referencia en el cuerpo y en `X-Request-ID`, y la misma referencia encabeza su línea de log, con la plantilla de ruta y sin IDs;
  - una referencia válida del cliente se respeta;
  - no hay valores sensibles ni en la respuesta ni en el log;
  - antes no había referencia y la conexión se cortaba en la siguiente petición.
- **TC02:**
  - la restauración en `tappy_restored` queda lista (`/ready` 200), con la venta y su trabajo pendiente visibles en `backlog` y `reconciliations`;
  - restaurar sobre la base en uso se rechaza;
  - el origen no cambia.
- **TC03:**
  - el arriendo vencido de un ejecutor interrumpido aparece en `backlog`;
  - `run-jobs` lo completa una sola vez y el log nombra la venta `6GKF5KZDHZ`;
  - la segunda ejecución no reclama nada y el `backlog` final queda vacío.

Estado VC01: **PASS**.

## Checks

`uv run python -m quality.check` sobre `c23d9bb`, con `.env` exportado: PASS en todos los pasos.

- format, lint, types (mypy strict) y hygiene;
- migrations: sin migraciones nuevas, solo upgrade/downgrade/upgrade + `alembic check`;
- tests: 583 passed, con Postgres real aislado y proyectos Compose desechables;
- api: 15 contratos sin diferencias;
- evidence: B01–B33 APPROVED.

## Supresiones

Ninguna nueva: la exención existente `S603`/`S607` se mueve con `ComposeProject` a `tests/compose_support.py`.

## Umbral

AC PASS / AC aplicables = 3/3 = **100%**.

## Review Standards/Spec

| Ronda | Revisión | Standards | Spec | Hallazgos |
| --- | --- | --- | --- | --- |
| 1 | `c23d9bb` | PENDING | PENDING | — |
