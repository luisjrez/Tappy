# Evidencia — B18 Confirmar una recepción exacta

Ticket: [#26](https://github.com/luisjrez/Tappy/issues/26) · Historia: [H5 #5](https://github.com/luisjrez/Tappy/issues/5) · Protocolo: [TICKET_QUALITY_PROTOCOL](../planning/TICKET_QUALITY_PROTOCOL.md) · Manifiesto: [B18-confirm-reception.toml](B18-confirm-reception.toml)

> Verificado con eventos sintéticos con la **forma oficial** del evento `codi.qr.payment_received` de pey, firmados localmente, y con el adaptador pey contra un pey falso local. **Ningún pago real ni webhook real de pey**: no demuestra integración bancaria real (B35). Nadie marca un cobro como recibido a mano: solo la evidencia validada lo confirma.

## Revisiones y escenario

- Ticket, UC/AC/TC y comprobación: B18-UC01–UC03, B18-AC01–AC03, B18-TC01–TC03, B18-VC01. Incluye el arrastre de B17 en [#26](https://github.com/luisjrez/Tappy/issues/26).
- Modalidad: **antes/después** para el detalle de cobro (pasa de `open`/`pending` a `paid` con transferencia; `SaleResponse` gana `received_amount_cents` y `transfers`) y para el estado del evento de B17 (antes quedaba `received`; ahora se aplica al guardarse: `applied` o `unmatched`); **resultado inicial** para la aplicación de evidencia y el comando `process-events`.
- Cambios esperados en tests anteriores: el cuerpo exacto del cobro (B11) incluye `received_amount_cents: 0` y `transfers: []`; el test de B14 que buscaba la palabra «received» comprueba ahora `received_amount_cents == 0` y `transfers == []` (el nombre del campo contiene la palabra); el test de B17 espera `unmatched` para un evento sin intento asociado.
- Base: rama B17 `d9f558d` (PR #73), stack #68. Revisión evaluada: candidato `4d1224b`.
- Entorno: macOS, Colima + Compose (Postgres 18), Python 3.14.8. Fecha: 2026-11-24 (UTC 2026-11-25). Ejecutor: sesión local de desarrollo del autor del PR.

## Diseño

- Traducción en la frontera (`tappy.payments.pey_events.evidence_from_pey`): del evento plano de pey a `PaymentEvidence` — `codiQrId`, `metadata.tappy_attempt_id`, `transactionId`, `bankAccountId`, `datePaid` (epoch → UTC) e importe en pesos leído como `Decimal` y convertido a centavos **solo si es exacto** (`300.005` → sin importe). Otros tipos de evento no son evidencia de QR (push/enlace llegan en B37/B39).
- Una única operación de aplicación (`tappy.sales.evidence.apply_evidence`, para eventos y conciliación): busca el intento por proveedor + `codiQrId` y lo bloquea, exige que el id de intento de `metadata` coincida si viene, bloquea el cobro (`FOR UPDATE` + `populate_existing`) y confirma solo si hay `transactionId`, el intento es pagable (`creating`/`pending`/`reconciling`/`expired`), el cobro está `open`, la cuenta es la cuenta para la que se emitió el QR y el importe es exactamente el del cobro. Entonces, en la misma transacción: inserta la transferencia, intento → `paid`, cobro → `paid`. Si algo falta o no coincide, nada cambia.
- `transactions` (migración `0014`): transferencia por `(provider, provider_transaction_id)` único, importe y moneda con checks, cuenta receptora, fecha de pago, recepción y evento de origen; un trigger impide cualquier modificación («recorded transfers are immutable»). `webhook_events.status` admite `applied` y `unmatched`.
- Procesamiento (`tappy.sales.receptions`): cada evento `received` se aplica en su propia transacción con `FOR UPDATE SKIP LOCKED`; el webhook lo intenta justo después de guardarlo (si falla, se registra en el log y el evento queda `received`, la respuesta sigue siendo `204` porque ya está guardado) y `python -m tappy.sales process-events` reprocesa los pendientes (informa aplicados, sin correspondencia y fallidos).
- Detalle: `GET /sales/{id}` muestra `received_amount_cents` y `transfers` (id de transacción del proveedor, importe, fecha de pago verificada y recepción).

## Trazabilidad UC → AC → TC → test

| UC | AC | TC | Test real | Resultado |
| --- | --- | --- | --- | --- |
| B18-UC01 | B18-AC01 | B18-TC01 | `test_exact_evidence_confirms_the_transfer_and_the_sale` (webhook exacto: cobro `paid`, recibido 30000, transferencia con id y fecha, intento `paid`, evento `applied`, 1 transferencia); `test_the_operations_command_applies_stored_events`; `test_epoch_seconds_are_read_as_utc`; `test_transfers_cannot_be_changed_once_recorded` | PASS |
| B18-UC02 | B18-AC02 | B18-TC02 | `test_insufficient_evidence_never_marks_the_sale_received` (9 casos: sin cuenta, otra cuenta, 300.01, 300.005, sin importe, QR desconocido, sin `transactionId`, otro id de intento, otro tipo de evento → cobro `open`, intento `pending`, evento `unmatched`, 0 transferencias); `test_an_invalid_signature_leaves_the_pending_attempt_untouched` (arrastre de B17) | PASS |
| B18-UC03 | B18-AC03 | B18-TC03 | `test_a_failure_inside_the_application_leaves_no_partial_state_and_reprocessing_completes` (un trigger temporal hace fallar la actualización del cobro: ni transferencia ni cambio de intento; al retirarlo, `process-events` aplica 1 y una segunda pasada 0) | PASS |

## TDD

| Comportamiento | Red | Green |
| --- | --- | --- |
| Confirmación, insuficiencia, fallo y comando | `assert 'open' == 'paid'`, `KeyError: 'received_amount_cents'` (no existía la aplicación ni los campos) | `evidence_from_pey`, `apply_evidence`, `Transfer`, procesamiento, CLI, migración `0014` |
| Atomicidad | Mutación con `db.commit()` tras insertar la transferencia: falla el test del fallo inducido (queda estado parcial) | Una sola transacción por evento |
| Importe exacto | Mutación sin la comprobación de importe: 3 casos de insuficiencia fallan | `evidence.amount_cents == sale.amount_cents` |

Durante el Green, los tests usaban intentos del simulador y quedaban `unmatched`: la correspondencia exige el mismo proveedor que emitió el QR, así que los tests crean el intento con el adaptador pey sobre el pey falso de B15 (como el flujo real).

## B18-VC01 — Antes/después de la recepción

Proceso real `python -m tappy` sobre `4d1224b` con `TAPPY_PAYMENT_PROVIDER=pey` (pey falso local para crear los QR) y `TAPPY_PEY_WEBHOOK_SECRET` generado por ejecución; los webhooks se firman localmente con la forma oficial del evento. Valores sintéticos sin normalizar.

| Paso | Status | Respuesta |
| --- | --- | --- |
| Antes: `GET /sales/{A}` | 200 | `{"id": "071be4e8-68b4-4ec2-ae46-88babb8f8225", "merchant_id": "ca985d5e-9076-4051-84e8-335fedf7da0e", "reference": "01DGD0M2K2", "amount_cents": 30000, "currency": "MXN", "concept": null, "status": "open", "beneficiary_name": "Tienda Demo A SA de CV", "masked_account": "**************6782", "created_at": "2026-11-25T00:55:35.971080Z", "attempts": [{"id": "d972b933-0e36-4fe2-92ab-07a21145bea1", "sale_id": "071be4e8-68b4-4ec2-ae46-88babb8f8225", "sale_reference": "01DGD0M2K2", "method": "qr", "status": "pending", "simulated": false, "provider_request_id": "QRVC01AAAA", "qr_payload": "{\"TYP\":1,\"v\":\"01\",\"ic\":0,\"IDC\":\"QRVC01AAAA\"}", "failure_code": null, "created_at": "2026-11-25T00:55:35.984427Z"}], "received_amount_cents": 0, "transfers": []}` |
| Webhook exacto para A (30000, cuenta y QR del intento) | 204 | `(sin cuerpo)` |
| Después: `GET /sales/{A}` | 200 | `{"id": "071be4e8-68b4-4ec2-ae46-88babb8f8225", "merchant_id": "ca985d5e-9076-4051-84e8-335fedf7da0e", "reference": "01DGD0M2K2", "amount_cents": 30000, "currency": "MXN", "concept": null, "status": "paid", "beneficiary_name": "Tienda Demo A SA de CV", "masked_account": "**************6782", "created_at": "2026-11-25T00:55:35.971080Z", "attempts": [{"id": "d972b933-0e36-4fe2-92ab-07a21145bea1", "sale_id": "071be4e8-68b4-4ec2-ae46-88babb8f8225", "sale_reference": "01DGD0M2K2", "method": "qr", "status": "paid", "simulated": false, "provider_request_id": "QRVC01AAAA", "qr_payload": "{\"TYP\":1,\"v\":\"01\",\"ic\":0,\"IDC\":\"QRVC01AAAA\"}", "failure_code": null, "created_at": "2026-11-25T00:55:35.984427Z"}], "received_amount_cents": 30000, "transfers": [{"provider_transaction_id": "TX-372B4C9AE26D", "amount_cents": 30000, "occurred_at": "2026-11-18T11:06:40Z", "received_at": "2026-11-25T00:55:36.036454Z"}]}` |
| Webhook para B con importe 150.01 (esperado 150.00) | 204 | `(sin cuerpo)` |
| Webhook para B sin `bankAccountId` | 204 | `(sin cuerpo)` |
| `GET /sales/{B}` tras evidencia insuficiente | 200 | `{"id": "bfd871bb-d176-47f0-8848-7cbe6141856e", "merchant_id": "ca985d5e-9076-4051-84e8-335fedf7da0e", "reference": "T3V2S1E808", "amount_cents": 15000, "currency": "MXN", "concept": null, "status": "open", "beneficiary_name": "Tienda Demo A SA de CV", "masked_account": "**************6782", "created_at": "2026-11-25T00:55:36.051044Z", "attempts": [{"id": "2bfc52c9-03c1-45fc-a9a4-5647990125e1", "sale_id": "bfd871bb-d176-47f0-8848-7cbe6141856e", "sale_reference": "T3V2S1E808", "method": "qr", "status": "pending", "simulated": false, "provider_request_id": "QRVC01BBBB", "qr_payload": "{\"TYP\":1,\"v\":\"01\",\"ic\":0,\"IDC\":\"QRVC01BBBB\"}", "failure_code": null, "created_at": "2026-11-25T00:55:36.057850Z"}], "received_amount_cents": 0, "transfers": []}` |
| (Trigger temporal que hace fallar toda actualización de `sales`) | — | — |
| Webhook exacto para C con un fallo inducido en la actualización del cobro | 204 | `(sin cuerpo)` |
| `GET /sales/{C}` tras el fallo | 200 | `{"id": "7a89492f-5d20-4d67-a15b-ab77057a1687", "merchant_id": "ca985d5e-9076-4051-84e8-335fedf7da0e", "reference": "Z8V0YBRMHH", "amount_cents": 2500, "currency": "MXN", "concept": null, "status": "open", "beneficiary_name": "Tienda Demo A SA de CV", "masked_account": "**************6782", "created_at": "2026-11-25T00:55:36.094716Z", "attempts": [{"id": "030ca79a-7d3f-4521-85cc-085c6db2e413", "sale_id": "7a89492f-5d20-4d67-a15b-ab77057a1687", "sale_reference": "Z8V0YBRMHH", "method": "qr", "status": "pending", "simulated": false, "provider_request_id": "QRVC01CCCC", "qr_payload": "{\"TYP\":1,\"v\":\"01\",\"ic\":0,\"IDC\":\"QRVC01CCCC\"}", "failure_code": null, "created_at": "2026-11-25T00:55:36.101327Z"}], "received_amount_cents": 0, "transfers": []}` |
| Estado tras el fallo | — | received , transferencias de C: 0 |
| `GET /sales/{C}` tras `process-events` | 200 | `{"id": "7a89492f-5d20-4d67-a15b-ab77057a1687", "merchant_id": "ca985d5e-9076-4051-84e8-335fedf7da0e", "reference": "Z8V0YBRMHH", "amount_cents": 2500, "currency": "MXN", "concept": null, "status": "paid", "beneficiary_name": "Tienda Demo A SA de CV", "masked_account": "**************6782", "created_at": "2026-11-25T00:55:36.094716Z", "attempts": [{"id": "030ca79a-7d3f-4521-85cc-085c6db2e413", "sale_id": "7a89492f-5d20-4d67-a15b-ab77057a1687", "sale_reference": "Z8V0YBRMHH", "method": "qr", "status": "paid", "simulated": false, "provider_request_id": "QRVC01CCCC", "qr_payload": "{\"TYP\":1,\"v\":\"01\",\"ic\":0,\"IDC\":\"QRVC01CCCC\"}", "failure_code": null, "created_at": "2026-11-25T00:55:36.101327Z"}], "received_amount_cents": 2500, "transfers": [{"provider_transaction_id": "TX-D775810358F4", "amount_cents": 2500, "occurred_at": "2026-11-18T11:06:40Z", "received_at": "2026-11-25T00:55:37.172067Z"}]}` |

Reproceso tras retirar el trigger:

```
$ python -m tappy.sales process-events
1 event applied, 0 unmatched, 0 failed
$ python -m tappy.sales process-events
0 events applied, 0 unmatched, 0 failed
```

Comprobaciones: estados finales de los eventos `applied`, `unmatched`, `unmatched`, `applied`; transferencias 30000 y 2500; el fallo quedó registrado una vez en el log del servidor («could not be applied; it stays received»); el secreto y la clave aparecen 0 veces en el log. Datos y procesos eliminados al terminar. Estado VC01: **PASS**.

### Diferencias

| Superficie | Antes (B17/B16) | Después | Clasificación | Decisión |
| --- | --- | --- | --- | --- |
| `GET /sales/{id}` | Sin campos de recepción; un pago nunca se reflejaba | `received_amount_cents` y `transfers`; `status` `paid` con evidencia exacta | Aditiva + comportamiento | Aceptada (AC01) |
| Evento guardado | Quedaba `received` | Se aplica al guardarse: `applied` / `unmatched`; `received` solo si la aplicación falló | Comportamiento | Aceptada (AC03: reproceso por comando) |

## Checks

`uv run python -m quality.check` sobre `4d1224b` (con `.env` exportado): PASS format, lint, types (mypy strict), hygiene, migrations (upgrade/downgrade/upgrade + `alembic check`), tests (365 passed, Postgres real aislado), api (16 contratos sin diferencias); `evidence` B01–B17 APPROVED.

## Supresiones

Sin supresiones nuevas.

## Umbral

AC PASS / AC aplicables = 3/3 = **100%**.

## Review Standards/Spec

Pendiente.
