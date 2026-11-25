# Evidencia — B16 Recuperar creación QR incierta

Ticket: [#24](https://github.com/luisjrez/Tappy/issues/24) · Historia: [H4 #4](https://github.com/luisjrez/Tappy/issues/4) · Protocolo: [TICKET_QUALITY_PROTOCOL](../planning/TICKET_QUALITY_PROTOCOL.md) · Manifiesto: [B16-uncertain-creation.toml](B16-uncertain-creation.toml)

> Verificado con el simulador y con un pey falso local que sirve la forma oficial del contrato; **no se llamó a pey real** (sin integración bancaria real demostrada). La conciliación efectiva de estos intentos (consultar a pey y resolver) es B22; la recuperación de trabajos tras reinicio con lease, B23.

## Revisiones y escenario

- Ticket, UC/AC/TC y comprobación: B16-UC01–UC03, B16-AC01–AC03, B16-TC01–TC03, B16-VC01. Incluye el arrastre de B14 en [#24](https://github.com/luisjrez/Tappy/issues/24) (fallo del proveedor que dejaba el intento `creating` activo y caída entre la llamada y el registro).
- Modalidad: **antes/después** para el resultado incierto de `POST /sales/{id}/attempts` (B14/B15 respondían `503` y dejaban el intento `creating`) y **resultado inicial** para los trabajos de conciliación y la interfaz operativa (`python -m tappy.sales`).
- Base: rama B15 `85786d1` (PR #71), stack de H4 #68. Revisión evaluada: candidato `1e3096e`. Commit aparte `fb011e1`: el manifiesto de B15 sigue el test renombrado (`…keeps_the_attempt_creating` → `…keeps_the_attempt_reconciling`), con el precedente de B42/B06.
- Entorno: macOS, Colima + Compose (Postgres 18), Python 3.14.8. Fecha: 2026-11-24 (UTC 2026-11-25). Ejecutor: sesión local de desarrollo del autor del PR.
- Datos sintéticos (comercios «Tienda Demo A/B», CLABE ficticias, clave de prueba generada por ejecución).

## Diseño

- `ReconciliationJob` (migración `0012_reconciliation_jobs`): `attempt_id`, `reason`, `status` (`pending`/`done`), `run_at`, `tries`, `lease_until` (para B23) y unicidad `(attempt_id, reason)` — un trabajo lógico por intento y razón.
- Resultado incierto (`ProviderUnavailableError`: `timeout`, `connection`, `server_error`, `invalid_response`, `duplicate_provider_id`): en una transacción, el intento pasa de `creating` a `reconciling` y se crea su trabajo con el motivo como evidencia. La API responde **`202`** con el intento (id, referencia y estado), sin instrucciones para repetir el pago (§10 de arquitectura). Nunca se declara `failed` por falta de respuesta; `failed` sigue reservado a rechazos definitivos (`failure_code`, B15).
- Repetir con la misma `Idempotency-Key` devuelve el mismo intento (`200`) sin volver a llamar al proveedor; otra clave recibe `409` porque `reconciling` es activo.
- Caída entre la llamada al proveedor y el registro: el intento queda `creating`. `python -m tappy.sales recover-interrupted` mueve a `reconciling` (trabajo `interrupted_creation`) los intentos `creating` sin cambios desde hace más de `TAPPY_ATTEMPT_CREATION_TIMEOUT_SECONDS` (por defecto 60, mayor que el timeout de pey de 10), con `FOR UPDATE SKIP LOCKED`; es idempotente.
- Interfaz operativa: `python -m tappy.sales reconciliations` lista intentos y trabajos pendientes (intento, referencia, estado, motivo, `run_at`).
- Refactor («unificar errores definitivos e inciertos sin perder evidencia»): una sola salida en `request_attempt` — `pending` (QR registrado), `failed` + `failure_code` (definitivo, `502`) o `reconciling` + trabajo con motivo (incierto, `202`).

## Trazabilidad UC → AC → TC → test

| UC | AC | TC | Test real | Resultado |
| --- | --- | --- | --- | --- |
| B16-UC01 | B16-AC01 | B16-TC01 | `test_lost_response_leaves_the_attempt_reconciling_with_a_durable_job` (el proveedor recibió la orden y la respuesta se perdió: `202`, `reconciling`, referencia, sin id inventado; trabajo `timeout:pending`); `test_every_uncertain_outcome_is_kept_for_reconciliation` (`server_error`, `invalid_response`, `connection`); `test_uncertain_response_keeps_the_attempt_reconciling` (pey 201 sin id); `test_a_provider_id_already_linked_to_another_attempt_is_uncertain` | PASS |
| B16-UC02 | B16-AC02 | B16-TC02 | `test_retry_with_the_same_key_recovers_the_attempt_without_a_second_request` (misma clave → `200` mismo intento; otra clave → `409`; una sola orden al proveedor; 1 intento, 1 trabajo); `test_unavailable_provider_keeps_the_attempt_for_reconciliation` | PASS |
| B16-UC03 | B16-AC03 | B16-TC03 | `test_uncertainty_and_job_survive_a_restart_and_show_in_the_operations_command` (nueva instancia: sigue `reconciling`; el comando lista intento, referencia, motivo y `pending`; nada `failed`); `test_interrupted_creations_are_moved_to_reconciliation_by_the_operations_command`; `test_recent_creations_are_left_alone`; `test_recovery_runs_are_idempotent` | PASS |

## TDD

| Comportamiento | Red | Green |
| --- | --- | --- |
| Resultado incierto, reintento, reinicio | `assert <HTTPStatus.SERVICE_UNAVAILABLE: 503> == <HTTPStatus.ACCEPTED: 202>`, `assert 'creating' == 'reconciling'` | `record_uncertain_qr` + `ReconciliationJob` + `202` |
| Interfaz operativa | Primero `No module named tappy.sales.__main__` (no es Red de comportamiento); con el esqueleto del CLI: `assert '1 interrupted attempt moved to reconciliation' in ''`, `assert 'creating' == 'reconciling'` | `recover_interrupted`, `pending_reconciliations`, CLI |

Cambios esperados en tests anteriores (antes/después): `test_unavailable_provider_fails_closed_and_keeps_the_reservation` (B14) → `test_unavailable_provider_keeps_the_attempt_for_reconciliation`; `test_uncertain_response_keeps_the_attempt_creating` (B15) → `…_reconciling`; `test_a_provider_id_already_linked_to_another_attempt_is_uncertain` ahora espera `202` y un trabajo `duplicate_provider_id`.

## B16-VC01 — Antes/después y recuperación real

**Antes** ([B15](B15-pey-qr.md), `55c57e9`): respuesta incierta → `503 {"detail": "The QR provider is unavailable (invalid_response); the attempt is kept for reconciliation"}` y el intento `creating` (activo, sin trabajo).

**Después** — proceso real `python -m tappy` sobre `1e3096e` con `TAPPY_PAYMENT_PROVIDER=pey`, pey falso local en `127.0.0.1:8899` y `TAPPY_PEY_TIMEOUT_SECONDS=1`; el pey falso acepta (registra la petición) y responde a los 3 s:

| Petición | Status | Respuesta |
| --- | --- | --- |
| `POST /sales/{sale}/attempts {qr}` con K (pey acepta y responde tras 3 s; timeout de Tappy 1 s) | 202 | `{"id": "4e50edb4-c2a1-4730-af50-21b85fb270bf", "sale_id": "f0547570-e684-4e9c-97fb-0bed4c0790be", "sale_reference": "HWX4E6GC5R", "method": "qr", "status": "reconciling", "simulated": false, "provider_request_id": null, "qr_payload": null, "failure_code": null, "created_at": "2026-11-25T00:04:49.424186Z"}` |
| `POST /sales/{sale}/attempts {qr}` con K (reintento) | 200 | `{"id": "4e50edb4-c2a1-4730-af50-21b85fb270bf", "sale_id": "f0547570-e684-4e9c-97fb-0bed4c0790be", "sale_reference": "HWX4E6GC5R", "method": "qr", "status": "reconciling", "simulated": false, "provider_request_id": null, "qr_payload": null, "failure_code": null, "created_at": "2026-11-25T00:04:49.424186Z"}` |
| `POST /sales/{sale}/attempts {qr}` con otra clave | 409 | `{"detail": "The sale already has an active payment attempt"}` |
| Servidor terminado con `kill -9` (PID 30457); `/health` sin respuesta | — | — |
| `GET /sales/{sale}` tras `kill -9` y reinicio | 200 | `{"id": "f0547570-e684-4e9c-97fb-0bed4c0790be", "merchant_id": "1ea19205-1619-4659-b100-16999db8b83c", "reference": "HWX4E6GC5R", "amount_cents": 30000, "currency": "MXN", "concept": null, "status": "open", "beneficiary_name": "Tienda Demo A SA de CV", "masked_account": "**************6782", "created_at": "2026-11-25T00:04:49.405801Z", "attempts": [{"id": "4e50edb4-c2a1-4730-af50-21b85fb270bf", "sale_id": "f0547570-e684-4e9c-97fb-0bed4c0790be", "sale_reference": "HWX4E6GC5R", "method": "qr", "status": "reconciling", "simulated": false, "provider_request_id": null, "qr_payload": null, "failure_code": null, "created_at": "2026-11-25T00:04:49.424186Z"}]}` |

Interfaz operativa tras el reinicio (`python -m tappy.sales reconciliations`):

```
attempt: 4e50edb4-c2a1-4730-af50-21b85fb270bf
sale reference: HWX4E6GC5R
attempt status: reconciling
reason: timeout
status: pending
run at: 2026-11-25T00:04:50.459022+00:00
```

**Caída a mitad de la llamada** — nuevo proceso con `TAPPY_PEY_TIMEOUT_SECONDS=20` y `TAPPY_ATTEMPT_CREATION_TIMEOUT_SECONDS=1`; el pey falso tarda 30 s y el servidor de Tappy se mata con `kill -9` mientras espera:

| Petición | Status | Respuesta |
| --- | --- | --- |
| `POST /sales/{other}/attempts {qr}` (pey tarda 30 s; el servidor de Tappy se mata con `kill -9` mientras espera) | — | sin respuesta |
| Servidor terminado con `kill -9` (PID 31634) mientras esperaba a pey | — | — |
| Estado del intento en la base tras la caída | — | ['creating'] |
| `GET /sales/{other}` tras recover-interrupted | 200 | `{"id": "2fff1027-d5cc-49b6-be2a-fdc219593048", "merchant_id": "a2980b94-2b41-4f3c-9372-6204b552fd77", "reference": "VX4E0CMBXD", "amount_cents": 1500, "currency": "MXN", "concept": null, "status": "open", "beneficiary_name": "Tienda Demo B", "masked_account": "**************0017", "created_at": "2026-11-25T00:05:24.552076Z", "attempts": [{"id": "d3ef737d-4377-4992-a3a3-4b511edf8abf", "sale_id": "2fff1027-d5cc-49b6-be2a-fdc219593048", "sale_reference": "VX4E0CMBXD", "method": "qr", "status": "reconciling", "simulated": false, "provider_request_id": null, "qr_payload": null, "failure_code": null, "created_at": "2026-11-25T00:05:24.564777Z"}]}` |

```
$ python -m tappy.sales recover-interrupted
1 interrupted attempt moved to reconciliation
$ python -m tappy.sales recover-interrupted
0 interrupted attempts moved to reconciliation
$ python -m tappy.sales reconciliations
attempt: d3ef737d-4377-4992-a3a3-4b511edf8abf
sale reference: VX4E0CMBXD
attempt status: reconciling
reason: interrupted_creation
status: pending
run at: 2026-11-25T00:05:30.331140+00:00
```

Comprobaciones: pey recibió una sola petición por intento (el reintento no la repitió); la clave aparece 0 veces en los logs; ningún intento quedó `failed`. Una primera ejecución del escenario de caída con timeout de 1 s no llegó a dejar el intento `creating` (Tappy registró el timeout antes del `kill -9`) y se repitió con el timeout de 20 s mostrado arriba. Datos y procesos eliminados al terminar. Estado VC01: **PASS**.

### Diferencias

| Superficie | Antes | Después | Clasificación | Decisión |
| --- | --- | --- | --- | --- |
| `POST /sales/{id}/attempts` con resultado incierto | `503` con `detail` | `202` con el intento `reconciling` | Cambio de contrato (status y cuerpo) | Aceptada: §10 de arquitectura («devuelve el ID local y la condición de conciliación»); aún no hay consumidores (B40) |
| Intento tras resultado incierto | `creating` sin trabajo | `reconciling` + `reconciliation_jobs` con motivo | Comportamiento | Aceptada (AC01/AC03) |
| Interfaz operativa | No existía | `python -m tappy.sales reconciliations` / `recover-interrupted` | Nuevo | Aceptada (UC03) |

## Checks

`uv run python -m quality.check` sobre `1e3096e` + `fb011e1` (con `.env` exportado): PASS format, lint, types (mypy strict), hygiene, migrations (upgrade/downgrade/upgrade + `alembic check`), tests (315 passed, Postgres real aislado), api (15 contratos sin diferencias); `evidence` B01–B15 APPROVED.

## Supresiones

Sin supresiones nuevas.

## Umbral

AC PASS / AC aplicables = 3/3 = **100%**.

## Review Standards/Spec

Pendiente.
