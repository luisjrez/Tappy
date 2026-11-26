# Evidencia — B35 Verificar QR real de extremo a extremo

Ticket: [#43](https://github.com/luisjrez/Tappy/issues/43) · Historia: [H7 #7](https://github.com/luisjrez/Tappy/issues/7) · Protocolo: [TICKET_QUALITY_PROTOCOL](../planning/TICKET_QUALITY_PROTOCOL.md) · Manifiesto: [B35-real-qr-rehearsal.toml](B35-real-qr-rehearsal.toml)

> **Estado: BLOQUEADO.** No hay acceso autorizado a pey ni receptor habilitado, así que la prueba real (TC01) no se ejecutó. **El ensayo de este documento usa un pey falso y no demuestra la integración bancaria real.** No hay captura ni comprobante bancario, y ninguna parte de esta evidencia debe leerse como integración aprobada.

## Revisiones y escenario

- **Trazabilidad:** B35-UC01–UC03, B35-AC01–AC03 y B35-VC01. Superficie: recorrido externo y HTTP.
- **Modalidad:** resultado inicial. El ensayo y el procedimiento son nuevos.
- **Base y revisiones:**
  - Base: rama B34 `6a474a8` ([PR #110](https://github.com/luisjrez/Tappy/pull/110)).
  - Candidato: `b7760f9`.
- **Entorno:** macOS, Postgres 18.6 aislado (Colima + Compose), Python 3.14.8 y pey falso (`httpx2.MockTransport`). Fecha: 2026-11-25 (UTC). Ejecutor: sesión local de desarrollo del autor del PR.
- **Cambios de producción:** ninguno. El ensayo pasó contra el código existente, así que no hubo hallazgos que ajustar (Refactor: «ajustar únicamente lo demostrado por hallazgos»).

## Qué se entrega

- **Ensayo automatizado** (`tests/sales/test_rehearsal.py`): el mismo recorrido que la prueba real, contra un pey falso:
  1. Se crea la venta y su QR; el operador pierde la respuesta y repite con la misma `Idempotency-Key` (`200`, el mismo intento, una sola petición a pey).
  2. La aplicación se detiene y arranca otra vez sobre la misma base.
  3. pey notifica el pago, repite la misma notificación y la envía de nuevo con otro id.
  4. Una consulta de conciliación encuentra la misma transferencia.
  5. Detalle, historial y resumen diario muestran una sola recepción del importe acordado, sin incidencias, guardada bajo el entorno `test`.
- **Procedimiento de la prueba real** (README, «Real QR test»): requisitos que se deben confirmar por escrito, pasos manuales que nunca corren desde CI, y evidencia sanitizada en un archivo propio (`docs/evidence/B35-real-qr-run.md`), separada de este ensayo.

## Trazabilidad UC → AC → TC

| UC | AC | TC | Prueba | Resultado |
| --- | --- | --- | --- | --- |
| B35-UC01 | B35-AC01 | B35-TC01 | Externa y manual: QR real, pago del importe acordado y consulta de detalle, historial y resumen | **BLOCKED** (ver TC01) |
| B35-UC02 | B35-AC02 | B35-TC02 | Manual: preparar la ejecución sin acceso ni receptor habilitado. Resultado esperado: BLOCKED, y la simulación no se presenta como integración | PASS |
| B35-UC03 | B35-AC03 | B35-TC03 | `tests/sales/test_rehearsal.py::test_a_rehearsal_with_lost_responses_a_restart_and_repeated_evidence_keeps_one_reception` | PASS |

### B35-TC01 — prueba real bloqueada

No se ejecutó; nada se inventó. Requisitos sin cumplir al 2026-11-25:

1. **Acceso:** no hay API key ni secreto de webhook de pey autorizados. `TAPPY_PEY_API_KEY` y `TAPPY_PEY_WEBHOOK_SECRET` están vacíos en el entorno local.
2. **Ambiente:** pey no ha confirmado si existe un sandbox operativo; los términos lo describen y la documentación solo publica producción ([pey-validation.md](../research/pey-validation.md), pregunta 1).
3. **Receptor y titular:** falta confirmar qué cuenta y titular son elegibles, con cuenta propia por comercio y sin cuenta concentradora (pregunta 2, que «bloquea la prueba real hasta confirmarlo»).

Para desbloquearla, alguien del equipo autorizado debe conseguir esas confirmaciones y seguir el procedimiento del README. El resultado va en `docs/evidence/B35-real-qr-run.md`.

### B35-TC02 — preparación sin acceso

- Se preparó la ejecución: se revisaron los requisitos y se escribió el procedimiento.
- Resultado: **BLOCKED**, con los tres motivos de TC01. Este documento y el README lo dicen al principio.
- La simulación no se presenta como integración aprobada: el ensayo está marcado como pey falso, y el procedimiento exige que la prueba real deje su propia evidencia.

## TDD

- **Red:** el ensayo se escribió antes de cualquier cambio. Su primera ejecución falló por una expectativa mía, no por el código: esperaba `201` al repetir con la misma clave, y la API responde `200` (repetición de intentos documentada en B13). Corregida la expectativa, el ensayo pasa contra el código existente: no hubo hallazgos.
- **Refactor:** no hubo cambios de producción que ajustar.
- **Mutaciones** sobre el candidato, con `tests/sales/test_rehearsal.py`. Cada una se revierte:

```
M1 repeticion de QR ignorada: 1 failed in 0.62s
M2 mensaje repetido aplicado otra vez: 1 failed in 0.66s
M3 transferencia ya registrada no reconocida: 1 failed in 0.63s
M4 duplicado contado como nueva recepcion: 1 failed in 0.64s
```

- En una primera pasada sobrevivieron dos mutaciones sobre guardas de respaldo que solo actúan en carreras (`StoreOutcome.NEW` y la violación de unicidad de transferencias). Se cambiaron por las rutas que deduplican de verdad (estado `received` del evento y transferencia ya registrada). El ensayo ahora también comprueba que no se abra ninguna incidencia.

## Aplicabilidad por superficie

| Superficie | Aplica | Justificación |
| --- | --- | --- |
| API | Sí | Ensayo de crear, repetir, notificar, conciliar y consultar. Ningún contrato cambia |
| Recorrido externo real | Bloqueado | Sin acceso ni receptor (TC01) |
| Comandos | Sí | `backlog` después del ensayo |
| Panel | No aplica | El back office no cambia |

## B35-VC01 — ensayo y estado de la prueba real

**Prueba real: BLOCKED.** No hay captura bancaria, comprobante ni ejecución previa que mostrar.

**Ensayo** con pey falso, base aislada desechable y datos sintéticos:

**Antes del reinicio** (pey falso que emite el QR)

- POST /sales → 201 · `{"reference": "XPP35T6MM2", "amount_cents": 30000, "status": "open"}`
- POST /sales/{id}/attempts → 201 · `{"status": "pending", "provider_request_id": "AB12CD34EF"}`
- POST /sales/{id}/attempts (misma clave: respuesta perdida) → 200 · `{"status": "pending", "provider_request_id": "AB12CD34EF"}`
- Peticiones de creación recibidas por el pey falso: 1

**La aplicación se detiene y arranca otra vez sobre la misma base**

- POST /webhooks/pey (msg_rehearsal_1) → 204
- POST /webhooks/pey (msg_rehearsal_1) → 204
- POST /webhooks/pey (msg_rehearsal_2) → 204
- Consulta de conciliación a pey: `confirmed`, transferencias nuevas: 0
- GET /sales/{id} → 200 · `{"status": "paid", "confirmed_amount_cents": 30000, "transfers": 1, "exceptions": 0}`
- GET /sales → 200 · `[{"reference": "XPP35T6MM2", "status": "paid"}]`
- GET /merchants/{id}/summary/daily?date=2026-11-18 → 200 · `{"received_amount_cents": 30000, "transfer_count": 1, "covered_sale_count": 1, "open_exception_count": 0}`

**Base después del ensayo**

- transactions: 1 (entorno `test`)
- webhook_events: `msg_rehearsal_1:applied,msg_rehearsal_2:duplicate`

`backlog` (exit 0):

```
received webhook events: 0
due reconciliation jobs: 0
leased reconciliation jobs: 0 (0 with an expired lease)
exhausted reconciliation jobs: 0
attempts creating longer than 60 s: 0
open payment exceptions: 0
```

**Validación:**

- **TC03:**
  - la respuesta perdida se repite sin crear otro QR;
  - tras el reinicio, tres notificaciones y una consulta dejan una sola transferencia de 30000 centavos;
  - la venta queda `paid` en el detalle y en el historial, y el resumen cuenta 30000 una vez, sin incidencias;
  - todo queda bajo el entorno `test`, separado de cualquier ejecución real.
- **TC02:** el estado BLOCKED se muestra sin inventar ejecución.

Estado VC01: **PASS** para lo que aplica (ensayo y estado bloqueado declarado). La prueba real sigue BLOCKED.

## Checks

`uv run python -m quality.check` sobre `b7760f9`, con `.env` exportado:

- format, lint, types (mypy strict) y hygiene: PASS;
- migrations: PASS, sin migraciones nuevas;
- tests: PASS, 618 passed, con Postgres real aislado;
- api: PASS, 15 contratos sin diferencias;
- evidence: **FAIL a propósito.** B01–B34 están APPROVED, y B35 queda BLOCKED por TC01 (completitud 66.67 %, AC01 bloqueado). Por eso B35 va en un PR borrador fuera de la cadena del stack: su estado bloqueado no debe pintar de rojo los tickets siguientes, ni ocultarse para que el gate pase.

## Umbral

AC PASS / AC aplicables = 2/3 = **66.67 %**, por debajo del 97 %. **B35 no se puede aprobar ni cerrar** hasta ejecutar TC01 con acceso real autorizado.

## Review Standards/Spec

| Ronda | Revisión | Standards | Spec | Hallazgos |
| --- | --- | --- | --- | --- |
| 1 | `b7760f9` | PENDING | PENDING | — |
