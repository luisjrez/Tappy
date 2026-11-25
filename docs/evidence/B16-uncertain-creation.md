# Evidencia — B16 Recuperar creación QR incierta

Ticket: [#24](https://github.com/luisjrez/Tappy/issues/24) · Historia: [H4 #4](https://github.com/luisjrez/Tappy/issues/4) · Protocolo: [TICKET_QUALITY_PROTOCOL](../planning/TICKET_QUALITY_PROTOCOL.md) · Manifiesto: [B16-uncertain-creation.toml](B16-uncertain-creation.toml)

> Verificado con el simulador y con un pey falso local que sirve la forma oficial del contrato; **no se llamó a pey real** (sin integración bancaria real demostrada). La conciliación efectiva de estos intentos (consultar a pey y resolver) es B22; la recuperación de trabajos tras reinicio con lease, B23.

## Revisiones y escenario

- Ticket, UC/AC/TC y comprobación: B16-UC01–UC03, B16-AC01–AC03, B16-TC01–TC03, B16-VC01. Incluye el arrastre de B14 en [#24](https://github.com/luisjrez/Tappy/issues/24) (fallo del proveedor que dejaba el intento `creating` activo y caída entre la llamada y el registro).
- Modalidad: **antes/después** para el resultado incierto de `POST /sales/{id}/attempts` (B14/B15 respondían `503` y dejaban el intento `creating`) y **resultado inicial** para los trabajos de conciliación y la interfaz operativa (`python -m tappy.sales`).
- Base: rama B15 `85786d1` (PR #71), stack de H4 #68. Revisiones: candidato `1e3096e` → correcciones de review `ad31e26` (revisión final; VC01 repetida sobre ella). Commit aparte `fb011e1`: el manifiesto de B15 sigue el test renombrado (`…keeps_the_attempt_creating` → `…keeps_the_attempt_reconciling`), con el precedente de B42/B06.
- Entorno: macOS, Colima + Compose (Postgres 18), Python 3.14.8. Fecha: 2026-11-24 (UTC 2026-11-25). Ejecutor: sesión local de desarrollo del autor del PR.
- Datos sintéticos (comercios «Tienda Demo A/B», CLABE ficticias, clave de prueba generada por ejecución).

## Diseño

- `ReconciliationJob` (migración `0012_reconciliation_jobs`): `attempt_id`, `reason` (`JobReason`: `timeout`, `connection`, `server_error`, `invalid_response`, `duplicate_provider_id`, `interrupted_creation`), `status` (`pending`/`done`), `run_at` y unicidad `(attempt_id, reason)` — un trabajo lógico por intento y razón. El lease y los reintentos los añadirá B23 cuando los use. El downgrade se niega si existen trabajos.
- Resultado incierto (`ProviderUnavailableError`: `timeout`, `connection`, `server_error`, `invalid_response`, `duplicate_provider_id`): en una transacción, el intento pasa de `creating` a `reconciling` y se crea su trabajo con el motivo como evidencia. La API responde **`202`** con el intento (id, referencia y estado), sin instrucciones para repetir el pago (§10 de arquitectura). Nunca se declara `failed` por falta de respuesta; `failed` sigue reservado a rechazos definitivos (`failure_code`, B15).
- Repetir con la misma `Idempotency-Key` devuelve el mismo intento (`200`) sin volver a llamar al proveedor; otra clave recibe `409` porque `reconciling` es activo.
- Caída entre la llamada al proveedor y el registro: el intento queda `creating`. `python -m tappy.sales recover-interrupted` mueve a `reconciling` (trabajo `interrupted_creation`) los intentos `creating` sin cambios desde hace más de `TAPPY_ATTEMPT_CREATION_TIMEOUT_SECONDS` (por defecto 60), con `FOR UPDATE SKIP LOCKED`; es idempotente. La configuración exige que ese umbral supere 4 × `TAPPY_PEY_TIMEOUT_SECONDS` (el timeout de httpx aplica por fase: conexión, escritura, lectura y pool), para no recuperar una llamada que todavía puede responder.
- Si aun así llega el QR de un intento ya movido a `reconciling` (sin id), se guarda su `provider_request_id` y payload como evidencia para B22, se deja aviso en el log y el intento sigue `reconciling` (la API responde `202`); nunca se descarta.
- Interfaz operativa: `python -m tappy.sales reconciliations` lista intentos y trabajos pendientes (intento, referencia, estado, motivo, `run_at`).
- Refactor («unificar errores definitivos e inciertos sin perder evidencia»): una sola salida en `request_attempt` con `AttemptOutcome` (`created`/`replayed`/`uncertain`) que el router traduce a `201`/`200`/`202` con una tabla; los motivos inciertos son `UncertainReason` en la frontera de proveedor y `JobReason` en el trabajo. Interfaz operativa alineada con el CLI de identidad (`parse`, código 1 ante configuración inválida); el listado usa un JOIN.

## Trazabilidad UC → AC → TC → test

| UC | AC | TC | Test real | Resultado |
| --- | --- | --- | --- | --- |
| B16-UC01 | B16-AC01 | B16-TC01 | `test_lost_response_leaves_the_attempt_reconciling_with_a_durable_job` (el proveedor recibió la orden y la respuesta se perdió: `202`, `reconciling`, referencia, sin id inventado; trabajo `timeout:pending`); `test_every_uncertain_outcome_is_kept_for_reconciliation` (`server_error`, `invalid_response`, `connection`); `test_uncertain_response_keeps_the_attempt_reconciling` (pey 201 sin id); `test_a_provider_id_already_linked_to_another_attempt_is_uncertain` | PASS |
| B16-UC02 | B16-AC02 | B16-TC02 | `test_retry_with_the_same_key_recovers_the_attempt_without_a_second_request` (misma clave → `200` mismo intento; otra clave → `409`; una sola orden al proveedor; 1 intento, 1 trabajo); `test_unavailable_provider_keeps_the_attempt_for_reconciliation` | PASS |
| B16-UC03 | B16-AC03 | B16-TC03 | `test_uncertainty_and_job_survive_a_restart_and_show_in_the_operations_command` (nueva instancia: sigue `reconciling`; el comando lista intento, referencia, motivo y `pending`; nada `failed`); `test_interrupted_creations_are_moved_to_reconciliation_by_the_operations_command`; `test_recent_creations_are_left_alone`; `test_recovery_runs_are_idempotent`; `test_a_late_qr_for_a_recovered_attempt_is_kept_as_evidence` (la recuperación ocurre durante la llamada: el QR tardío se guarda, el intento sigue `reconciling`, `202`); `test_creation_timeout_must_outlast_every_provider_timeout_phase` | PASS |

## TDD

| Comportamiento | Red | Green |
| --- | --- | --- |
| Resultado incierto, reintento, reinicio | `assert <HTTPStatus.SERVICE_UNAVAILABLE: 503> == <HTTPStatus.ACCEPTED: 202>`, `assert 'creating' == 'reconciling'` | `record_uncertain_qr` + `ReconciliationJob` + `202` |
| Interfaz operativa | Primero `No module named tappy.sales.__main__` (no es Red de comportamiento); con el esqueleto del CLI: `assert '1 interrupted attempt moved to reconciliation' in ''`, `assert 'creating' == 'reconciling'` | `recover_interrupted`, `pending_reconciliations`, CLI |

| QR tardío tras la recuperación (review) | `assert 201 == <HTTPStatus.ACCEPTED: 202>` (el id y el payload se descartaban) | `record_issued_qr` guarda la evidencia en intentos `reconciling` |
| Umbral frente al timeout de pey (review) | `Failed: DID NOT RAISE ValueError` | Validador `creation_outlasts_provider_calls` |

Cambios esperados en tests anteriores (antes/después): `test_unavailable_provider_fails_closed_and_keeps_the_reservation` (B14) → `test_unavailable_provider_keeps_the_attempt_for_reconciliation`; `test_uncertain_response_keeps_the_attempt_creating` (B15) → `…_reconciling`; `test_a_provider_id_already_linked_to_another_attempt_is_uncertain` ahora espera `202` y un trabajo `duplicate_provider_id`.

## B16-VC01 — Antes/después y recuperación real

**Antes** (última evidencia aprobada de [B15](B15-pey-qr.md), código `55c57e9`; la rama base `85786d1` solo añade su aprobación): respuesta incierta → `503 {"detail": "The QR provider is unavailable (invalid_response); the attempt is kept for reconciliation"}` y el intento `creating` (activo, sin trabajo).

**Después** — proceso real `python -m tappy` sobre `ad31e26` con `TAPPY_PAYMENT_PROVIDER=pey`, pey falso local en `127.0.0.1:8899`, `TAPPY_PEY_TIMEOUT_SECONDS=1` y `TAPPY_ATTEMPT_CREATION_TIMEOUT_SECONDS=5`; el pey falso acepta (registra la petición) y responde a los 3 s:

| Petición | Status | Respuesta |
| --- | --- | --- |
| `POST /sales/{sale}/attempts {qr}` con K (pey acepta y responde tras 3 s; timeout de Tappy 1 s) | 202 | `{"id": "1be2e89d-bdd7-4e1a-868c-cb1354994ad8", "sale_id": "69b23b1f-89ec-4696-97a5-fce309773ea9", "sale_reference": "VF95WNEP5Z", "method": "qr", "status": "reconciling", "simulated": false, "provider_request_id": null, "qr_payload": null, "failure_code": null, "created_at": "2026-11-25T00:15:09.529714Z"}` |
| `POST /sales/{sale}/attempts {qr}` con K (reintento) | 200 | `{"id": "1be2e89d-bdd7-4e1a-868c-cb1354994ad8", "sale_id": "69b23b1f-89ec-4696-97a5-fce309773ea9", "sale_reference": "VF95WNEP5Z", "method": "qr", "status": "reconciling", "simulated": false, "provider_request_id": null, "qr_payload": null, "failure_code": null, "created_at": "2026-11-25T00:15:09.529714Z"}` |
| `POST /sales/{sale}/attempts {qr}` con otra clave | 409 | `{"detail": "The sale already has an active payment attempt"}` |
| Servidor terminado con `kill -9` (PID 50048); `/health` sin respuesta | — | — |
| `GET /sales/{sale}` tras `kill -9` y reinicio | 200 | `{"id": "69b23b1f-89ec-4696-97a5-fce309773ea9", "merchant_id": "c040cceb-0b12-4527-91e2-0260c65513d7", "reference": "VF95WNEP5Z", "amount_cents": 30000, "currency": "MXN", "concept": null, "status": "open", "beneficiary_name": "Tienda Demo A SA de CV", "masked_account": "**************6782", "created_at": "2026-11-25T00:15:09.509066Z", "attempts": [{"id": "1be2e89d-bdd7-4e1a-868c-cb1354994ad8", "sale_id": "69b23b1f-89ec-4696-97a5-fce309773ea9", "sale_reference": "VF95WNEP5Z", "method": "qr", "status": "reconciling", "simulated": false, "provider_request_id": null, "qr_payload": null, "failure_code": null, "created_at": "2026-11-25T00:15:09.529714Z"}]}` |

Interfaz operativa tras el reinicio:

```
$ python -m tappy.sales reconciliations
attempt: 1be2e89d-bdd7-4e1a-868c-cb1354994ad8
sale reference: VF95WNEP5Z
attempt status: reconciling
reason: timeout
status: pending
run at: 2026-11-25T00:15:10.554468+00:00
```

**Caída a mitad de la llamada** — nuevo proceso con `TAPPY_PEY_TIMEOUT_SECONDS=2` y `TAPPY_ATTEMPT_CREATION_TIMEOUT_SECONDS=9` (cumple la nueva regla > 4 × timeout de pey); el pey falso tarda 30 s y el servidor de Tappy se mata con `kill -9` a ~1.2 s, mientras espera:

| Petición | Status | Respuesta |
| --- | --- | --- |
| `POST /sales/{other}/attempts {qr}` (Tienda Demo B; pey tarda 30 s) | — | el cliente recibe «Server disconnected without sending a response» al matar el servidor |
| Servidor terminado con `kill -9` (PID 50223) mientras esperaba a pey | — | — |
| Estado del intento de «Tienda Demo B» en la base tras la caída | — | ['creating'] |
| `GET /sales/{other}` tras recover-interrupted | 200 | `{"id": "f667ae3d-4bdd-4974-a3ac-6e806004eb83", "merchant_id": "1e55c0e7-76b0-4935-91cc-0daac0d82b4e", "reference": "JTZ3XCA2X4", "amount_cents": 1500, "currency": "MXN", "concept": null, "status": "open", "beneficiary_name": "Tienda Demo B", "masked_account": "**************0017", "created_at": "2026-11-25T00:15:14.733429Z", "attempts": [{"id": "3b555406-4a16-44d1-af6c-57aa2883255b", "sale_id": "f667ae3d-4bdd-4974-a3ac-6e806004eb83", "sale_reference": "JTZ3XCA2X4", "method": "qr", "status": "reconciling", "simulated": false, "provider_request_id": null, "qr_payload": null, "failure_code": null, "created_at": "2026-11-25T00:15:14.746734Z"}]}` |

```
$ python -m tappy.sales recover-interrupted   # antes de 9 s
0 interrupted attempts moved to reconciliation
$ python -m tappy.sales recover-interrupted   # después de 9 s
1 interrupted attempt moved to reconciliation
$ python -m tappy.sales recover-interrupted
0 interrupted attempts moved to reconciliation
$ python -m tappy.sales reconciliations
attempt: 1be2e89d-bdd7-4e1a-868c-cb1354994ad8
sale reference: VF95WNEP5Z
attempt status: reconciling
reason: timeout
status: pending
run at: 2026-11-25T00:15:10.554468+00:00

attempt: 3b555406-4a16-44d1-af6c-57aa2883255b
sale reference: JTZ3XCA2X4
attempt status: reconciling
reason: interrupted_creation
status: pending
run at: 2026-11-25T00:15:27.830765+00:00
```

Comprobaciones: pey recibió una sola petición por intento (el reintento no la repitió); la clave aparece 0 veces en los logs; ningún intento quedó `failed`; la recuperación respeta el umbral (0 antes de 9 s, 1 después) y es idempotente. El caso de un QR que llega tarde para un intento ya recuperado está cubierto por `test_a_late_qr_for_a_recovered_attempt_is_kept_as_evidence`. Una primera VC01 (sobre `1e3096e`) usó timeouts que la nueva regla ya no admite; esta tabla la sustituye. Datos y procesos eliminados al terminar. Estado VC01: **PASS**.

### Diferencias

| Superficie | Antes | Después | Clasificación | Decisión |
| --- | --- | --- | --- | --- |
| `POST /sales/{id}/attempts` con resultado incierto | `503` con `detail` | `202` con el intento `reconciling` | Cambio de contrato (status y cuerpo) | Aceptada: §10 de arquitectura («devuelve el ID local y la condición de conciliación»); aún no hay consumidores (B40) |
| Intento tras resultado incierto | `creating` sin trabajo | `reconciling` + `reconciliation_jobs` con motivo | Comportamiento | Aceptada (AC01/AC03) |
| Interfaz operativa | No existía | `python -m tappy.sales reconciliations` / `recover-interrupted` | Nuevo | Aceptada (UC03) |

## Checks

`uv run python -m quality.check` sobre `ad31e26` (con `.env` exportado): PASS format, lint, types (mypy strict), hygiene, migrations (upgrade/downgrade/upgrade + `alembic check`), tests (317 passed, Postgres real aislado), api (15 contratos sin diferencias); `evidence` B01–B15 APPROVED.

## Supresiones

Sin supresiones nuevas.

## Umbral

AC PASS / AC aplicables = 3/3 = **100%**.

## Review Standards/Spec

Pendiente.
