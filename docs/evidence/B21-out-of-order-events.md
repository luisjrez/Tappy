# Evidencia — B21 Procesar eventos anticipados y desordenados

Ticket: [#29](https://github.com/luisjrez/Tappy/issues/29) · Historia: [H5 #5](https://github.com/luisjrez/Tappy/issues/5) · Protocolo: [TICKET_QUALITY_PROTOCOL](../planning/TICKET_QUALITY_PROTOCOL.md) · Manifiesto: [B21-out-of-order-events.toml](B21-out-of-order-events.toml)

> Verificado con eventos sintéticos que tienen la forma oficial de pey, firmados localmente, y con un pey falso local que entrega el webhook antes de responder la creación del QR. **No hubo pagos ni webhooks reales.** Ningún operador marca un cobro como recibido: solo cubre un cobro la evidencia firmada y validada.

## Revisiones y escenario

- **Trazabilidad:** B21-UC01–UC03, B21-AC01–AC03, B21-TC01–TC03 y B21-VC01.
- **Modalidad: antes/después.** Cambia la secuencia de estados ante un pago anticipado.
  - Antes: el evento quedaba `unassociated` en `review` para siempre y el cobro seguía `open`.
  - Después: el evento se asocia o se reprocesa y el cobro termina `paid`. La API y los contratos no cambian (`api`: 16 contratos sin diferencias).
- **Arrastre de B18 ([comentario en #29](https://github.com/luisjrez/Tappy/issues/29)):** distinguir «sin asociación todavía» de «no coincide» y reintentar cuando aparezca la asociación, también para intentos en `reconciling` sin id. Ambos quedan cubiertos (ver Diseño).
- **Base y revisiones:**
  - Base: rama B20 `b80cb1e` ([PR #76](https://github.com/luisjrez/Tappy/pull/76)), stack #68.
  - Candidato: `2ecd31a` + `94fd7f0`.
  - Correcciones de la review: `bf0b852` (ronda 1) y `2aa67c3` (notas de la ronda 2), revisión final. La VC01 se repitió sobre ella.
- **Entorno:** macOS, Colima + Compose (Postgres 18), Python 3.14.8. Fecha: 2026-11-24 (UTC 2026-11-25). Ejecutor: sesión local de desarrollo del autor del PR.

## Diseño

### Asociación diferida (`tappy.sales.evidence`)

Si ningún intento tiene el `codiQrId` del evento, se intenta asociar por el id de intento que Tappy envía a pey en `metadata.tappy_attempt_id` (B15 ya lo enviaba). El intento debe:

- ser del mismo proveedor;
- no tener todavía id de QR;
- estar en `creating` o `reconciling` (`AWAITING_QR_STATUSES`).

Si cumple, adopta ese `codiQrId` y el evento se aplica con las mismas validaciones de B18–B20: cuenta, importe exacto y transacción.

Casos que nunca se asocian:

- un intento con **otro** id de QR;
- un intento `failed` o `expired`.

En esos casos se mantiene `unassociated`, igual que en B20, sin asociación aproximada.

### Reproceso de eventos en espera (`tappy.sales.receptions.apply_waiting_events`)

- Las incidencias `unassociated` guardan el `codiQrId` de su evidencia. La migración `0017` añade la columna `provider_request_id` y un índice parcial sobre las abiertas. Además rellena el campo en las incidencias abiertas existentes a partir del cuerpo de su evento, solo si `codiQrId` es texto de 1–64 caracteres.
- Al registrar el id de QR (`record_issued_qr`), se reaplican los eventos en espera con ese id. Solo se resuelven (`resolved_at`, `sale_id`) los que ahora se asocian con certeza; el evento toma el estado del resultado (`applied`, `review`…).
- «Sin asociación todavía» se reintenta. «No coincide» (otro intento u otro QR) sigue abierta.

### Carrera respuesta ↔ evento

- Ambos caminos toman primero un `pg_advisory_xact_lock` sobre `proveedor:codiQrId`, luego el intento (`FOR UPDATE`) y después el cobro.
- Si el evento llega mientras se guarda la respuesta, espera y luego encuentra el id. Si llega antes, deja su incidencia y la respuesta la reprocesa al obtener el lock.
- El orden de locks es el mismo en todos los caminos. Los eventos en espera ya están en `review`, y `process_event` solo bloquea los `received`, así que no hay ciclo.

### Transiciones con control de versión (`tappy.sales.transitions`)

- Hay una sola tabla `ALLOWED_TRANSITIONS`, con las salidas permitidas de los estados de intento del §7 de [arquitectura](../02-arquitectura.md).
- Excepción: `failed → paid`, que el §7 condiciona a abrir incidencia, queda para el pago tardío (B26).
- `move()` es el único punto que cambia el estado. `PAYABLE_ATTEMPT_STATUSES` se deriva de la tabla.
- `PaymentAttempt` conserva su `version_id_col`, así que la escritura tiene control de versión optimista además del lock.

Refactor «retirar condicionales duplicados»:

- rechazo, incertidumbre, conciliación de interrumpidos y cobertura usan `move()`, y los `if status is CREATING` desaparecen;
- `request_attempt` decide el código de respuesta por el estado final (`settled_reservation`).

### Respuesta tardía o distinta

- Si la respuesta trae el mismo id que el intento ya pagado, solo completa el `qr_payload`: `paid` no vuelve a `pending`.
- Si trae otro id que el adoptado, se registra un warning y se trata como `duplicate_provider_id` (mismo mecanismo que B15): el intento `creating` pasa a `reconciling`, y uno `paid` no cambia.
- Un timeout o un rechazo posteriores al pago tampoco degradan el intento. La solicitud responde `201` con el intento `paid`.

## Trazabilidad UC → AC → TC → test

Todos los tests están en `tests/sales/test_out_of_order.py`.

| UC | AC | TC | Test real | Resultado |
| --- | --- | --- | --- | --- |
| B21-UC01 | B21-AC01 | B21-TC01 | `test_a_payment_event_before_the_creation_response_ends_confirmed` (cobro e intento `paid`, `codiQrId` y `qr_payload` guardados, 1 transferencia, evento `applied`, sin incidencias); `test_an_attempt_in_reconciliation_without_a_qr_id_adopts_a_later_event` (arrastre de B18); `test_an_early_short_payment_keeps_the_sale_in_review_and_the_qr_is_still_recorded`; `test_a_failed_attempt_never_adopts_an_event`; `test_a_response_with_another_qr_than_the_adopted_one_goes_to_reconciliation` | PASS |
| B21-UC02 | B21-AC02 | B21-TC02 | `test_a_late_pending_response_never_degrades_a_paid_attempt` (el intento ya es `paid` antes de la respuesta; tras ella sigue `paid` y responde `201`); `test_a_late_response_with_another_qr_never_re_associates_a_paid_attempt`; `test_a_payment_before_a_creation_timeout_is_reported_as_created_and_paid` | PASS |
| B21-UC03 | B21-AC03 | B21-TC03 | `test_an_unassociable_early_event_is_applied_once_the_reference_exists` (evento sin metadata: `unassociated` → al registrar el id, 1 transferencia, evento `applied`, incidencia resuelta); `test_an_event_without_metadata_racing_the_creation_response_is_applied` (carrera determinista con `wait_until_blocked_on_a_lock`); `test_an_event_naming_an_attempt_that_has_another_qr_is_never_adopted`; `test_waiting_references_are_backfilled_for_existing_exceptions` | PASS |

En pey, «evento pendiente» corresponde a la respuesta de creación con el QR pendiente de pago: pey no emite webhooks de estado pendiente para QR, según `docs/research/pey-validation.md`. TC02 lo ejercita así. `paid` no tiene salidas en la tabla, y además `attach_issued_qr` solo avanza a `pending` un intento `creating`.

## TDD

| Comportamiento | Red | Green |
| --- | --- | --- |
| TC01–TC03 y pago anticipado con importe distinto | Tests ejecutados contra la base `b80cb1e`: 5 de 6 fallan. Fallos: `assert 'open' == 'paid'` (×2), `assert <AttemptStatus.PENDING> is <AttemptStatus.PAID>`, `assert 'open' == 'review'` y `Failed: the request never waited for a row lock`. El que pasaba (`…another_qr_is_never_adopted`) caracteriza la regla de B20, que se conserva | `adopting_attempt`, `apply_waiting_events`, migración `0017` |
| Carrera sin metadata | Se escribió después de la primera implementación. Falló (`the request never waited for a row lock`) y la mutación que quita el lock consultivo lo vuelve a romper | `hold_reference` en ambos caminos |
| Tabla de transiciones | `ModuleNotFoundError: tappy.sales.transitions` | `ALLOWED_TRANSITIONS`/`move`. El test unitario de la tabla se retiró en la review porque replicaba la implementación; se cubre por la API |
| `reconciling` sin id y timeout tras pago | `assert 202 == 201` frente al candidato `2ecd31a` | `settled_reservation` |
| Review: intento `failed`, respuesta con otro id, relleno de la migración | Mutaciones: sin el filtro de estado falla `…failed_attempt_never_adopts…`; con la respuesta distinta ignorada fallan los 2 tests `another_qr`; sin relleno, `[None, None]` | Filtro `AWAITING_QR_STATUSES`, `duplicate_provider_id`, `UPDATE … FROM webhook_events` |

## Aplicabilidad por superficie

| Superficie | Aplica | Justificación |
| --- | --- | --- |
| API | Sí | La secuencia de estados en `POST /sales/{id}/attempts` y `GET /sales/{id}` cambia. Los esquemas no cambian |
| Panel | No aplica | No hay vistas en este alcance |
| Comandos | Sí, sin cambios | `process-events` y `exceptions` reflejan el resultado. No hay comandos nuevos |

## B21-VC01 — Antes/después del pago anticipado

Proceso real `python -m tappy` con `TAPPY_PAYMENT_PROVIDER=pey` y un secreto de webhooks generado al vuelo. El pey falso local, al recibir `POST /codi/qr`, primero entrega a Tappy el webhook firmado `codi.qr.payment_received` (`204`) y solo después responde `201` con el QR.

- Venta A: el evento lleva la `metadata` que Tappy envió.
- Venta B: el evento no lleva metadata.

Los valores son sintéticos (cobro de 300.00).

**Antes** (base `b80cb1e`):

| Paso | Status | Resultado |
| --- | --- | --- |
| A: pago con metadata antes de la respuesta de creación | 201 | `{"sale": "open", "confirmed_amount_cents": 0, "attempt": "pending", "provider_request_id": "QRBEFOREAAAAA", "qr_payload": true, "transfers": 0, "exceptions": []}` |
| B: pago sin metadata antes de la respuesta de creación | 201 | `{"sale": "open", "confirmed_amount_cents": 0, "attempt": "pending", "provider_request_id": "QRBEFOREBBBBB", "qr_payload": true, "transfers": 0, "exceptions": []}` |

```
events [('msg_QRBEFOREAAAAA', 'review'), ('msg_QRBEFOREBBBBB', 'review')]
exceptions [('unassociated', False), ('unassociated', False)]
transfers (0, 0)
```

**Después** (revisión final `2aa67c3`; idéntico sobre `bf0b852`):

| Paso | Status | Resultado |
| --- | --- | --- |
| A: pago con metadata antes de la respuesta de creación | 201 | `{"sale": "paid", "confirmed_amount_cents": 30000, "attempt": "paid", "provider_request_id": "QRAFTERAAAAA", "qr_payload": true, "transfers": 1, "exceptions": []}` |
| B: pago sin metadata antes de la respuesta de creación | 201 | `{"sale": "paid", "confirmed_amount_cents": 30000, "attempt": "paid", "provider_request_id": "QRAFTERBBBBB", "qr_payload": true, "transfers": 1, "exceptions": [["unassociated", true]]}` |

```
events [('msg_QRAFTERAAAAA', 'applied'), ('msg_QRAFTERBBBBB', 'applied')]
exceptions [('unassociated', True)]
transfers (2, 60000)
{"qr_id": "QRAFTERAAAAA", "webhook_before_response": 204, "metadata": true}
{"qr_id": "QRAFTERBBBBB", "webhook_before_response": 204, "metadata": false}
$ python -m tappy.sales process-events
0 events applied, 0 unmatched, 0 in review, 0 duplicates, 0 failed
$ python -m tappy.sales exceptions
No open payment exceptions
```

**Transiciones observadas:**

- A: `creating` → `paid` por el evento. La respuesta tardía `pending` llega con el intento ya `paid`, solo completa el QR y no lo degrada.
- B: `creating` → evento `unassociated` → la respuesta registra el id (`pending`) → reproceso → `paid`. La incidencia queda resuelta y vinculada al cobro.
- Reprocesar no cambia nada: 0 eventos pendientes y 0 incidencias abiertas.

Los datos se eliminaron al terminar. Estado VC01: **PASS**.

### Diferencias y decisión

| TC/AC | Antes (B20) | Después | Clasificación | Decisión |
| --- | --- | --- | --- | --- |
| TC01/AC01: pago antes de la respuesta | Evento `review`/`unassociated` sin fin, cobro `open` | Evento `applied`, cobro `paid`, QR guardado | Comportamiento | Aceptada |
| TC02/AC02: respuesta `pending` tardía | No aplicaba: el pago nunca se confirmaba | El intento sigue `paid` y responde `201` | Comportamiento | Aceptada |
| TC03/AC03: evento no asociable | `unassociated` permanente | Reproceso al registrar el id, 1 transferencia, incidencia resuelta | Comportamiento | Aceptada |
| Contratos API | — | Sin diferencias | Ninguna | Aceptada |

## Checks

`uv run python -m quality.check` sobre `2aa67c3`, con `.env` exportado: PASS en todos los pasos.

- format, lint y types (mypy strict).
- hygiene.
- migrations: upgrade/downgrade/upgrade de `0017` + `alembic check`.
- tests: 412 passed, Postgres real aislado.
- api: 16 contratos sin diferencias.
- evidence: B01–B21 APPROVED.

## Supresiones

Sin supresiones nuevas.

## Umbral

AC PASS / AC aplicables = 3/3 = **100%**.

## Review Standards/Spec

| Ronda | Revisión | Standards | Spec | Hallazgos |
| --- | --- | --- | --- | --- |
| 1 | `2ecd31a` + `94fd7f0` | REQUEST_CHANGES | REQUEST_CHANGES | Ver detalle debajo de la tabla |
| 2 | `bf0b852` + `e7b20cb` | APPROVE | APPROVE | Todos los hallazgos de la ronda 1 corregidos o justificados. Notas aplicadas en `2aa67c3`: helper compartido `conflicting_qr` para el warning, rama inalcanzable de `adopting_attempt` retirada, relleno de `0017` limitado a eventos `pey`, redacción de TC02 corregida |

Detalle de la ronda 1, todo corregido en `bf0b852`:

- La adopción también alcanzaba intentos `failed`/`expired`.
- Una respuesta de creación con otro id se descartaba en silencio. Ahora pasa a conciliación con warning.
- La tabla de transiciones era más estrecha que el §7. Ahora lo refleja, salvo `failed → paid` (B26).
- TC02 no ejercía la transición `paid → pending`.
- Faltaba rellenar las incidencias previas a `0017`.
- Notas aplicadas:
  - renombrado a `adopting_attempt`;
  - test unitario que replicaba la tabla, retirado;
  - escenario del doble de proveedor agrupado en `Scenario`;
  - la condición de `record_issued_qr` se separó en dos casos explícitos.
- No aplicadas, con motivo:
  - `attempt_provider` hace una consulta extra: evita cambiar la firma pública de `record_issued_qr`.
  - Ambos casos («sin asociación todavía» y «no coincide») mantienen el motivo `unassociated` de B20: el reintento ya los distingue, y añadir un motivo nuevo excede B21.

Hallazgos pendientes: 0.
