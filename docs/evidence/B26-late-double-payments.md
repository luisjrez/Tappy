# Evidencia — B26 Registrar pago tardío y doble recepción

Ticket: [#34](https://github.com/luisjrez/Tappy/issues/34) · Historia: [H5 #5](https://github.com/luisjrez/Tappy/issues/5) · Protocolo: [TICKET_QUALITY_PROTOCOL](../planning/TICKET_QUALITY_PROTOCOL.md) · Manifiesto: [B26-late-double-payments.toml](B26-late-double-payments.toml)

> Verificado con eventos sintéticos que tienen la forma oficial de pey, firmados localmente, y con un pey falso local. **No hubo pagos ni webhooks reales.** Solo la evidencia verificada del proveedor suma dinero: ningún operador marca un cobro como recibido. Retirar una presentación no cancela nada en el banco.

## Revisiones y escenario

- **Trazabilidad:** B26-UC01–UC03, B26-AC01–AC03, B26-TC01–TC03 y B26-VC01.
- **Modalidad: antes/después.**
  - **Antes (B25):** una segunda transferencia propia para una venta que ya no estaba `open` abría `sale_not_open` y **no se registraba**: el dinero llegaba, pero no se contaba. El reintento seguía mostrando su QR aunque la venta ya estuviera cubierta.
  - **Después:** la transferencia se conserva, la venta queda `review` con `covered: true` y se abre `double_reception`. La presentación más nueva se retira.
  - Cambios en el contrato: `SaleResponse` gana `covered` y `AttemptResponse` gana `withdrawn_at`; `next_action` admite `hide_qr`.
- **Cambios esperados en tests anteriores:**
  - Los cuerpos exactos de B11, B13 y B14 incluyen los campos nuevos.
  - El test de B19 de unicidad por entorno insertaba una transferencia de otro entorno **para la misma venta**. Ahora esa recepción previa hace que la del entorno `test` sea una doble recepción: el evento queda `review` con `double_reception`. El punto del test se mantiene: la transferencia de `test` se registra una vez.
- **Base y revisiones:**
  - Base: rama B25 `8ae9a43` ([PR #81](https://github.com/luisjrez/Tappy/pull/81)), stack #68.
  - Candidato: `b3ca5c2`.
  - Correcciones de la review: `3fbced1`, revisión final. La VC01 se repitió sobre ella.
- **Entorno:** macOS, Colima + Compose (Postgres 18), Python 3.14.8. Fecha: 2026-11-25 (UTC). Ejecutor: sesión local de desarrollo del autor del PR.

## Diseño

Todo sigue pasando por la operación única `apply_evidence`, para webhooks y conciliación, sin reglas especiales por canal.

### Se registra toda recepción propia verificada

Si la evidencia se asocia con certeza a un intento, la cuenta es la del QR y los datos están completos, la transferencia se registra **aunque la venta ya no esté `open`**. Así se cumplen los arrastres de B18 y B20.

- Una cuenta ajena (`receiver_mismatch`) o datos incompletos nunca se registran.
- Un intento `failed`, que nunca tuvo QR, sigue en `sale_not_open` sin registro. `failed → paid` (§7) queda fuera del alcance: no es alcanzable, porque sin id de QR no hay evidencia asociable.
- Un `transactionId` repetido sigue siendo `duplicate` y no suma dos veces.

### Segunda recepción (`receive_again`)

Se aplica si la venta ya había recibido dinero: una transferencia previa leída bajo el lock de la venta.

- La transferencia se conserva y cuenta en `confirmed_amount_cents`: dos de 300.00 dan 600.00.
- Si es el importe exacto, ese intento pasa a `paid`; su QR fue pagado.
- La venta pasa a `review` («más de una transferencia bancaria distinta», §7).
- Se abre `double_reception` con el importe esperado y el recibido, y la transferencia vinculada.

Casos:

- el mismo QR pagado dos veces;
- el QR viejo pagado después de un reintento y luego el QR nuevo;
- el importe exacto después de uno corto (`amount_mismatch` + `double_reception`).

### Cobertura

`covered` es `true` cuando algún intento recibió el importe exacto (`paid`). Con solo una transferencia corta, queda `false`.

### Pago tardío al intento viejo

Un intento `expired`, aunque ya esté comprobado, sigue pudiendo pagarse (`expired → paid`, §7). Si la venta estaba `open`, queda cubierta.

### Retirada de la presentación

Cuando un intento pasa a `paid` (`pay_attempt`), los demás intentos activos de la venta reciben `withdrawn_at` y `next_action: hide_qr`.

- Su estado no cambia: no hay `failure_code` ni cancelación.
- Si su QR recibe un pago igualmente, se registra como doble recepción.
- Si es un intento `reconciling`, su trabajo sigue y aplica lo que encuentre.
- En una venta que ya no está `open`, los intentos no pagados sugieren `none`.

### Arrastres

| Origen | Requisito | Estado |
| --- | --- | --- |
| B18 | Registrar el segundo pago auténtico, abrir la doble recepción, cerrar o ajustar el intento activo | Cumplido: se registra, se abre `double_reception` y el intento activo se retira (o pasa a `paid` si su QR se pagó) |
| B20 | Registrar transferencias propias para ventas `paid`/`review`, mantener la incidencia y decidir qué pasa con el intento `pending` | Cumplido: se registran con `double_reception`, y el intento que recibe el importe exacto pasa a `paid` |
| B25 #1 | Intento nuevo activo cuando se paga el viejo | Cumplido: se retira (`hide_qr`) |
| B25 #2 | Pago en los últimos segundos tras `verified_at` | Cumplido: se registra como pago tardío o doble recepción |
| B25 #3 | `close_paid_jobs` | Sin cambios necesarios |

**Sin endpoint de resumen todavía:** el «resumen» del AC se verifica en el detalle (`confirmed_amount_cents`, `covered`, `status`, `exceptions`). Los reportes son otra historia.

## Trazabilidad UC → AC → TC → test

Todos los tests están en `tests/sales/test_late_payments.py`.

| UC | AC | TC | Test real | Resultado |
| --- | --- | --- | --- | --- |
| B26-UC01 | B26-AC01 | B26-TC01 | `test_an_authentic_payment_to_the_old_expired_attempt_covers_the_sale` | PASS |
| B26-UC02 | B26-AC02 | B26-TC02 | `test_a_second_distinct_transfer_is_kept_and_opens_a_double_reception` (60000, `review`, `covered`, `double_reception` con 30000/30000, 1 venta); `test_the_same_qr_paid_twice_keeps_both_transfers`; `test_an_exact_payment_after_a_short_one_is_kept_and_covers_the_sale_in_review`; `test_a_second_reception_found_by_reconciliation_is_kept_once`; `test_a_foreign_account_payment_for_a_paid_sale_is_never_recorded` | PASS |
| B26-UC03 | B26-AC03 | B26-TC03 | `test_the_newer_presentation_is_withdrawn_without_promising_cancellation`; `test_repeating_the_old_payment_never_duplicates_the_money`; `test_covering_through_a_second_reception_also_withdraws_newer_presentations`; `test_an_older_verified_attempt_suggests_nothing_once_the_sale_is_covered` | PASS |

## TDD

**Red de comportamiento:** los tests se escribieron antes del código y se corrieron contra la rama sin implementación. Fallan 5 de 6. El que pasaba (`repeating_the_old_payment…`) caracteriza la deduplicación de B19, que se conserva.

```
E       KeyError: 'covered'
E       assert 30000 == (2 * 30000)
E       assert 30000 == (2 * 30000)
E       assert 25000 == ((2 * 30000)
FAILED tests/sales/test_late_payments.py::test_an_authentic_payment_to_the_old_expired_attempt_covers_the_sale
FAILED tests/sales/test_late_payments.py::test_the_newer_presentation_is_withdrawn_without_promising_cancellation
FAILED tests/sales/test_late_payments.py::test_a_second_distinct_transfer_is_kept_and_opens_a_double_reception
FAILED tests/sales/test_late_payments.py::test_the_same_qr_paid_twice_keeps_both_transfers
FAILED tests/sales/test_late_payments.py::test_an_exact_payment_after_a_short_one_is_kept_and_covers_the_sale_in_review
5 failed, 1 passed in 3.43s
```

| Comportamiento | Red | Green |
| --- | --- | --- |
| Registro, doble recepción, cobertura y retirada | Ver arriba | `receive_again`, `double_reception` (`0021`), `covered`, `withdrawn_at`, `hide_qr` |
| Retirada también al cubrir por segunda recepción (review) | Falla `covering_through_a_second_reception…`: el reintento seguía con `show_qr` | `pay_attempt` retira siempre que un intento pasa a `paid` |
| Sugerencia en una venta cubierta (review) | Falla `older_verified_attempt_suggests_nothing…`: sugería `new_attempt` | `none` si la venta no está `open` |
| Mutaciones | Sin retirada: falla 1. Sin segunda recepción: fallan 3. Sin pasar a `paid` el intento exacto: fallan 2 | — |

## Aplicabilidad por superficie

| Superficie | Aplica | Justificación |
| --- | --- | --- |
| API | Sí | `covered`, `withdrawn_at`, `hide_qr`, `double_reception` y transferencias registradas |
| Comandos | Sí | `exceptions` lista `double_reception` |
| Panel | No aplica | Sin vistas en este alcance; la revisión de incidencias es H6 |

## B26-VC01 — Antes/después del pago tardío y la doble recepción

Proceso real `python -m tappy` con `TAPPY_PAYMENT_PROVIDER=pey`, `TAPPY_QR_EXPIRATION_SECONDS=360` y un secreto de webhooks generado al vuelo. Escenario:

1. Intento viejo A.
2. Vencimiento, con `expires_at` adelantado por SQL.
3. Comprobación real con `run-jobs`.
4. Reintento B.
5. Webhooks firmados: pago de A, el mismo pago reenviado con otro id de evento, y pago de B.

Valores sintéticos.

### Antes (B25 `8ae9a43`)

- Intento viejo (QR A) → 201 `{"status": "pending", "provider_request_id": "QRVC26A001", "previous_attempt_id": null, "late_payment_possible": false, "verified_at": null, "next_action": "show_qr"}`
- (se adelanta `expires_at` a «ahora − 1 s» por SQL para no esperar la ventana de 360 s)
- Lote programado: comprobación del vencido (`run-jobs`, exit 0): `pending attempts expired: 0 | jobs claimed: 1 | confirmed: 0, verified unpaid: 1, in review: 0, rescheduled: 0, exhausted: 0, lease lost: 0, failed: 0`
- Reintento (QR B) → 201 `{"status": "pending", "provider_request_id": "QRVC26B001", "previous_attempt_id": "6f07dcae…", "late_payment_possible": true, "verified_at": null, "next_action": "show_qr"}`
- Venta antes del pago tardío → 200 `{"status": "open", "covered": "—", "confirmed_amount_cents": 0, "transfers": [], "exceptions": [], "attempts": [{"qr": "QRVC26A001", "status": "expired", "next_action": "new_attempt", "withdrawn": false}, {"qr": "QRVC26B001", "status": "pending", "next_action": "show_qr", "withdrawn": false}]}`

**TC01 y TC03: pago auténtico al intento viejo vencido**

- Webhook: pago de QR A (TX-VC26-A) → 204
- Venta tras el pago tardío → 200 `{"status": "paid", "covered": "—", "confirmed_amount_cents": 30000, "transfers": ["TX-VC26-A"], "exceptions": [], "attempts": [{"qr": "QRVC26A001", "status": "paid", "next_action": "none", "withdrawn": false}, {"qr": "QRVC26B001", "status": "pending", "next_action": "show_qr", "withdrawn": false}]}`
- Webhook: misma transferencia TX-VC26-A reenviada con otro id de evento → 204
- Venta tras repetir la evidencia → 200 `{"status": "paid", "covered": "—", "confirmed_amount_cents": 30000, "transfers": ["TX-VC26-A"], "exceptions": [], "attempts": [{"qr": "QRVC26A001", "status": "paid", "next_action": "none", "withdrawn": false}, {"qr": "QRVC26B001", "status": "pending", "next_action": "show_qr", "withdrawn": false}]}`

**TC02: segunda transferencia distinta (QR B pagado igualmente)**

- Webhook: pago de QR B (TX-VC26-B) → 204
- Venta tras la doble recepción → 200 `{"status": "paid", "covered": "—", "confirmed_amount_cents": 30000, "transfers": ["TX-VC26-A"], "exceptions": ["sale_not_open"], "attempts": [{"qr": "QRVC26A001", "status": "paid", "next_action": "none", "withdrawn": false}, {"qr": "QRVC26B001", "status": "pending", "next_action": "show_qr", "withdrawn": false}]}`

Consultas a pey:
{"get": "/transaction/codi/qr/QRVC26A001", "nextToken": "first", "status": 200}

### Después (revisión final `3fbced1`)

- Intento viejo (QR A) → 201 `{"status": "pending", "provider_request_id": "QRVC26A001", "previous_attempt_id": null, "late_payment_possible": false, "verified_at": null, "next_action": "show_qr"}`
- (se adelanta `expires_at` a «ahora − 1 s» por SQL para no esperar la ventana de 360 s)
- Lote programado: comprobación del vencido (`run-jobs`, exit 0): `pending attempts expired: 0 | jobs claimed: 1 | confirmed: 0, verified unpaid: 1, in review: 0, rescheduled: 0, exhausted: 0, lease lost: 0, failed: 0`
- Reintento (QR B) → 201 `{"status": "pending", "provider_request_id": "QRVC26B001", "previous_attempt_id": "af839e8a…", "late_payment_possible": true, "verified_at": null, "next_action": "show_qr"}`
- Venta antes del pago tardío → 200 `{"status": "open", "covered": false, "confirmed_amount_cents": 0, "transfers": [], "exceptions": [], "attempts": [{"qr": "QRVC26A001", "status": "expired", "next_action": "new_attempt", "withdrawn": false}, {"qr": "QRVC26B001", "status": "pending", "next_action": "show_qr", "withdrawn": false}]}`

**TC01 y TC03: pago auténtico al intento viejo vencido**

- Webhook: pago de QR A (TX-VC26-A) → 204
- Venta tras el pago tardío → 200 `{"status": "paid", "covered": true, "confirmed_amount_cents": 30000, "transfers": ["TX-VC26-A"], "exceptions": [], "attempts": [{"qr": "QRVC26A001", "status": "paid", "next_action": "none", "withdrawn": false}, {"qr": "QRVC26B001", "status": "pending", "next_action": "hide_qr", "withdrawn": true}]}`
- Webhook: misma transferencia TX-VC26-A reenviada con otro id de evento → 204
- Venta tras repetir la evidencia → 200 `{"status": "paid", "covered": true, "confirmed_amount_cents": 30000, "transfers": ["TX-VC26-A"], "exceptions": [], "attempts": [{"qr": "QRVC26A001", "status": "paid", "next_action": "none", "withdrawn": false}, {"qr": "QRVC26B001", "status": "pending", "next_action": "hide_qr", "withdrawn": true}]}`

**TC02: segunda transferencia distinta (QR B pagado igualmente)**

- Webhook: pago de QR B (TX-VC26-B) → 204
- Venta tras la doble recepción → 200 `{"status": "review", "covered": true, "confirmed_amount_cents": 60000, "transfers": ["TX-VC26-A", "TX-VC26-B"], "exceptions": ["double_reception"], "attempts": [{"qr": "QRVC26A001", "status": "paid", "next_action": "none", "withdrawn": false}, {"qr": "QRVC26B001", "status": "paid", "next_action": "none", "withdrawn": true}]}`

Consultas a pey:
{"get": "/transaction/codi/qr/QRVC26A001", "nextToken": "first", "status": 200}

Validación:

- **TC01:** el pago auténtico al intento A vencido se conserva y cubre la venta (`paid`, `covered`, 30000).
- **TC03:**
  - B queda retirado (`hide_qr`) sin `failure_code` ni texto de cancelación.
  - Reenviar la misma transferencia no suma: sigue en 30000 con una sola transferencia.
- **TC02:** el pago de B se conserva (60000, dos transferencias), la venta queda `review` con `covered: true` y se abre `double_reception`.
- **Antes:**
  - B seguía mostrando su QR.
  - El segundo pago abría `sale_not_open` y no se registraba (30000 contados frente a 60000 recibidos).

Los datos se eliminaron al terminar. Estado VC01: **PASS**.

### Diferencias y decisión

| TC/AC | Antes (B25) | Después | Clasificación | Decisión |
| --- | --- | --- | --- | --- |
| TC01 | Venta cubierta | Venta cubierta y `covered: true` | Aditiva | Aceptada |
| TC02 | Segundo pago sin registrar (`sale_not_open`) | Registrado: 60000, `review`, `double_reception` | Comportamiento | Aceptada |
| TC03 | El reintento mostraba su QR | Se retira (`hide_qr`) sin cancelación; sin dinero duplicado | Comportamiento | Aceptada |

## Checks

`uv run python -m quality.check` sobre `3fbced1`, con `.env` exportado: PASS en todos los pasos.

- format, lint y types (mypy strict).
- hygiene.
- migrations: upgrade/downgrade/upgrade de `0021` + `alembic check`.
- tests: 488 passed, Postgres real aislado.
- api: 16 contratos sin diferencias.
- evidence: B01–B25 APPROVED.

## Supresiones

Sin supresiones nuevas.

## Umbral

AC PASS / AC aplicables = 3/3 = **100%**.

## Review Standards/Spec

| Ronda | Revisión | Standards | Spec | Hallazgos |
| --- | --- | --- | --- | --- |
| 1 | `b3ca5c2` | REQUEST_CHANGES | APPROVE | Ver detalle debajo de la tabla |
| 2 | `3fbced1` + `6298a6c` | APPROVE | APPROVE | Hueco corregido con `pay_attempt` y su test; sin hallazgos nuevos |

Detalle de la ronda 1, todo aplicado en `3fbced1` con Red/Green:

- **Standards:**
  - Cubrir la venta por una segunda recepción no retiraba las otras presentaciones.
  - El parámetro `sale` de `classify_doubt` ya no se usaba.
  - Había un `flush` redundante.
- **Spec:**
  - Tests nuevos: cuenta ajena en una venta pagada, doble recepción encontrada por conciliación, `covered: false` con solo un pago corto.
  - Un vencido comprobado sugería `new_attempt` en una venta cubierta.

Registrados sin cambio:

- `failed → paid` queda fuera del alcance porque no es alcanzable.
- Un sobrepago sigue siendo `amount_mismatch` sin cobertura, porque cubrir exige el importe exacto.

Hallazgos pendientes: 0.
