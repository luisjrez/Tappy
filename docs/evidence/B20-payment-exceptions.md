# Evidencia — B20 Conservar discrepancias como incidencia

Ticket: [#28](https://github.com/luisjrez/Tappy/issues/28) · Historia: [H5 #5](https://github.com/luisjrez/Tappy/issues/5) · Protocolo: [TICKET_QUALITY_PROTOCOL](../planning/TICKET_QUALITY_PROTOCOL.md) · Manifiesto: [B20-payment-exceptions.toml](B20-payment-exceptions.toml)

> Verificado con eventos sintéticos con la forma oficial de pey, firmados localmente, y con un pey falso local. **Sin pagos ni webhooks reales.** Nadie marca un cobro como recibido a mano; la resolución de incidencias por un revisor es B32.

## Revisiones y escenario

- Ticket, UC/AC/TC y comprobación: B20-UC01–UC03, B20-AC01–AC03, B20-TC01–TC03, B20-VC01.
- Modalidad: **antes/después** del tratamiento de la evidencia dudosa (antes: quedaba `unmatched` sin rastro y una transferencia propia de otro importe se perdía; después: incidencia, evento `review` y la transferencia propia verificada se conserva) y de `SaleResponse` (gana `exceptions`); **resultado inicial** para el comando `exceptions`.
- Cambios esperados en tests anteriores: el test de evidencia insuficiente de B18 fija por variante el estado del evento (`review` salvo un evento que no es de pago QR, `unmatched`), el del cobro y el importe confirmado (300.01 conserva 30001 en `review`); el de valores extremos y el de `transactionId` reutilizado esperan `review` (este último renombrado a `…opens_a_review`, con el manifiesto de B18 actualizado en el commit aparte `a988900`); el de B19 de otro importe con el mismo `transactionId` y el de B17 de un evento sin intento esperan `review`; el cuerpo exacto de B11 incluye `"exceptions": []`.
- Base: rama B19 `f55dab3` (PR #75), stack #68. Revisión evaluada: candidato `03e4b7d`.
- Entorno: macOS, Colima + Compose (Postgres 18), Python 3.14.8. Fecha: 2026-11-24 (UTC 2026-11-25). Ejecutor: sesión local de desarrollo del autor del PR.

## Diseño

- `payment_exceptions` (migración `0016`): cobro (opcional), transferencia (opcional), evento de origen, motivo, importe esperado y recibido, apertura y resolución; único por `(evento, motivo)` con `ON CONFLICT DO NOTHING`, así que reprocesar no duplica incidencias. `webhook_events.status` admite `review`.
- Motivos (`ExceptionReason`): `amount_mismatch`, `receiver_mismatch`, `unassociated`, `conflicting_transfer`, `incomplete_evidence`, `sale_not_open`.
- Refactor «separar recepción comprobada de cobertura de la venta»: `apply_evidence` asocia (sin aproximación: proveedor + `codiQrId` + id de intento si viene), clasifica dudas (`doubt`), registra la recepción (`record_reception`) y solo después decide la cobertura (`cover_sale`) o la incidencia (`flag`):
  - Sin asociación cierta → `unassociated` sin cobro (TC03).
  - Transferencia ya registrada: igual → `duplicate`; distinta → `conflicting_transfer`.
  - Cuenta distinta o ausente → `receiver_mismatch`, sin transferencia para el comercio (TC02). Datos incompletos → `incomplete_evidence`. Intento no pagable o cobro no `open` → `sale_not_open` (registrar esos pagos es B26).
  - Cuenta y QR propios con **otro importe** → se registra la transferencia real (dinero verificado del comercio), el cobro pasa a `review` (no `paid`) y se abre `amount_mismatch` con esperado/recibido (TC01). Un cobro en `review` no acepta intentos nuevos.
- Consulta: `GET /sales/{id}` muestra `exceptions`; `python -m tappy.sales exceptions` lista todas las abiertas (motivo, referencia o «unassociated», evento, importes, apertura). `process-events` informa también las que pasan a revisión.

## Trazabilidad UC → AC → TC → test

| UC | AC | TC | Test real | Resultado |
| --- | --- | --- | --- | --- |
| B20-UC01 | B20-AC01 | B20-TC01 | `test_a_short_own_transfer_is_kept_and_opens_an_incident_without_covering_the_sale` (25000 de 30000: cobro `review`, confirmado 25000, transferencia conservada, incidencia con esperado/recibido, intento no pagado, evento `review`); `test_an_over_payment_is_also_an_incident`; `test_a_sale_in_review_accepts_no_new_attempts` | PASS |
| B20-UC02 | B20-AC02 | B20-TC02 | `test_money_to_another_account_never_counts_for_the_merchant` (otra cuenta o sin cuenta: nada suma, 0 transferencias, `receiver_mismatch`); `test_a_transfer_id_already_used_with_other_data_opens_an_incident`; `test_incomplete_evidence_for_the_attempt_goes_to_review` | PASS |
| B20-UC03 | B20-AC03 | B20-TC03 | `test_unassociable_evidence_stays_in_review_without_approximate_association` (QR desconocido u otro id de intento: incidencia `unassociated` sin cobro, el cobro no se toca, reprocesar no la duplica, listada por el comando); `test_reprocessing_an_incident_never_duplicates_it_or_the_money` | PASS |

## TDD

| Comportamiento | Red | Green |
| --- | --- | --- |
| Incidencias, recepción propia, no asociación | 11 de 12 fallan antes de implementar: `KeyError: 'exceptions'` (×9) y `assert 'open' == 'review'` (×2); el que pasaba (`test_a_sale_in_review_accepts_no_new_attempts`) lo hacía porque el cobro ya no estaba abierto por otra vía | `PaymentException`, `flag`, `doubt`, `record_reception`/`cover_sale`, migración `0016` |
| Importe distinto | Mutación que cubre el cobro aunque el importe no coincida: falla TC01 | Cobertura solo con importe exacto |
| Receptor ajeno | Mutación sin comprobar la cuenta: fallan los 2 casos de TC02 | `receiver_mismatch` antes de registrar nada |

## B20-VC01 — Antes/después de las incidencias

Proceso real `python -m tappy` sobre `03e4b7d` con `TAPPY_PAYMENT_PROVIDER=pey` (pey falso local para los QR) y secreto de webhooks generado. Valores sintéticos.

| Paso | Status | Resultado |
| --- | --- | --- |
| Venta A antes | 200 | `{"status": "open", "amount_cents": 30000, "confirmed_amount_cents": 0, "transfers": [], "exceptions": []}` |
| A: transferencia propia de 250.00 (esperado 300.00) | 204 | `(sin cuerpo)` |
| Venta A después | 200 | `{"status": "review", "amount_cents": 30000, "confirmed_amount_cents": 25000, "transfers": [{"provider_transaction_id": "TX-ECCDDCC695", "amount_cents": 25000, "masked_account": "**************6782"}], "exceptions": [{"reason": "amount_mismatch", "expected_amount_cents": 30000, "received_amount_cents": 25000, "created_at": "2026-11-25T05:05:24.046128Z", "resolved_at": null}]}` |
| B: 300.00 hacia una cuenta ajena | 204 | `(sin cuerpo)` |
| Venta B después | 200 | `{"status": "open", "amount_cents": 30000, "confirmed_amount_cents": 0, "transfers": [], "exceptions": [{"reason": "receiver_mismatch", "expected_amount_cents": 30000, "received_amount_cents": 30000, "created_at": "2026-11-25T05:05:24.094041Z", "resolved_at": null}]}` |
| Pago con un QR desconocido (no asociable con certeza) | 204 | `(sin cuerpo)` |
| Venta C después (no se asocia por aproximación) | 200 | `{"status": "open", "amount_cents": 30000, "confirmed_amount_cents": 0, "transfers": [], "exceptions": []}` |
| Nuevo intento sobre A en revisión | 409 | `{"detail":"The sale is not open"}` |

Revisión y reproceso:

```
$ python -m tappy.sales exceptions
reason: amount_mismatch
sale reference: N0A9819WD3
event: msg_vc20_a
expected amount cents: 30000
received amount cents: 25000
opened at: 2026-11-25T05:05:24.046128+00:00

reason: receiver_mismatch
sale reference: 07K684YG73
event: msg_vc20_b
expected amount cents: 30000
received amount cents: 30000
opened at: 2026-11-25T05:05:24.094041+00:00

reason: unassociated
sale reference: unassociated
event: msg_vc20_c
expected amount cents: None
received amount cents: 30000
opened at: 2026-11-25T05:05:24.136678+00:00
$ # los tres eventos devueltos a received
$ python -m tappy.sales process-events
0 events applied, 0 unmatched, 2 in review, 1 duplicate, 0 failed
```

Estado final: `exceptions [('amount_mismatch', 1), ('receiver_mismatch', 1), ('unassociated', 1)] transfers (1, 25000) events [('duplicate', 1), ('review', 2)]`. Qué suma y qué no: A suma 25000 (dinero propio verificado) pero no queda cubierta (`review`, `amount_mismatch`); B no suma nada (cuenta ajena); el pago con QR desconocido no se asocia a ningún cobro. Reprocesar dejó las mismas tres incidencias y una sola transferencia (el evento de A pasa a `duplicate` porque su transferencia ya existe). **Antes** (B19): los tres eventos habrían quedado `unmatched` sin incidencia y la transferencia de 25000 no se habría registrado. Datos eliminados al terminar. Estado VC01: **PASS**.

### Contrato: `SaleResponse` (B19 → B20)

```diff
--- sale20_before.json	2026-11-24 23:06:09
+++ sale20_after.json	2026-11-24 23:06:09
@@ -39,6 +39,13 @@
       "title": "Currency",
       "type": "string"
     },
+    "exceptions": {
+      "items": {
+        "$ref": "#/components/schemas/ExceptionResponse"
+      },
+      "title": "Exceptions",
+      "type": "array"
+    },
     "id": {
       "title": "Id",
       "type": "string"
@@ -79,7 +86,8 @@
     "created_at",
     "attempts",
     "confirmed_amount_cents",
-    "transfers"
+    "transfers",
+    "exceptions"
   ],
   "title": "SaleResponse",
   "type": "object"
```

`ExceptionResponse`: `reason`, `expected_amount_cents`, `received_amount_cents`, `created_at`, `resolved_at`. Clasificación: aditiva compatible; el estado `review` del cobro ya existía en el contrato.

## Checks

`uv run python -m quality.check` sobre `03e4b7d` + `a988900` (con `.env` exportado): PASS format, lint, types (mypy strict), hygiene, migrations (upgrade/downgrade/upgrade + `alembic check`), tests (398 passed, Postgres real aislado), api (16 contratos sin diferencias); `evidence` B01–B19 APPROVED.

## Supresiones

Sin supresiones nuevas.

## Umbral

AC PASS / AC aplicables = 3/3 = **100%**.

## Review Standards/Spec

Pendiente.
