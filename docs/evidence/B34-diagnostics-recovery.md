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
  - Candidato de la ronda 1: `c23d9bb`.
  - Candidato de la ronda 2: `842a4e8` (correcciones de la ronda 1 en `caf9960` y `842a4e8`).
  - Candidato de la ronda 3: `a37fc63` (sugerencias no bloqueantes de la ronda 2).
  - Candidato de la ronda 4: `bcdb773` (aviso de secretos cortos, sugerido por las dos revisiones de la ronda 3).
- **Entorno:** macOS, Colima + Compose (Postgres 18.6 en los contenedores; `pg_dump` y `pg_restore` se ejecutan dentro del contenedor, con la misma versión que el servidor) y Python 3.14.8. Fecha: 2026-11-25 (UTC). Ejecutor: sesión local de desarrollo del autor del PR.

## Diseño

### Referencia correlacionable (`tappy.platform.diagnostics`)

- **`RequestReference`** es un middleware ASGI.
  - Toda respuesta HTTP lleva `X-Request-ID`. Se acepta la del cliente si cumple `[A-Za-z0-9_-]{8,64}` y no es solo de dígitos (si no, la redacción podría enmascararla en el log como teléfono o CLABE); si no, se genera una de 32 caracteres hexadecimales.
  - La referencia vive en un `ContextVar`, así que también llega a los endpoints que corren en el pool de hilos.
- **Error inesperado:**
  - El cliente recibe `500` con `{"detail": "Internal server error", "reference": …}`; nunca recibe el mensaje interno.
  - Se registra `Unhandled error in <método> <plantilla de ruta>` (por ejemplo `/sales/{sale_id}/attempts`, sin IDs) con su traza y bajo la misma referencia.
  - Los errores esperados conservan su código y su `detail`.
- **`configure_logging`:**
  - El servidor (`python -m tappy`, incluidas las líneas propias de Uvicorn: arranque y acceso), `python -m tappy.sales` y `python -m tappy.identity` escriben a stderr con el formato `hora nivel logger [referencia] mensaje`.
  - Uvicorn arranca con `log_config=None`: su configuración por defecto pone `propagate=False` en sus loggers y saltaría la redacción.
  - Las líneas de acceso se escriben dentro de la petición, así que llevan la misma referencia que la respuesta.
  - El handler es idempotente.
- **Comandos:** un error inesperado en `tappy.sales` o `tappy.identity` registra `Command <nombre> failed` con la traza redactada y sale con `1`, en lugar de una traza de Python sin formato.

### Redacción unificada (`tappy.platform.redaction`)

`RedactingFormatter` redacta la línea ya formateada completa (mensaje y traza). No modifica el `LogRecord`, así que otros handlers no se ven afectados. `ReferenceFilter` solo añade la referencia.

- **Secretos configurados:** `TAPPY_SECRET_KEY`, `TAPPY_PEY_API_KEY`, `TAPPY_PEY_WEBHOOK_SECRET` (con y sin el prefijo `whsec_`) y la contraseña de la base → `[redacted]`, del más largo al más corto, para que uno contenido en otro no deje partes del mayor. Los de menos de 8 caracteres no se reemplazan: no se distinguen de palabras normales (una contraseña `tappy` borraría `tappy.sales.cli` y además revelaría cuál es). Al configurar el logging se avisa una vez qué ajuste es demasiado corto, sin su valor (`The database password is shorter than 8 characters, so logs cannot redact it`). El README pide secretos más largos.
- **Credenciales en texto:** `Bearer …` y `whsec_…` → `[redacted]`.
- **Datos personales y bancarios:**
  - CLABE de 18 dígitos, también agrupada `3 3 11 1` o `4 4 4 4 2` → `**************6789`;
  - teléfono mexicano de 10 dígitos, también agrupado `2 4 4` o `3 3 4` con espacios, puntos o guiones, con la lada entre paréntesis (`(55) 1234 5678`) y con `52`, `+52` o `+52 1` → `******5678` (más asteriscos por cada dígito del prefijo);
  - las dos reglas aceptan la forma codificada en URL de una ruta registrada (`%2B52…`, `%20` entre grupos);
  - correo → `[email]`.
- **Lo que no se toca:** dígitos dentro de identificadores más largos (UUID, digest, ids de QR o de pey, `A1234567890`), montos y fechas.

### Indicadores de atraso (`tappy.sales.backlog`, comando `backlog`)

El comando muestra:

- eventos `received` sin aplicar;
- trabajos reclamables ahora;
- trabajos con arriendo, y cuántos de esos arriendos ya vencieron (un ejecutor que murió);
- trabajos agotados;
- intentos en `creating` que superan `TAPPY_ATTEMPT_CREATION_TIMEOUT_SECONDS`;
- incidencias abiertas.

Los eventos recibidos, los trabajos reclamables y las creaciones atascadas muestran además, en segundos, cuánto lleva esperando su elemento más antiguo.

Además, cada trabajo que procesa `run-jobs` registra `Reconciliation job <id> for sale <referencia> (attempt <id>): <resultado>`. Así una referencia de venta se puede seguir con `reconciliations`, `run-jobs` y `backlog`.

### Respaldo y restauración (README «Backup and restore»)

```sh
docker compose exec -T db pg_dump --format=custom --no-owner -U tappy -d tappy > tappy.dump \
  && docker compose exec -T db createdb -U tappy tappy_restored \
  && docker compose exec -T db pg_restore --no-owner --exit-on-error --single-transaction \
    -U tappy -d tappy_restored < tappy.dump
```

- **Encadenado:** cada paso corre solo si el anterior tuvo éxito; con `--single-transaction`, una restauración que falla a medias deja la base nueva vacía.

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
- **Pendiente:** el plazo de retención y cuándo purgar o minimizar es una decisión de producto todavía abierta (arquitectura §11), registrada en [#109](https://github.com/luisjrez/Tappy/issues/109) y enlazada desde el README. Mientras tanto se conservan y B34 no purga nada.

## Trazabilidad UC → AC → TC → test

| UC | AC | TC | Test real | Resultado |
| --- | --- | --- | --- | --- |
| B34-UC01 | B34-AC01 | B34-TC01 | `tests/test_diagnostics.py::test_an_unexpected_error_answers_a_reference_and_logs_it_without_sensitive_data`: un proveedor sintético lanza un error con token, CLABE, teléfono y correo. Resultado: `500` con la referencia; el log tiene la referencia y la plantilla de ruta, sin ninguno de los cuatro valores; la respuesta tampoco los contiene. Además `…::test_configured_secrets_never_reach_a_log_line`, `…::test_a_safe_caller_reference_is_kept_and_an_unsafe_one_replaced` `…::test_every_error_response_carries_its_reference` (`404`, `401`, `422`) y `…::test_server_and_command_lines_go_through_the_same_redacted_format`: un proceso real de `python -m tappy` escribe su línea de acceso con la referencia y con el teléfono `%2B52…` y la CLABE de la consulta enmascarados; `tappy.sales` y `tappy.identity` con la base caída salen con `1` y registran `Command … failed` sin la contraseña. Las reglas de redacción se prueban caso por caso en `tests/test_redaction.py` (`…::test_sensitive_values_are_masked`, `…::test_identifiers_amounts_and_dates_are_kept`, `…::test_configured_secrets_are_replaced_wherever_they_appear`, `…::test_a_longer_secret_is_replaced_whole_even_when_it_contains_a_shorter_one`, `…::test_a_secret_too_short_to_tell_apart_from_ordinary_words_is_not_replaced`) y el aviso de `tests/test_diagnostics.py::test_a_configured_secret_too_short_to_redact_is_named_without_its_value` | PASS |
| B34-UC02 | B34-AC02 | B34-TC02 | `tests/test_backup_restore.py::test_a_backup_restores_into_a_new_database_with_the_sale_and_its_pending_job`: `pg_dump`, después `createdb` y `pg_restore` en `tappy_restored`; `/ready` da `200`; la misma venta y el trabajo `pending` aparecen en `reconciliations` y `backlog`; el origen no cambia. Además `…::test_the_restore_refuses_to_overwrite_an_existing_database` | PASS |
| B34-UC03 | B34-AC03 | B34-TC03 | `tests/test_backup_restore.py::test_a_runner_interrupted_after_the_restore_finishes_the_job_once_and_can_be_followed`: tras restaurar, un ejecutor reclama y muere; `backlog` muestra el arriendo vencido. El primer `run-jobs` reclama 1 y lo verifica, y el log nombra la venta; el segundo no reclama nada. El trabajo termina `done` con 2 intentos, el ejecutor interrumpido ya no conserva su reclamo y el `backlog` final queda vacío. Además `tests/sales/test_backlog.py::test_every_backlog_indicator_counts_only_what_is_waiting` y `…::test_the_backlog_command_prints_each_indicator_with_its_age`: cada indicador con un valor distinto de cero, junto a elementos que no deben contar (trabajo futuro, arriendo vivo, trabajos `done`, evento aplicado, incidencia resuelta, creación reciente) | PASS |

## TDD

### Ronda 1 (`c23d9bb`)

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

### Ronda 2 (`caf9960`, `842a4e8`): correcciones de la review

**Red sobre `c23d9bb`** con los tests nuevos y endurecidos: fallan 9.

```
FAILED tests/test_redaction.py::test_sensitive_values_are_masked[clabe 002 180 70012345678 9.-clabe **************6789.]
FAILED tests/test_redaction.py::test_sensitive_values_are_masked[phone +525512345678-phone ********5678]
FAILED tests/test_redaction.py::test_sensitive_values_are_masked[phone +52 55 1234 5678-phone ********5678]
FAILED tests/test_redaction.py::test_sensitive_values_are_masked[phone 52-551-234-5678-phone ********5678]
FAILED tests/test_redaction.py::test_sensitive_values_are_masked[phone (55 1234 5678)-phone (******5678)]
FAILED tests/test_redaction.py::test_identifiers_amounts_and_dates_are_kept[qr SIM-1234567890AB and pey 01M3QR8H0RH0XBCKYYD242YXNV]
FAILED tests/test_diagnostics.py::test_an_unexpected_error_answers_a_reference_and_logs_it_without_sensitive_data
FAILED tests/test_diagnostics.py::test_configured_secrets_never_reach_a_log_line
FAILED tests/test_diagnostics.py::test_server_and_command_lines_go_through_the_same_redacted_format
9 failed, 18 passed in 20.27s
```

- **Motivos:**
  - las formas agrupadas y con `+52` no se enmascaraban;
  - un id de QR perdía dígitos;
  - la llave del webhook sin `whsec_` llegaba al log;
  - Uvicorn escribía con su formato propio (`INFO:     Started server process`), sin referencia ni redacción.
- **Caracterización:** `tests/sales/test_backlog.py` y la nueva aserción de TC03 ya pasan sobre `c23d9bb`. Cubren comportamiento existente que la review pidió probar, y su eficacia se demuestra con las mutaciones M15–M19.
- **Hallazgo de VC01:** la VC01 de esta ronda mostró que un `+52` codificado en URL (`%2B525512345678`) seguía sin enmascararse en la línea de acceso. Se añadieron 4 casos que fallaron (3 de forma codificada y 1 de `%20` antes del número) y después la corrección `842a4e8`.

**Mutaciones** sobre `caf9960`, con `tests/test_diagnostics.py`, `tests/test_redaction.py`, `tests/sales/test_backlog.py` y `tests/test_backup_restore.py`:

```
M1 formato sin redactar: 3 failed, 24 passed
M2 uvicorn con su propio logging: 1 failed, 26 passed
M3 CLABE sin enmascarar: 3 failed, 24 passed
M4 telefono sin enmascarar: 7 failed, 20 passed
M5 sin secretos configurados: 1 failed, 26 passed
M6 error 500 sin referencia: 1 failed, 26 passed
M7 referencia del cliente sin validar: 1 failed, 26 passed
M8 ejecutor sin log de referencia: 1 failed, 26 passed
M9 backlog sin arriendos vencidos: 1 failed, 26 passed
M10 telefono +52 sin prefijo: 4 failed, 23 passed
M11 digitos dentro de UUID: 1 failed, 27 passed
M12 llave whsec sin prefijo: 1 failed, 26 passed
M13 comando de ventas sin log de fallo: 1 failed, 26 passed
M14 comando de identidad sin log de fallo: 1 failed, 26 passed
M15 recibidos sin antiguedad: 2 failed, 25 passed
M16 vencidos con arriendo vivo: 2 failed, 25 passed
M17 agotados sin contar: 2 failed, 26 passed
M18 creaciones sin corte: 2 failed, 25 passed
M19 excepciones resueltas contadas: 2 failed, 25 passed
```

- **Sobrevivientes en la primera pasada:** M11 y M17.
  - M11: no había un id cuyos dígitos siguieran a una letra o `-` sin más letras detrás. Se añadió `qr SIM-1234567890 and order A1234567890`.
  - M17: la semilla tenía un trabajo agotado y uno `done`, así que contar `done` daba lo mismo. Se añadió un segundo trabajo `done`.
  - Repetidas, las dos fallan (las cifras de arriba son las de la repetición).

Mutaciones de la forma codificada, sobre `842a4e8`:

```
M20 sin %2B como prefijo: 3 failed, 24 passed
M21 sin %20 entre grupos: 1 failed, 26 passed
M22 codificacion contada como digitos: 4 failed, 23 passed
M23 sin inicio tras %20: 1 failed, 26 passed
```

### Ronda 3 (`a37fc63`): sugerencias no bloqueantes de la ronda 2

**Red sobre `cf004aa`** con los tests nuevos: fallan 9.

```
FAILED tests/test_redaction.py::test_sensitive_values_are_masked[clabe 0021 8070 0123 4567 89-clabe **************6789]
FAILED tests/test_redaction.py::test_sensitive_values_are_masked[phone +5215512345678-phone *********5678]
FAILED tests/test_redaction.py::test_sensitive_values_are_masked[phone +52 1 55 1234 5678-phone *********5678]
FAILED tests/test_redaction.py::test_sensitive_values_are_masked[phone (55) 1234 5678-phone ******5678]
FAILED tests/test_redaction.py::test_sensitive_values_are_masked[phone (551) 234 5678-phone ******5678]
FAILED tests/test_redaction.py::test_sensitive_values_are_masked[phone 55.1234.5678-phone ******5678]
FAILED tests/test_redaction.py::test_a_longer_secret_is_replaced_whole_even_when_it_contains_a_shorter_one
FAILED tests/test_redaction.py::test_a_secret_too_short_to_tell_apart_from_ordinary_words_is_not_replaced
FAILED tests/test_diagnostics.py::test_a_safe_caller_reference_is_kept_and_an_unsafe_one_replaced
9 failed, 30 passed in 6.29s
```

**Mutaciones** sobre `a37fc63`, con `tests/test_diagnostics.py` y `tests/test_redaction.py`:

```
M24 sin prefijo movil 1: 2 failed, 33 passed
M25 sin lada entre parentesis: 2 failed, 33 passed
M26 sin punto como separador: 1 failed, 34 passed
M27 sin CLABE en grupos de 4: 1 failed, 34 passed
M28 secretos en orden de llegada: 1 failed, 34 passed
M29 secretos cortos reemplazados: 1 failed, 34 passed
M30 referencia solo de digitos aceptada: 1 failed, 34 passed
```

**Sondeo de falsos positivos** tras aceptar `.` como separador: 100 000 UUID, 100 000 ids hexadecimales y 100 000 decimales aleatorios salen sin cambios. Versiones (`1.2.3`), IP (`192.168.100.200`), montos (`1234.56`), fechas (`2026.11.25`) y horas con microsegundos tampoco cambian.

**Refactor:** `wait_for_json` pasa de `tests/test_startup.py` a `tests/support.py`, y su exención `S310` se mueve con él. La comprobación de antigüedades del `backlog` usa un mínimo y una holgura de 60 s, en lugar de rangos estrechos.

## Aplicabilidad por superficie

| Superficie | Aplica | Justificación |
| --- | --- | --- |
| API | Sí | `X-Request-ID` en toda respuesta y `500` con referencia. Los snapshots de contrato no registran ese encabezado, así que el paso `api` (sin diferencias) solo demuestra que los cuerpos y códigos existentes no cambian; el encabezado lo prueban TC01 y VC01 |
| Logs | Sí | Formato con referencia y redacción en el servidor (incluido Uvicorn) y en los dos comandos |
| Comandos | Sí | `backlog` nuevo, log por trabajo en `run-jobs`, fallo inesperado registrado y procedimiento de respaldo |
| Panel | No aplica | El back office no cambia |

## B34-VC01 — respuestas, logs y comandos

Las secciones A y B son de la ronda 1 (`c23d9bb`); la sección C repite el escenario sobre el candidato de la ronda 2 (`842a4e8`) y lo compara con `c23d9bb`.

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

### C. Ronda 2: `c23d9bb` (antes) frente a `842a4e8` (después)

Mismo proceso con la base caída, más una petición `GET /health?phone=%2B525512345678&clabe=002180700123456789` (valores sintéticos).

#### Líneas de Uvicorn

Antes (`c23d9bb`), con el formato propio de Uvicorn, sin referencia y sin redacción:

```
INFO:     Started server process [48271]
INFO:     127.0.0.1:64589 - "POST /auth/login HTTP/1.1" 500 Internal Server Error
INFO:     127.0.0.1:64589 - "GET /health?phone=%2B525512345678&clabe=002180700123456789 HTTP/1.1" 200 OK
```

Después (`842a4e8`), cada línea de acceso lleva la referencia de su respuesta y la consulta sale enmascarada:

```
INFO uvicorn.error [-] Started server process [51438]
ERROR tappy.platform.diagnostics [7742342bd2ae4d798ef0b184cb8eb485] Unhandled error in POST /auth/login
INFO uvicorn.access [7742342bd2ae4d798ef0b184cb8eb485] 127.0.0.1:64854 - "POST /auth/login HTTP/1.1" 500
INFO uvicorn.access [918bb42c00db46ad8eb5ac52a945bad7] 127.0.0.1:64854 - "GET /health?phone=********5678&clabe=**************6789 HTTP/1.1" 200
INFO uvicorn.access [vc01-caller-ref] 127.0.0.1:64854 - "GET /health HTTP/1.1" 200
```

Apariciones de cada valor sensible en el log del servidor:

| Valor sintético | `c23d9bb` | `842a4e8` |
| --- | --- | --- |
| Token `Bearer` | 0 | 0 |
| CLABE | 1 | 0 |
| Teléfono | 1 | 0 |
| Contraseña de la base | 0 | 0 |
| `TAPPY_SECRET_KEY` | 0 | 0 |

Las respuestas HTTP no cambian entre las dos revisiones: `500` con referencia en los dos errores, `200` en `/health` y la referencia del cliente respetada.

#### Comandos con la base caída

`python -m tappy.sales backlog` y `python -m tappy.identity show --email vc01-operador@tappy.example`, con `TAPPY_DATABASE_URL` en el puerto cerrado:

- **Antes (`c23d9bb`):** exit 1 con una traza de Python sin formato (145 y 138 líneas), fuera del log y sin redacción.
- **Después (`842a4e8`):** exit 1 con una línea de log y la traza redactada debajo:

  ```
  ERROR tappy.sales.cli [-] Command backlog failed
  ERROR tappy.identity.cli [-] Command show failed
  sqlalchemy.exc.OperationalError: (psycopg.OperationalError) connection failed: connection to server at "127.0.0.1", port 59999 failed: could not receive data from server: Connection refused
  ```

  La contraseña de la base y el correo aparecen 0 veces.

#### Respaldo y restauración con `--single-transaction`

Repetido sobre `842a4e8` con el procedimiento del README, ahora encadenado y con `--single-transaction`, en el proyecto Compose desechable `tappy-compose-a270bf8364fa`. Venta sintética `EE1FJ76YJ2`.

- Restaurar sobre `tappy` → rechazado por `createdb` (exit 1).
- Restaurar en `tappy_restored` → OK; `GET /ready` = 200; venta `open` y trabajo `expired pending`.
- `backlog` tras el ejecutor interrumpido: `leased reconciliation jobs: 1 (1 with an expired lease)`.
- `run-jobs` reclama 1 y registra `Reconciliation job … for sale EE1FJ76YJ2 (…): verified`; la segunda ejecución reclama 0.
- Al final: trabajo `done 2`, intento verificado y base de origen sin cambios.


### D. Ronda 3: `a37fc63`

Mismo script de la sección C sobre `a37fc63`, más una petición con `X-Request-ID: 5512345678`:

- `GET /health` con referencia de solo dígitos → 200 · `X-Request-ID: ada90acf5cd34f5c8507a0ae2c7eecb8` (se genera una nueva).
- El resto de respuestas es igual que en la sección C, y la línea de acceso sigue enmascarando `phone=********5678&clabe=**************6789`.
- Apariciones en el log del token, la CLABE, el teléfono, la contraseña de la base y `TAPPY_SECRET_KEY`: 0 de cada uno.

**Validación:**

- **TC01:**
  - cada `500` trae su referencia en el cuerpo y en `X-Request-ID`, y la misma referencia encabeza su línea de log, con la plantilla de ruta y sin IDs;
  - una referencia válida del cliente se respeta;
  - no hay valores sensibles ni en la respuesta ni en el log;
  - antes no había referencia y la conexión se cortaba en la siguiente petición;
  - en la ronda 2, las líneas de Uvicorn y los fallos de los comandos pasan por el mismo formato redactado, y la CLABE y el teléfono que `c23d9bb` dejaba en la línea de acceso desaparecen.
- **TC02:**
  - la restauración en `tappy_restored` queda lista (`/ready` 200), con la venta y su trabajo pendiente visibles en `backlog` y `reconciliations`;
  - restaurar sobre la base en uso se rechaza;
  - el origen no cambia.
- **TC03:**
  - el arriendo vencido de un ejecutor interrumpido aparece en `backlog`;
  - `run-jobs` lo completa una sola vez y el log nombra la venta (`6GKF5KZDHZ` en la ronda 1, `EE1FJ76YJ2` en la repetición de la ronda 2);
  - la segunda ejecución no reclama nada y el `backlog` final queda vacío.

Estado VC01: **PASS**.

## Checks

`uv run python -m quality.check` sobre `bcdb773`, con `.env` exportado:

- format, lint, types (mypy strict) y hygiene: PASS;
- migrations: PASS; sin migraciones nuevas, solo upgrade/downgrade/upgrade + `alembic check`;
- tests: PASS, 617 passed, con Postgres real aislado y proyectos Compose desechables;
- api: PASS, 15 contratos sin diferencias (no registran `X-Request-ID`; ver «Aplicabilidad»);
- evidence: B01–B33 APPROVED. B34 queda bloqueado solo porque su review está `PENDING`, que es lo esperado antes de la ronda 4.

Rondas anteriores, con los mismos pasos en PASS: `c23d9bb` (ronda 1) con 583 tests `842a4e8` (ronda 2) con 608 y `a37fc63` (ronda 3) con 616.

## Supresiones

Ninguna nueva. Las exenciones existentes se mueven con su código: `S603`/`S607` con `ComposeProject` a `tests/compose_support.py`, y `S310` con `wait_for_json` de `tests/test_startup.py` a `tests/support.py`.

## Umbral

AC PASS / AC aplicables = 3/3 = **100%**.

## Review Standards/Spec

| Ronda | Revisión | Standards | Spec | Hallazgos |
| --- | --- | --- | --- | --- |
| 1 | `c23d9bb` | REQUEST_CHANGES | REQUEST_CHANGES | Standards 5, Spec 9 (ver abajo) |
| 2 | `842a4e8` | APPROVE | APPROVE | Sin bloqueantes; Standards 4 y Spec 4 sugerencias (ver abajo) |
| 3 | `a37fc63` | APPROVE | APPROVE | Sin bloqueantes; las dos revisiones señalan que un secreto corto queda visible sin aviso, y Spec, que faltaban dos tests en la fila de trazabilidad |
| 4 | `bcdb773` | APPROVE | APPROVE | Sin bloqueantes. Tres notas aceptadas sin aplicar (ver abajo) |

### Hallazgos de la ronda 1 y su corrección

**Standards**

1. Las líneas de Uvicorn saltaban la redacción (su configuración por defecto no propaga) → `log_config=None` y test con un proceso real.
2. Las expresiones de CLABE/teléfono enmascaraban dígitos de UUID y no reconocían `+52` → reglas con límites de token, formas agrupadas y `+52`; casos unitarios en `tests/test_redaction.py` (22 en `842a4e8`, 30 en `a37fc63`).
3. El filtro mutaba el `LogRecord` y podía fallar en `getMessage` → `RedactingFormatter` redacta la línea ya formateada.
4. El fixture de logs no restauraba el nivel raíz → restaurado.
5. Prefijo del proyecto Compose ligado a persistencia → `tappy-compose-`.

**Spec**

1. y 2. Las mismas reglas de redacción → corregidas como Standards 2.
3. Errores inesperados de los comandos sin log → `Command … failed` y exit 1 en `tappy.sales` y `tappy.identity`.
4. Uvicorn → como Standards 1.
5. Faltaba probar cada indicador del `backlog` con valores distintos de cero → `tests/sales/test_backlog.py`.
6. La retención de payloads debía quedar como seguimiento → [#109](https://github.com/luisjrez/Tappy/issues/109), enlazada desde el README y esta evidencia.
7. Restauración sin encadenar → `&&` y `--single-transaction`, también en el helper de los tests.
8. Redacción de la evidencia («15 contratos», «cada indicador…») y aserciones de la contraseña de la base y la llave del webhook → corregidas; la referencia dentro del pool de hilos la cubre el aviso del proveedor.
9. TC03 no comprobaba que el dueño interrumpido perdiera su reclamo → `held_claim` es `None` tras la reanudación.

Además, la VC01 de la ronda 2 encontró el `+52` codificado en URL sin enmascarar → corregido en `842a4e8`.

### Sugerencias de la ronda 2 y su corrección (`a37fc63`)

**Standards**

1. `wait_for_json` se importaba de un módulo de tests → movido a `tests/support.py`.
2. Faltaban `+52 1` y la lada entre paréntesis → añadidos, con casos.
3. Antigüedades del `backlog` con rangos estrechos → mínimo esperado más una holgura de 60 s.
4. Los secretos se reemplazaban en orden de llegada → del más largo al más corto, con un test de secretos contenidos.

**Spec**

1. Una referencia del cliente de 10 o 18 dígitos se enmascararía en el log y dejaría de coincidir con el encabezado → se rechazan las referencias de solo dígitos.
2. Una contraseña corta borraría palabras normales de los logs → no se reemplazan secretos de menos de 8 caracteres; documentado en el README.
3. Formatos sin cubrir (`(55) 1234 5678`, `55.1234.5678`, CLABE `4 4 4 4 2`), y el README era más amplio que las reglas → formatos añadidos, y el README nombra exactamente las agrupaciones.
4. Detalles desactualizados de la evidencia (número de casos y venta de TC03) → corregidos.

### Sugerencias de la ronda 3 y su corrección (`bcdb773`)

1. **Un secreto de menos de 8 caracteres queda visible sin que nadie lo note** (Standards y Spec). `configure_logging` avisa una vez por proceso, con un `WARNING` que nombra el ajuste y nunca su valor.
   - Se eligió el aviso en lugar de rechazar la configuración (propuesta de Spec) para no romper una base local sin contraseña o con una contraseña corta. El README pide secretos más largos.
   - **Red:** `test_a_configured_secret_too_short_to_redact_is_named_without_its_value` falló con `assert 0 == 1` antes del cambio.
2. **Faltaban dos tests en la fila de trazabilidad de TC01** (Spec) → añadidos, con el test del aviso.

### Notas de la ronda 4, aceptadas sin aplicar

Las dos revisiones aprobaron `bcdb773`. Las tres notas restantes son cosméticas o teóricas y se registran sin abrir otra ronda:

1. **Nombre del ajuste** (Standards): el aviso dice «The database password» mientras los demás nombran la variable de entorno. Es solo redacción; el aviso nunca muestra el valor.
2. **Duplicación en el test del aviso** (Standards): repite la preparación del fixture `log_stream` en línea. No cambia lo que se prueba.
3. **`whsec_` corto** (Spec): solo se mide la longitud del valor completo. Un `TAPPY_PEY_WEBHOOK_SECRET` como `whsec_abc` dejaría `abc` sin redactar y sin aviso. Los secretos reales de webhook son cadenas base64 largas, así que es teórico.

## Estado final

Standards y Spec: **APPROVE** sobre `bcdb773` (evidencia `05d4230`). AC 3/3 = 100 %, VC01 PASS y todos los checks en verde.
