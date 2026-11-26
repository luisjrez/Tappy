# Evidencia — B23 Recuperar trabajos tras reinicio

Ticket: [#31](https://github.com/luisjrez/Tappy/issues/31) · Historia: [H5 #5](https://github.com/luisjrez/Tappy/issues/5) · Protocolo: [TICKET_QUALITY_PROTOCOL](../planning/TICKET_QUALITY_PROTOCOL.md) · Manifiesto: [B23-job-recovery.toml](B23-job-recovery.toml)

> Verificado con un pey falso local y relojes controlados. **No hubo consultas, pagos ni webhooks reales.** Solo la evidencia del proveedor (webhook firmado o consulta) confirma un cobro; ningún operador marca recibido.

## Revisiones y escenario

- **Trazabilidad:** B23-UC01–UC03, B23-AC01–AC03, B23-TC01–TC03 y B23-VC01.
- **Modalidad:**
  - **Resultado inicial** para el comando nuevo `run-jobs`, que ejecuta un lote programable.
  - **Antes/después** para `reconciliations`: el listado gana intentos, lease, último problema y trabajos `exhausted`.
  - La API no cambia de contrato (`api`: 16 contratos sin diferencias).
- **Base y revisiones:**
  - Base: rama B22 `5295de9` ([PR #78](https://github.com/luisjrez/Tappy/pull/78)), stack #68.
  - Candidato: `94c3ae6`.
  - Correcciones de la review: `3cb0970` (ronda 1) y `c98e5b5` (nit de la ronda 2), revisión final. La VC01 se repitió sobre ella.
- **Entorno:** macOS, Colima + Compose (Postgres 18), Python 3.14.8. Fecha: 2026-11-25 (UTC). Ejecutor: sesión local de desarrollo del autor del PR.

## Diseño

### Trabajos persistidos (migración `0018`)

`reconciliation_jobs` gana estas columnas, según el §6 de arquitectura:

- `tries` (≥ 0);
- `lease_owner` y `lease_until`;
- `last_problem`;
- el estado `exhausted`;
- un índice parcial de trabajos `pending` por `run_at`.

El downgrade se niega si hay trabajos `exhausted`.

### Reclamación con lease (`tappy.sales.jobs`)

- `claim_jobs` toma hasta `TAPPY_JOB_BATCH_SIZE` trabajos `pending` que cumplan tres condiciones: ya vencieron, tienen el lease libre o vencido y les quedan intentos. Usa `FOR UPDATE SKIP LOCKED`.
- Cada reclamación les asigna un `lease_owner` nuevo y `lease_until = ahora + TAPPY_JOB_LEASE_SECONDS`, y suma un intento: una caída también consume intento.
- Con el lease vigente, nadie más los toma.
- Terminar (`finish_job`) o reprogramar (`reschedule_job`) exige ser el dueño del lease, que se borra al cerrar un trabajo por cualquier vía. Así, un ejecutor cuyo lease venció no cambia nada (`lease_lost`). Si otro camino ya cerró el trabajo como `done`, reprogramarlo da `lease_lost` y terminarlo cuenta como confirmado, sin ningún cambio en los datos.
- Con pey, el lease debe superar la consulta más larga posible: 10 páginas × 4 fases de timeout. El validador de configuración no aplica con el simulador.

### Planificador aislado

- `JobPolicy.delay`: el backoff empieza en `TAPPY_JOB_BACKOFF_SECONDS` y se duplica por intento hasta `TAPPY_JOB_BACKOFF_MAX_SECONDS`.
- Si pey responde 429 con `Retry-After`, la espera es la mayor de las dos. Se aceptan segundos, acotados a un día; una fecha HTTP o un valor inválido se ignoran.
- El reloj (`Clock`) se inyecta en todo el ejecutor: los tests usan `MovableClock` y el comando, `SystemClock`.
- Supuesto: los leases se comparan con el reloj del ejecutor, así que los hosts deben tener los relojes sincronizados.

### Ejecutor de lotes (`JobRunner.run`, comando `python -m tappy.sales run-jobs`)

Pensado para cron (por ejemplo, cada minuto), sin cola externa. Cada lote hace, en orden:

1. Aplica hasta un lote de eventos `received`. Un evento guardado antes de una caída se aplica.
2. Cierra los trabajos de intentos ya pagados, por ejemplo por un webhook.
3. Pasa a conciliación los `creating` interrumpidos.
4. Marca `exhausted` los trabajos sin intentos cuyo último lease venció (`lease_expired`).
5. Reclama y ejecuta los trabajos con la conciliación de B22.

Resultado de cada trabajo:

- `confirmed` o `review`: el trabajo queda `done`.
- `not_queryable` (intento sin id de QR): queda `exhausted` en el acto para un operador, porque la consulta por id es imposible; un webhook posterior todavía puede confirmar el cobro y el lote siguiente cierra el trabajo.
- Sin evidencia o con un problema del proveedor: se reprograma con backoff. Al llegar a `TAPPY_JOB_MAX_TRIES` queda `exhausted` y no se reintenta más.

El dinero nunca se cuenta dos veces: todo pasa por la confirmación deduplicada de B18–B22.

### Consultable

- `reconciliations` lista los trabajos `pending` y `exhausted` con intentos, lease y último problema.
- `GET /sales/{id}` muestra la confirmación.
- `run-jobs` imprime un resumen: eventos, trabajos cerrados, intentos recuperados, reclamados, confirmados, en revisión, reprogramados, agotados, con lease perdido y fallidos.

Decisión: `run-jobs` termina con 0 aunque haya fallos, igual que `process-events`; el conteo `failed` queda en la salida para la supervisión.

### Pendientes conocidos

- Un evento `received` que falla siempre por la base de datos se reintenta en cada lote: no tiene contador de intentos. Está acotado por lote y protegido por `skip_locked`.
- Un trabajo `exhausted` deja el intento en `reconciling` y no hay comando para rearmarlo. La revisión por un operador es el back office (H6).

## Trazabilidad UC → AC → TC → test

Todos los tests están en `tests/sales/test_job_runner.py`, salvo los indicados.

| UC | AC | TC | Test real | Resultado |
| --- | --- | --- | --- | --- |
| B23-UC01 | B23-AC01 | B23-TC01 | `test_an_event_stored_before_a_crash_is_applied_by_the_next_batch` (por el comando `run-jobs`); `test_a_due_job_is_reconciled_and_its_result_is_visible`; `test_an_interrupted_creation_without_a_qr_id_goes_to_an_operator_at_once`; `test_jobs_of_attempts_paid_by_a_webhook_are_closed_by_the_next_batch` | PASS |
| B23-UC02 | B23-AC02 | B23-TC02 | `test_a_live_lease_has_a_single_claimant` (transacción abierta y lease vigente: 0 reclamados); `test_a_claimant_whose_lease_expired_cannot_finish_the_job` (dueños distintos, 1 transferencia); `test_a_job_closed_elsewhere_while_leased_is_never_reopened` | PASS |
| B23-UC03 | B23-AC03 | B23-TC03 | `test_a_crash_and_a_rate_limit_are_retried_with_backoff_and_a_limit` (caída, lease vigente, lease vencido, 429 → 12:13, antes de tiempo no reclama, `exhausted` al tercer intento, 2 consultas en total); `test_a_retry_after_longer_than_the_backoff_is_respected`; `test_a_crash_after_every_claim_still_ends_exhausted`; `test_no_evidence_waits_with_growing_backoff`; `tests/payments/test_pey_query.py::test_a_rate_limit_carries_the_providers_bounded_wait`; `tests/sales/test_uncertain_creation.py::test_the_job_lease_must_outlast_a_bounded_query_only_with_pey` | PASS |

## TDD

| Comportamiento | Red | Green |
| --- | --- | --- |
| Ejecutor, lease y backoff | Los tests se escribieron antes del código: `ModuleNotFoundError: No module named 'tappy.sales.jobs'`. Primer Green: 8 de 9 pasan; el que falló tenía mal el texto esperado (`1 event applied`) | `jobs.py`, `0018`, `run-jobs` |
| Lease vigente | Mutación sin condición de lease: fallan `live_lease_has_a_single_claimant` y `crash_and_a_rate_limit…` | Filtro de lease |
| Límite de intentos | Mutación sin `tries < max` en la reclamación: falla `crash_after_every_claim…` (tras reforzar ese test con una reclamación directa, porque la primera mutación sobrevivía gracias al barrido) | Filtro y barrido |
| `Retry-After` | Mutación que ignora la espera: falla `retry_after_longer_than_the_backoff…` | `max(backoff, retry_after)` |
| Dueño del lease | Mutación sin `lease_owner`: falla `claimant_whose_lease_expired…`. Mutación con un cierre por pago que no borra el lease: falla `job_closed_elsewhere…` | `held_claim` por dueño; `close_paid_jobs` borra el lease |

## Aplicabilidad por superficie

| Superficie | Aplica | Justificación |
| --- | --- | --- |
| Comandos | Sí | `run-jobs` nuevo; `reconciliations` ampliado |
| API | Sí, sin cambio de contrato | `GET /sales/{id}` refleja lo recuperado |
| Panel | No aplica | Sin vistas en este alcance |

## B23-VC01 — Lote, lease y 429

Proceso real `python -m tappy` con `TAPPY_PAYMENT_PROVIDER=pey`, `TAPPY_PEY_TIMEOUT_SECONDS=0.1` y `TAPPY_JOB_LEASE_SECONDS=5`, para ver el vencimiento en tiempo real. El pey falso local responde por QR: B con `429` y `Retry-After: 300`, C con un pago. Valores sintéticos.

Escenarios:

- **A:** evento guardado sin aplicar, que representa una caída tras persistirlo; se inserta directamente en `webhook_events`.
- **B y C:** intentos `reconciling` con un trabajo pendiente, es decir, una creación incierta preparada por SQL.

En el «después», el ejecutor 1 se simula desde el script de la VC01: llama a `claim_jobs` con `JobPolicy.from_settings` y no termina los trabajos, que es lo que deja un proceso caído.

### Antes (B22 `5295de9`)

- A: evento guardado y proceso caído antes de aplicarlo → 200 `{"status": "open", "confirmed_amount_cents": 0, "attempt": "pending", "transfers": []}`

**Lote programado**

```
$ python -m tappy.sales run-jobs
usage: python -m tappy.sales [-h]
                             {reconciliations,recover-interrupted,process-events,event-conflicts,exceptions,reconcile} ...
python -m tappy.sales: error: argument command: invalid choice: 'run-jobs' (choose from 'reconciliations', 'recover-interrupted', 'process-events', 'event-conflicts', 'exceptions', 'reconcile')
(exit 2)
```

- A después → 200 `{"status": "open", "confirmed_amount_cents": 0, "attempt": "pending", "transfers": []}`

- B después (429) → 200 `{"status": "open", "confirmed_amount_cents": 0, "attempt": "reconciling", "transfers": []}`

- C después → 200 `{"status": "open", "confirmed_amount_cents": 0, "attempt": "reconciling", "transfers": []}`

**Trabajos abiertos**

```
$ python -m tappy.sales reconciliations
attempt: 3ab95a1e-0aa7-4656-87af-b7636c423f81
sale reference: 0RKNY7BA46
attempt status: reconciling
reason: timeout
status: pending
run at: 2026-11-25T06:41:46.521746+00:00

attempt: 94caab8a-d18b-46c7-ac32-64cf0bd4fd1a
sale reference: T0XW7P7APR
attempt status: reconciling
reason: timeout
status: pending
run at: 2026-11-25T06:41:46.555804+00:00
(exit 0)
```

pey requests: (ninguna)

### Después (revisión final `c98e5b5`)

- A: evento guardado y proceso caído antes de aplicarlo → 200 `{"status": "open", "confirmed_amount_cents": 0, "attempt": "pending", "transfers": []}`

Ejecutor 1 reclama 2 trabajos y cae sin terminarlos (lease de 5 s).

**Ejecutor 2 con el lease vigente**

```
$ python -m tappy.sales run-jobs
events: 1 event applied, 0 unmatched, 0 in review, 0 duplicates, 0 failed
jobs of paid attempts closed: 0
interrupted attempts moved to reconciliation: 0
jobs claimed: 0
confirmed: 0, in review: 0, rescheduled: 0, exhausted: 0, lease lost: 0, failed: 0
(exit 0)
```

Hora del lote programado (UTC): 2026-11-25T06:57:15+00:00

**Lote programado**

```
$ python -m tappy.sales run-jobs
events: 0 events applied, 0 unmatched, 0 in review, 0 duplicates, 0 failed
jobs of paid attempts closed: 0
interrupted attempts moved to reconciliation: 0
jobs claimed: 2
confirmed: 1, in review: 0, rescheduled: 1, exhausted: 0, lease lost: 0, failed: 0
QR payments query for attempt ce0a39b7-e8f1-4054-ba54-9ea3669e8956 failed (rate_limited); payment stays unconfirmed
(exit 0)
```

- A después → 200 `{"status": "paid", "confirmed_amount_cents": 30000, "attempt": "paid", "transfers": ["TX-VC23-A"]}`

- B después (429) → 200 `{"status": "open", "confirmed_amount_cents": 0, "attempt": "reconciling", "transfers": []}`

- C después → 200 `{"status": "paid", "confirmed_amount_cents": 30000, "attempt": "paid", "transfers": ["TX-VC23-C"]}`

**Trabajos abiertos**

```
$ python -m tappy.sales reconciliations
attempt: ce0a39b7-e8f1-4054-ba54-9ea3669e8956
sale reference: A39KQEZA2F
attempt status: reconciling
reason: timeout
status: pending
run at: 2026-11-25T07:02:16.246716+00:00
tries: 2
leased until: not leased
last problem: rate_limited
(exit 0)
```

pey requests:
{"get": "/transaction/codi/qr/QRVC23BBBB", "nextToken": "first", "status": 429}
{"get": "/transaction/codi/qr/QRVC23CCCC", "nextToken": "first", "status": 200}

Validación:

- **TC01:** el evento de A se aplica y el cobro queda `paid`.
- **TC02:** con el lease vigente del ejecutor caído, el segundo ejecutor no reclama nada (0).
- **TC03:**
  - Vencido el lease, el lote reclama los 2 trabajos (intento 2).
  - C se confirma.
  - B recibe `429` y se reprograma a la hora del lote + 300 s (06:57:15 → 07:02:16). El backoff del intento 2 sería de 120 s, así que gana la espera de pey.
  - `reconciliations` muestra `tries: 2`, `last problem: rate_limited` y el trabajo sin lease.
- **Antes:** `run-jobs` no existía (exit 2), el evento guardado y los trabajos quedaban pendientes, y el listado no mostraba intentos ni problemas.

Los datos se eliminaron al terminar. Estado VC01: **PASS**.

### Diferencias y decisión

| TC/AC | Antes (B22) | Después | Clasificación | Decisión |
| --- | --- | --- | --- | --- |
| TC01 | Sin ejecutor de lotes; evento y trabajos pendientes | Lote que aplica, recupera y concilia | Nuevo | Aceptada |
| TC02 | Sin lease | Un solo reclamante por lease; sin efectos duplicados | Nuevo | Aceptada |
| TC03 | Sin reintentos | Backoff, `Retry-After`, límite y `exhausted` | Nuevo | Aceptada |
| `reconciliations` | Motivo, estado y fecha | Además intentos, lease, último problema y `exhausted` | Aditiva | Aceptada |

## Checks

`uv run python -m quality.check` sobre `c98e5b5`, con `.env` exportado: PASS en todos los pasos.

- format, lint y types (mypy strict).
- hygiene.
- migrations: upgrade/downgrade/upgrade de `0018` + `alembic check`.
- tests: 456 passed, Postgres real aislado.
- api: 16 contratos sin diferencias.
- evidence: B01–B22 APPROVED.

## Supresiones

Sin supresiones nuevas.

## Umbral

AC PASS / AC aplicables = 3/3 = **100%**.

## Review Standards/Spec

| Ronda | Revisión | Standards | Spec | Hallazgos |
| --- | --- | --- | --- | --- |
| 1 | `94c3ae6` | REQUEST_CHANGES | REQUEST_CHANGES | Ver detalle debajo de la tabla |
| 2 | `3cb0970` + `ca78ad5` | APPROVE | APPROVE | Bloqueantes resueltos. Aplicado en `c98e5b5`: comparación directa con `NOT_QUERYABLE`. Evidencia: redacción de `lease_lost`, filas de la VC01 como lista, peticiones a pey vacías explícitas y cómo se simuló el ejecutor 1. Notas sin cambio: el barrido de cierre puede esperar un lock breve de otro ejecutor |

Detalle de la ronda 1, todo corregido en `3cb0970`.

Bloqueantes:

- Un trabajo cerrado por otra vía podía reprogramarse o agotarse, porque el cierre por pago no borraba el lease. Ahora lo borra, y lo prueba un test con mutación.
- El test de creación interrumpida usaba un estado imposible: un intento `creating` con id de QR. Ahora el intento real sin id pasa a `exhausted` en el acto (`not_queryable`).

Notas aplicadas:

- Se cierran los trabajos `pending` o `exhausted` de intentos ya pagados.
- `lease_expired` solo sustituye el último problema si el trabajo quedó reclamado.
- Los eventos se procesan por lotes acotados.
- El validador del lease solo aplica con pey.
- Se eliminó `run_jobs`, que solo delegaba.
- Nombres: `lease_lost` y «No open reconciliations».

Registradas sin cambio:

- `run-jobs` termina con 0 aunque haya fallos.
- `last_problem` es texto libre que mezcla problemas del proveedor y resultados.
- Supuesto de relojes sincronizados.
- `.all()` en lugar de `.tuples()`, que SQLAlchemy 2.1 depreca.

Hallazgos pendientes: 0.
