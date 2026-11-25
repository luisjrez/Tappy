# Evidencia — B18 Confirmar una recepción exacta

Ticket: [#26](https://github.com/luisjrez/Tappy/issues/26) · Historia: [H5 #5](https://github.com/luisjrez/Tappy/issues/5) · Protocolo: [TICKET_QUALITY_PROTOCOL](../planning/TICKET_QUALITY_PROTOCOL.md) · Manifiesto: [B18-confirm-reception.toml](B18-confirm-reception.toml)

> Verificado con eventos sintéticos con la **forma oficial** del evento `codi.qr.payment_received` de pey, firmados localmente, y con el adaptador pey contra un pey falso local. **Ningún pago real ni webhook real de pey**: no demuestra integración bancaria real (B35). Nadie marca un cobro como recibido a mano: solo la evidencia validada lo confirma.

## Revisiones y escenario

- Ticket, UC/AC/TC y comprobación: B18-UC01–UC03, B18-AC01–AC03, B18-TC01–TC03, B18-VC01. Incluye el arrastre de B17 en [#26](https://github.com/luisjrez/Tappy/issues/26).
- Modalidad: **antes/después** para el detalle de cobro (pasa de `open`/`pending` a `paid` con transferencia; `SaleResponse` gana `confirmed_amount_cents` y `transfers`) y para el estado del evento de B17 (antes quedaba `received`; ahora se aplica al guardarse: `applied` o `unmatched`); **resultado inicial** para la aplicación de evidencia y el comando `process-events`.
- Cambios esperados en tests anteriores: el cuerpo exacto del cobro (B11) incluye `confirmed_amount_cents: 0` y `transfers: []`; el test de B14 que buscaba la palabra «received» comprueba ahora `confirmed_amount_cents == 0` y `transfers == []` (`received_at` de las transferencias contiene la palabra); el test de B17 espera `unmatched` para un evento sin intento asociado.
- Base: rama B17 `d9f558d` (PR #73), stack #68. Revisiones: candidato `4d1224b` → correcciones de review `e6365fa` (VC01 repetida sobre ella) → `de0a0c2` (solo simplifica un tipo de excepción redundante).
- Entorno: macOS, Colima + Compose (Postgres 18), Python 3.14.8. Fecha: 2026-11-24 (UTC 2026-11-25). Ejecutor: sesión local de desarrollo del autor del PR.

## Diseño

- Traducción en la frontera (`tappy.payments.pey_events.evidence_from_pey`): del evento plano de pey a `PaymentEvidence` — `codiQrId`, `metadata.tappy_attempt_id`, `transactionId`, `bankAccountId`, `datePaid` (epoch → UTC) e importe en pesos leído como `Decimal` y convertido a centavos **solo si es exacto, finito y positivo** (`300.005` o `1e999999999` → sin importe); fechas fuera de rango → sin fecha. Otros tipos de evento no son evidencia de QR (push/enlace llegan en B37/B39).
- Una única operación de aplicación (`tappy.sales.evidence.apply_evidence`, para eventos y conciliación): busca el intento por proveedor + `codiQrId` y lo bloquea, exige que el id de intento de `metadata` coincida si viene, bloquea el cobro (`FOR UPDATE` + `populate_existing`) y confirma solo si hay `transactionId` y fecha de pago válida, el intento es pagable (`creating`/`pending`/`reconciling`/`expired`), el cobro está `open`, la cuenta es la cuenta para la que se emitió el QR y el importe es exactamente el del cobro. Entonces, en la misma transacción: inserta la transferencia (en un savepoint: si ese `transactionId` ya está registrado, la evidencia queda sin correspondencia en lugar de fallar), intento → `paid`, cobro → `paid`. Si algo falta o no coincide, nada cambia. El bloqueo del cobro reutiliza `held_sale` (compartido con la reserva de intentos).
- `transactions` (migración `0014`): transferencia por `(provider, provider_transaction_id)` único, importe y moneda con checks, cuenta receptora, fecha de pago, recepción y evento de origen; triggers impiden actualizar, borrar o truncar («recorded transfers are immutable»). `webhook_events.status` admite `applied` y `unmatched`.
- Procesamiento (`tappy.sales.receptions`): cada evento `received` se aplica en su propia transacción con `FOR UPDATE SKIP LOCKED`; el webhook lo intenta justo después de guardarlo (si falla, se registra en el log solo el id del evento y el tipo de error —el motor oculta los parámetros SQL con `hide_parameters=True`, para que no aparezcan cuentas ni importes— y el evento queda `received`; la respuesta sigue siendo `204` porque ya está guardado, también si falla la lectura posterior al guardado) y `python -m tappy.sales process-events` reprocesa los pendientes (informa aplicados, sin correspondencia y fallidos). Hoy se ejecuta a mano o de forma periódica; la programación y recuperación de trabajos es B23.
- Retención y acceso del payload crudo (que incluye datos del pagador) quedan como arrastre en [#42 (B34)](https://github.com/luisjrez/Tappy/issues/42); otros arrastres: evento anterior a la asociación ([#29, B21](https://github.com/luisjrez/Tappy/issues/29)), `transactionId` repetido ([#27, B19](https://github.com/luisjrez/Tappy/issues/27)) y pago de un intento vencido con otro activo ([#34, B26](https://github.com/luisjrez/Tappy/issues/34)).
- Detalle: `GET /sales/{id}` muestra `confirmed_amount_cents` (suma de transferencias confirmadas del cobro; distinto del «Importe recibido» por periodo del glosario) y `transfers` (id de transacción del proveedor, importe, fecha de pago verificada, recepción y el receptor verificado: beneficiario y cuenta enmascarada).

## Trazabilidad UC → AC → TC → test

| UC | AC | TC | Test real | Resultado |
| --- | --- | --- | --- | --- |
| B18-UC01 | B18-AC01 | B18-TC01 | `test_exact_evidence_confirms_the_transfer_and_the_sale` (webhook exacto: cobro `paid`, confirmado 30000, transferencia con id, fecha y receptor verificado, intento `paid`, evento `applied`, 1 transferencia); `test_the_operations_command_applies_stored_events`; `test_epoch_seconds_are_read_as_utc`; `test_transfers_cannot_be_changed_or_removed_once_recorded` (UPDATE, DELETE, TRUNCATE) | PASS |
| B18-UC02 | B18-AC02 | B18-TC02 | `test_insufficient_evidence_never_marks_the_sale_received` (10 casos: sin cuenta, otra cuenta, 300.01, 300.005, sin importe, QR desconocido, sin `transactionId`, otro id de intento, otro tipo de evento, sin fecha → cobro `open`, intento `pending`, evento `unmatched`, 0 transferencias); `test_an_invalid_signature_leaves_the_pending_attempt_untouched` (arrastre de B17); `test_extreme_values_are_treated_as_insufficient_not_as_failures`; `test_a_transaction_id_already_recorded_for_another_sale_is_unmatched` | PASS |
| B18-UC03 | B18-AC03 | B18-TC03 | `test_a_failure_inside_the_application_leaves_no_partial_state_and_reprocessing_completes` (un trigger temporal hace fallar la **última** escritura —el estado del evento—, después de escribir cobro, intento y transferencia: tras el fallo hay 0 transferencias, el intento sigue `pending` y el evento `received`; al retirarlo, `process-events` aplica 1 y una segunda pasada 0) | PASS |

## TDD

| Comportamiento | Red | Green |
| --- | --- | --- |
| Confirmación, insuficiencia, fallo y comando | `assert 'open' == 'paid'`, `KeyError: 'received_amount_cents'` (no existía la aplicación ni los campos) | `evidence_from_pey`, `apply_evidence`, `Transfer`, procesamiento, CLI, migración `0014` |
| Atomicidad | Mutación con `db.commit()` tras insertar la transferencia: falla el test del fallo inducido (queda estado parcial). Tras la review, el fallo se induce en la última escritura (antes fallaba en la primera); con el código ya correcto pasa directamente: refuerza la prueba, no es un Red nuevo | Una sola transacción por evento |
| Valores extremos, id repetido, borrado (review) | `assert 'received' in {'applied','unmatched'}` (el evento fallaba en cada pasada: `decimal.Overflow`, `OverflowError`, `IntegrityError`) y `DID NOT RAISE` para DELETE/TRUNCATE | Conversión robusta, savepoint en la transferencia, triggers de borrado/truncado |
| Fecha obligatoria (review) | `assert 'applied' == 'unmatched'` con `datePaid` inválido (se aplicaba sin fecha) | La evidencia exige fecha de pago válida |
| Importe exacto | Mutación sin la comprobación de importe: 3 casos de insuficiencia fallan | `evidence.amount_cents == sale.amount_cents` |

Durante el Green, los tests usaban intentos del simulador y quedaban `unmatched`: la correspondencia exige el mismo proveedor que emitió el QR, así que los tests crean el intento con el adaptador pey sobre el pey falso de B15 (como el flujo real).

## B18-VC01 — Antes/después de la recepción

Proceso real `python -m tappy` sobre `e6365fa` con `TAPPY_PAYMENT_PROVIDER=pey` (pey falso local para crear los QR) y `TAPPY_PEY_WEBHOOK_SECRET` generado por ejecución; los webhooks se firman localmente con la forma oficial del evento. Valores sintéticos sin normalizar.

| Paso | Status | Respuesta |
| --- | --- | --- |
| Antes: `GET /sales/{A}` | 200 | `{"id": "c587a042-c69a-4ed8-b86d-71850e000b38", "merchant_id": "5a6818a2-351a-4693-87da-a9aaa9109aba", "reference": "Z9R58ZQ4VV", "amount_cents": 30000, "currency": "MXN", "concept": null, "status": "open", "beneficiary_name": "Tienda Demo A SA de CV", "masked_account": "**************6782", "created_at": "2026-11-25T01:08:45.292693Z", "attempts": [{"id": "17236970-6b18-4845-ab32-f87e2bf2062c", "sale_id": "c587a042-c69a-4ed8-b86d-71850e000b38", "sale_reference": "Z9R58ZQ4VV", "method": "qr", "status": "pending", "simulated": false, "provider_request_id": "QRVC01AAAA", "qr_payload": "{\"TYP\":1,\"v\":\"01\",\"ic\":0,\"IDC\":\"QRVC01AAAA\"}", "failure_code": null, "created_at": "2026-11-25T01:08:45.306097Z"}], "confirmed_amount_cents": 0, "transfers": []}` |
| Webhook exacto para A (30000, cuenta y QR del intento) | 204 | `(sin cuerpo)` |
| Después: `GET /sales/{A}` | 200 | `{"id": "c587a042-c69a-4ed8-b86d-71850e000b38", "merchant_id": "5a6818a2-351a-4693-87da-a9aaa9109aba", "reference": "Z9R58ZQ4VV", "amount_cents": 30000, "currency": "MXN", "concept": null, "status": "paid", "beneficiary_name": "Tienda Demo A SA de CV", "masked_account": "**************6782", "created_at": "2026-11-25T01:08:45.292693Z", "attempts": [{"id": "17236970-6b18-4845-ab32-f87e2bf2062c", "sale_id": "c587a042-c69a-4ed8-b86d-71850e000b38", "sale_reference": "Z9R58ZQ4VV", "method": "qr", "status": "paid", "simulated": false, "provider_request_id": "QRVC01AAAA", "qr_payload": "{\"TYP\":1,\"v\":\"01\",\"ic\":0,\"IDC\":\"QRVC01AAAA\"}", "failure_code": null, "created_at": "2026-11-25T01:08:45.306097Z"}], "confirmed_amount_cents": 30000, "transfers": [{"provider_transaction_id": "TX-139711513D06", "amount_cents": 30000, "occurred_at": "2026-11-18T11:06:40Z", "received_at": "2026-11-25T01:08:45.358110Z", "beneficiary_name": "Tienda Demo A SA de CV", "masked_account": "**************6782"}]}` |
| Webhook para B con importe 150.01 (esperado 150.00) | 204 | `(sin cuerpo)` |
| Webhook para B sin `bankAccountId` | 204 | `(sin cuerpo)` |
| `GET /sales/{B}` tras evidencia insuficiente | 200 | `{"id": "33595ddc-d248-43b8-ac81-ee99d775fad6", "merchant_id": "5a6818a2-351a-4693-87da-a9aaa9109aba", "reference": "N44K50ABWQ", "amount_cents": 15000, "currency": "MXN", "concept": null, "status": "open", "beneficiary_name": "Tienda Demo A SA de CV", "masked_account": "**************6782", "created_at": "2026-11-25T01:08:45.372841Z", "attempts": [{"id": "f39a06b3-69dc-4de9-8728-0fc6947f7205", "sale_id": "33595ddc-d248-43b8-ac81-ee99d775fad6", "sale_reference": "N44K50ABWQ", "method": "qr", "status": "pending", "simulated": false, "provider_request_id": "QRVC01BBBB", "qr_payload": "{\"TYP\":1,\"v\":\"01\",\"ic\":0,\"IDC\":\"QRVC01BBBB\"}", "failure_code": null, "created_at": "2026-11-25T01:08:45.379686Z"}], "confirmed_amount_cents": 0, "transfers": []}` |
| (Trigger temporal que hace fallar la actualización del estado del evento, la última escritura de la aplicación) | — | — |
| Webhook exacto para C con un fallo inducido en la última escritura (estado del evento) | 204 | `(sin cuerpo)` |
| `GET /sales/{C}` tras el fallo | 200 | `{"id": "00fb5082-420d-43ed-8a74-11f024b3e2eb", "merchant_id": "5a6818a2-351a-4693-87da-a9aaa9109aba", "reference": "TQC76R7HFE", "amount_cents": 2500, "currency": "MXN", "concept": null, "status": "open", "beneficiary_name": "Tienda Demo A SA de CV", "masked_account": "**************6782", "created_at": "2026-11-25T01:08:45.416981Z", "attempts": [{"id": "ebed2f4a-a931-4a95-8a9d-402b9c242bc7", "sale_id": "00fb5082-420d-43ed-8a74-11f024b3e2eb", "sale_reference": "TQC76R7HFE", "method": "qr", "status": "pending", "simulated": false, "provider_request_id": "QRVC01CCCC", "qr_payload": "{\"TYP\":1,\"v\":\"01\",\"ic\":0,\"IDC\":\"QRVC01CCCC\"}", "failure_code": null, "created_at": "2026-11-25T01:08:45.423718Z"}], "confirmed_amount_cents": 0, "transfers": []}` |
| Estado tras el fallo | — | evento received ; transferencias de C: 0 ; intento de C: pending |
| `GET /sales/{C}` tras `process-events` | 200 | `{"id": "00fb5082-420d-43ed-8a74-11f024b3e2eb", "merchant_id": "5a6818a2-351a-4693-87da-a9aaa9109aba", "reference": "TQC76R7HFE", "amount_cents": 2500, "currency": "MXN", "concept": null, "status": "paid", "beneficiary_name": "Tienda Demo A SA de CV", "masked_account": "**************6782", "created_at": "2026-11-25T01:08:45.416981Z", "attempts": [{"id": "ebed2f4a-a931-4a95-8a9d-402b9c242bc7", "sale_id": "00fb5082-420d-43ed-8a74-11f024b3e2eb", "sale_reference": "TQC76R7HFE", "method": "qr", "status": "paid", "simulated": false, "provider_request_id": "QRVC01CCCC", "qr_payload": "{\"TYP\":1,\"v\":\"01\",\"ic\":0,\"IDC\":\"QRVC01CCCC\"}", "failure_code": null, "created_at": "2026-11-25T01:08:45.423718Z"}], "confirmed_amount_cents": 2500, "transfers": [{"provider_transaction_id": "TX-0ADAAD15B1A4", "amount_cents": 2500, "occurred_at": "2026-11-18T11:06:40Z", "received_at": "2026-11-25T01:08:46.489812Z", "beneficiary_name": "Tienda Demo A SA de CV", "masked_account": "**************6782"}]}` |

Reproceso tras retirar el trigger:

```
$ python -m tappy.sales process-events
1 event applied, 0 unmatched, 0 failed
$ python -m tappy.sales process-events
0 events applied, 0 unmatched, 0 failed
```

Comprobaciones: estados finales de los eventos `applied`, `unmatched`, `unmatched`, `applied`; transferencias 30000 y 2500; el fallo quedó registrado una vez en el log del servidor sin datos (`Webhook event 3774928f-1e72-4b22-b3c2-596183c2af20 could not be applied (ProgrammingError); it stays received`); el secreto y la clave aparecen 0 veces en el log. Datos y procesos eliminados al terminar. Estado VC01: **PASS**.

### Contrato: `SaleResponse` (B17 → B18)

```diff
--- sale18_before.json	2026-11-24 19:08:40
+++ sale18_after.json	2026-11-24 19:08:41
@@ -26,6 +26,10 @@
       ],
       "title": "Concept"
     },
+    "confirmed_amount_cents": {
+      "title": "Confirmed Amount Cents",
+      "type": "integer"
+    },
     "created_at": {
       "format": "date-time",
       "title": "Created At",
@@ -53,6 +57,13 @@
     },
     "status": {
       "$ref": "#/components/schemas/SaleStatus"
+    },
+    "transfers": {
+      "items": {
+        "$ref": "#/components/schemas/TransferResponse"
+      },
+      "title": "Transfers",
+      "type": "array"
     }
   },
   "required": [
@@ -66,7 +77,9 @@
     "beneficiary_name",
     "masked_account",
     "created_at",
-    "attempts"
+    "attempts",
+    "confirmed_amount_cents",
+    "transfers"
   ],
   "title": "SaleResponse",
   "type": "object"
```

`TransferResponse`: `provider_transaction_id`, `amount_cents`, `occurred_at`, `received_at`, `beneficiary_name`, `masked_account`. Clasificación: aditiva compatible.

### Diferencias

| Superficie | Antes (B17/B16) | Después | Clasificación | Decisión |
| --- | --- | --- | --- | --- |
| `GET /sales/{id}` | Sin campos de recepción; un pago nunca se reflejaba | `confirmed_amount_cents` y `transfers`; `status` `paid` con evidencia exacta | Aditiva + comportamiento | Aceptada (AC01) |
| Evento guardado | Quedaba `received` | Se aplica al guardarse: `applied` / `unmatched`; `received` solo si la aplicación falló | Comportamiento | Aceptada (AC03: reproceso por comando) |

## Checks

`uv run python -m quality.check` sobre `de0a0c2` (con `.env` exportado): PASS format, lint, types (mypy strict), hygiene, migrations (upgrade/downgrade/upgrade + `alembic check`), tests (372 passed, Postgres real aislado), api (16 contratos sin diferencias); `evidence` B01–B17 APPROVED.

## Supresiones

Sin supresiones nuevas.

## Umbral

AC PASS / AC aplicables = 3/3 = **100%**.

## Review Standards/Spec

| Ronda | Revisión | Standards | Spec | Hallazgos |
| --- | --- | --- | --- | --- |
| 1 | `4d1224b` + `b219aba` | CHANGES_REQUESTED | CHANGES_REQUESTED | Standards (hard): los fallos registraban parámetros SQL (cuentas, importes) en el log; faltaba el diff OpenAPI. Riesgos: transferencias borrables, eventos que fallaban para siempre (importes/fechas extremos, `transactionId` repetido), error tras guardar devolvía 500. Spec: el detalle no mostraba el receptor verificado; el fallo inducido ocurría en la primera escritura (no probaba el rollback tras escrituras reales); retención del payload y control de reintento sin tratar |
| 2 | `e6365fa` + `3506ef9` | APPROVE | APPROVE | `hide_parameters`, triggers de borrado/truncado, conversión robusta, savepoint, fecha obligatoria, receptor verificado por transferencia, fallo en la última escritura, arrastres a #27/#29/#34/#42. Menor aplicado en `de0a0c2` |

Hallazgos pendientes: 0.
