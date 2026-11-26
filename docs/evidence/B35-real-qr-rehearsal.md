# Evidencia — B35 Verificar QR real de extremo a extremo

Ticket: [#43](https://github.com/luisjrez/Tappy/issues/43) · Historia: [H7 #7](https://github.com/luisjrez/Tappy/issues/7) · Protocolo: [TICKET_QUALITY_PROTOCOL](../planning/TICKET_QUALITY_PROTOCOL.md) · Manifiesto: [B35-real-qr-rehearsal.toml](B35-real-qr-rehearsal.toml)

> **Estado: BLOQUEADO.** No hay acceso autorizado a pey ni receptor habilitado, así que la prueba real (TC01) no se ejecutó. **El ensayo de este documento usa un pey falso y no demuestra la integración bancaria real.** No hay captura ni comprobante bancario, y ninguna parte de esta evidencia debe leerse como integración aprobada.

## Revisiones y escenario

- **Trazabilidad:** B35-UC01–UC03, B35-AC01–AC03 y B35-VC01. Superficie: recorrido externo y HTTP.
- **Modalidad:** resultado inicial. El ensayo y el procedimiento son nuevos.
- **Base y revisiones:**
  - Base: rama B34 `6a474a8` ([PR #110](https://github.com/luisjrez/Tappy/pull/110)).
  - Candidato de la ronda 1: `b7760f9`.
  - Candidato de la ronda 2: `f1b05ab` (correcciones de la ronda 1).
- **Entorno:** macOS, Postgres 18.6 aislado (Colima + Compose), Python 3.14.8 y pey falso (`httpx2.MockTransport`). Fecha: 2026-11-25 (UTC). Ejecutor: sesión local de desarrollo del autor del PR.
- **Cambios de producción:** ninguno. El ensayo pasó contra el código existente, así que no hubo hallazgos que ajustar (Refactor: «ajustar únicamente lo demostrado por hallazgos»).

## Qué se entrega

- **Ensayo automatizado** (`tests/sales/test_rehearsal.py`): el mismo recorrido que la prueba real, contra un pey falso:
  1. Se crea la venta y su QR; el cliente reintenta con la misma `Idempotency-Key` (`200`, el mismo intento, una sola petición a pey).
  2. La aplicación se detiene y arranca otra vez sobre la misma base.
  3. pey notifica el pago, repite la misma notificación y la envía de nuevo con otro id.
  4. Una consulta de conciliación (una petición `GET` a pey) encuentra la misma transferencia: encontrada 1, duplicada 1, nueva 0.
  5. Detalle, historial y resumen diario muestran una sola recepción del importe acordado, sin incidencias, guardada bajo el entorno `test`.
- **Procedimiento de la prueba real** (README, «Real QR test»):
  - seis requisitos que se deben confirmar por escrito: acceso, receptor, ambiente de pey, webhook HTTPS registrado en pey, y ambiente `integration` de Tappy con base propia, respaldo y limpieza, más participantes e importe;
  - pasos manuales que nunca corren desde CI;
  - las tres comprobaciones abiertas que arrastra #43 (ver TC01);
  - evidencia sanitizada. El repositorio es público, así que el registro completo queda fuera de git. Solo se publica una comparación sanitizada en un archivo propio (`docs/evidence/B35-real-qr-run.md`), separada de este ensayo y correlacionada por `X-Request-ID` y la referencia de venta, con los últimos 4 caracteres de los ids de pey.
- **Pérdida de red entre Tappy y pey:** si se pierde la respuesta de pey, el intento queda en `creating` y pasa a conciliación. Eso ya lo cubren `tests/sales/test_uncertain_creation.py` (B16) y `tests/sales/test_pey_qr_flow.py` (B15), así que el ensayo cubre la pérdida del lado del cliente.

## Trazabilidad UC → AC → TC

| UC | AC | TC | Prueba | Resultado |
| --- | --- | --- | --- | --- |
| B35-UC01 | B35-AC01 | B35-TC01 | Externa y manual: QR real, pago del importe acordado y consulta de detalle, historial y resumen | **BLOCKED** (ver TC01) |
| B35-UC02 | B35-AC02 | B35-TC02 | Manual: preparar la ejecución sin acceso ni receptor habilitado. Resultado esperado: BLOCKED, y la simulación no se presenta como integración | PASS |
| B35-UC03 | B35-AC03 | B35-TC03 | `tests/sales/test_rehearsal.py::test_a_rehearsal_with_a_client_retry_a_restart_and_repeated_evidence_keeps_one_reception`. La parte «evidencia real posterior sanitizada y separada» queda definida por el procedimiento del README y por el entorno `test` comprobado en el ensayo | PASS |

### B35-TC01 — prueba real bloqueada

No se ejecutó; nada se inventó. Requisitos sin cumplir al 2026-11-25:

1. **Acceso:** no hay API key ni secreto de webhook de pey autorizados. `TAPPY_PEY_API_KEY` y `TAPPY_PEY_WEBHOOK_SECRET` están vacíos en el entorno local.
2. **Ambiente:** pey no ha confirmado si existe un sandbox operativo; los términos lo describen y la documentación solo publica producción ([pey-validation.md](../research/pey-validation.md), pregunta 1).
3. **Receptor y titular:** falta confirmar qué cuenta y titular son elegibles, con cuenta propia por comercio y sin cuenta concentradora (pregunta 2, que «bloquea la prueba real hasta confirmarlo»).

Comprobaciones abiertas que esta prueba debe responder. Siguen abiertas mientras TC01 esté bloqueado:

| Origen | Pregunta | Qué registrar |
| --- | --- | --- |
| B15 (#23) | ¿Un `429 CALL_LIMIT_REACHED` puede llegar a crear un QR? | Sí, no o desconocido. Un sí obliga a tratar el `429` como incierto |
| B33 (#41) | ¿Las cuotas 10/10/120 por minuto quedan por debajo de los límites de pey para la cuenta? | Los límites de pey y si cada cuota queda por debajo |
| B34 (#42) | ¿Los errores y webhooks de pey traen datos que la redacción no cubre? | Qué formato quedó visible, nunca el valor |

Para desbloquearla, alguien del equipo autorizado debe conseguir esas confirmaciones y seguir el procedimiento del README. La comparación sanitizada va en `docs/evidence/B35-real-qr-run.md`, y la línea «Status: blocked» del README se actualiza en el mismo cambio.

### B35-TC02 — preparación sin acceso

- Se preparó la ejecución: se revisaron los requisitos y se escribió el procedimiento.
- Resultado: **BLOCKED**, con los tres motivos de TC01. Este documento y el README lo dicen al principio.
- La simulación no se presenta como integración aprobada: el ensayo está marcado como pey falso, y el procedimiento exige que la prueba real deje su propia evidencia.

## TDD

- **Caracterización, no Red:** el ensayo se escribió antes de cualquier cambio y pasa contra el código existente.
  - Su primera ejecución falló por una expectativa mía, no por falta de comportamiento: esperaba `201` al reintentar con la misma clave, y la API responde `200` (repetición de intentos documentada en B13). Según el protocolo, eso no demuestra un Red.
  - No hubo hallazgos, así que no hubo cambios de producción (Refactor: «ajustar únicamente lo demostrado por hallazgos»).
- **Mutaciones**, que prueban que el ensayo detecta regresiones. Se aplicaron sobre `f1b05ab` con `tests/sales/test_rehearsal.py` y cada una se revierte:

```
M1 repeticion de QR ignorada: 1 failed in 0.65s
M2 mensaje repetido aplicado otra vez: 1 failed in 0.67s
M3 transferencia ya registrada no reconocida: 1 failed in 0.64s
M5 consulta de pey sin transacciones: 1 failed in 0.64s
M4 duplicado contado como nueva recepcion: 1 failed in 0.65s
```

- **Cambios de la ronda 1 en las mutaciones:**
  - En una primera pasada sobrevivieron dos mutaciones sobre guardas de respaldo que solo actúan en carreras (`StoreOutcome.NEW` y la violación de unicidad de transferencias). Se cambiaron por las rutas que deduplican de verdad: el estado `received` del evento y la transferencia ya registrada.
  - M5 (pey responde la consulta sin transacciones) habría sobrevivido a la aserción de la ronda 1, que solo miraba `(CONFIRMED, 0)`. Ahora el ensayo comprueba `found`, `duplicates` y `applied`, y la consulta única a pey.

## Aplicabilidad por superficie

| Superficie | Aplica | Justificación |
| --- | --- | --- |
| API | Sí | Ensayo de crear, repetir, notificar, conciliar y consultar. Ningún contrato cambia |
| Recorrido externo real | Bloqueado | Sin acceso ni receptor (TC01) |
| Comandos | Sí | `backlog` después del ensayo |
| Panel | No aplica | El back office no cambia |

## B35-VC01 — ensayo y estado de la prueba real

**Prueba real: BLOCKED.** No hay captura bancaria, comprobante ni ejecución previa que mostrar.

**Ensayo** con pey falso, base aislada desechable y datos sintéticos, sobre `f1b05ab`.

- **Reproducción:** el script local de la sesión repite los pasos de `tests/sales/test_rehearsal.py` e imprime cada respuesta. El test es la forma reproducible del mismo recorrido.
- **Cuerpos:** son extractos de los campos relevantes, no la respuesta completa.

**Antes del reinicio** (pey falso que emite el QR). Los cuerpos son extractos de los campos relevantes, no la respuesta completa.

- POST /sales → 201 · `{"reference": "S0W3CSMR61", "amount_cents": 30000, "status": "open"}`
- POST /sales/{id}/attempts → 201 · `{"status": "pending", "provider_request_id": "AB12CD34EF"}`
- POST /sales/{id}/attempts (reintento del cliente con la misma clave) → 200 · `{"status": "pending", "provider_request_id": "AB12CD34EF"}`
- Peticiones de creación recibidas por el pey falso: 1

**La aplicación se detiene y arranca otra vez sobre la misma base**

- POST /webhooks/pey (msg_rehearsal_1) → 204
- POST /webhooks/pey (msg_rehearsal_1) → 204
- POST /webhooks/pey (msg_rehearsal_2) → 204
- Consulta de conciliación a pey (1 petición GET): resultado `confirmed`, encontradas 1, duplicadas 1, nuevas 0
- GET /sales/{id} → 200 · `{"status": "paid", "confirmed_amount_cents": 30000, "len(transfers)": 1, "len(exceptions)": 0}`
- GET /sales → 200 · `[{"reference": "S0W3CSMR61", "status": "paid"}]`
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
  - tras el reinicio, tres notificaciones y una consulta que encuentra la misma transferencia dejan una sola, de 30000 centavos;
  - la venta queda `paid` en el detalle y en el historial, y el resumen cuenta 30000 una vez, sin incidencias;
  - todo queda bajo el entorno `test`, separado de cualquier ejecución real.
- **TC02:** el estado BLOCKED se muestra sin inventar ejecución.

Estado VC01: **PASS** para lo que aplica (ensayo y estado bloqueado declarado). La prueba real sigue BLOCKED.

## Checks

`uv run python -m quality.check` sobre `f1b05ab`, con `.env` exportado (en la ronda 1, sobre `b7760f9`, el resultado fue el mismo):

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
| 1 | `b7760f9` | REQUEST_CHANGES | REQUEST_CHANGES | Standards 1 + 3 notas, Spec 3 + 3 notas (ver abajo) |
| 2 | `f1b05ab` | PENDING | PENDING | — |

### Hallazgos de la ronda 1 y su corrección (`f1b05ab`)

**Standards**

1. La consulta de conciliación no demostraba que encontrara la transferencia: `(CONFIRMED, 0)` también pasa con una página vacía. Ahora se comprueban `found == 1`, `duplicates == 1`, `applied == 0` y una sola consulta a pey, y se añadió la mutación M5.
2. El conteo de `POST` filtraba en línea → `sum(...)`.
3. El README no decía cómo correr el ensayo → comando añadido.
4. «Respuesta perdida» describía en realidad un reintento del cliente → renombrado en el test, el README y esta evidencia. La pérdida entre Tappy y pey queda referida a B15/B16.

**Spec**

1. El procedimiento habría publicado identificadores bancarios reales en un repositorio público. Ahora el registro completo queda fuera de git y solo se publica una comparación sanitizada, con los últimos 4 caracteres, `X-Request-ID` y la referencia de venta. «Never commit» añade importe y hora exactos, clave de rastreo, `numRef` y `metadata`.
2. Faltaban las tres comprobaciones arrastradas a #43 (B15, B33 y B34) → son el paso 4 del procedimiento y una tabla en TC01.
3. Faltaban el webhook registrado en pey y un ambiente separado → requisitos 4 y 5, con `TAPPY_ENVIRONMENT=integration`, base propia, respaldo según B34 y limpieza.
4. Nota: «Red» era una caracterización → corregido.
5. Nota: los cuerpos de VC01 eran proyecciones → marcados como extractos, con conteos explícitos (`len(...)`) y la forma de reproducirlos.
6. Nota: la pérdida de red del lado de pey → documentada como cubierta por B15/B16.
