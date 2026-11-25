# Evidencia — B28 Compartir datos de comprobante verificado

Ticket: [#36](https://github.com/luisjrez/Tappy/issues/36) · Historia: [H6 #6](https://github.com/luisjrez/Tappy/issues/6) · Protocolo: [TICKET_QUALITY_PROTOCOL](../planning/TICKET_QUALITY_PROTOCOL.md) · Manifiesto: [B28-verified-receipt.toml](B28-verified-receipt.toml)

> Verificado con eventos sintéticos firmados localmente y con un pey falso local. Los «datos del pagador» son ficticios. **No hubo pagos reales** y no se genera PDF. El comprobante solo existe para una recepción validada.

## Revisiones y escenario

- **Trazabilidad:** B28-UC01–UC03, B28-AC01–AC03 y B28-VC01.
- **Modalidad: resultado inicial.**
  - `GET /sales/{id}/receipt` es nuevo.
  - La regla de cobertura queda compartida: el historial, el detalle y el comprobante usan la misma. El contrato no cambia.
- **Base y revisiones:**
  - Base: rama B27 `d0b79f9` ([PR #83](https://github.com/luisjrez/Tappy/pull/83)), stack #68.
  - Candidato: `43b3ac5`.
  - Notas de la review: `368696a`, revisión final. La VC01 se repitió sobre ella.
- **Entorno:** macOS, Colima + Compose (Postgres 18), Python 3.14.8. Fecha: 2026-11-25 (UTC). Ejecutor: sesión local de desarrollo del autor del PR.

## Diseño

### Solo para una recepción validada

`covering_reception` toma la transferencia exacta de un intento `paid`; si hay varias, la primera por `received_at`. Esa misma proyección decide:

- `covered` en el detalle;
- el comprobante;
- la condición SQL del historial, que comprueba transferencia exacta + intento `paid`.

Así no hay reglas de confirmación duplicadas.

Cuándo no hay comprobante:

- **Pendiente o pago corto:** `404` «The sale has no confirmed reception».
- **Venta ajena o inexistente:** `404` «Sale not found». El alcance se comprueba antes, así que el primer mensaje nunca revela ventas ajenas.
- **Recepción a una cuenta ajena:** nunca llega a ser una transferencia (B20).

### DTO con lista explícita de campos permitidos

| Grupo | Campos |
| --- | --- |
| Referencias | referencia de la venta, id de transacción de pey |
| Comercio | nombre del comercio, beneficiario y cuenta enmascarada de la instantánea |
| Importe | importe, moneda, concepto |
| Fechas | `paid_at` (`datePaid` de pey), `received_at` (servidor) |
| Estado | `simulated`, `under_review` |

- Con una doble recepción, el comprobante es el de la transferencia que cubre la venta, con `under_review: true`.
- Se construye solo desde `Transfer`, `Sale` y `Merchant`, nunca desde el payload del proveedor.
- Nunca incluye datos del pagador (CLABE, nombre, clave de rastreo), `apiKeyId`, credenciales ni identificadores completos de cuenta.

### Fuera de alcance

- La clave de rastreo SPEI no se guarda en `Transfer`. Se valorará cuando se diseñe un comprobante compartible.
- No hay test con `simulated: true`, porque un intento simulado no puede recibir evidencia de pey. El campo lo marca si alguna vez ocurriera.

## Trazabilidad UC → AC → TC → test

Todos los tests están en `tests/sales/test_receipts.py`.

| UC | AC | TC | Test real | Resultado |
| --- | --- | --- | --- | --- |
| B28-UC01 | B28-AC01 | B28-TC01 | `test_a_validated_own_transfer_produces_its_receipt` (45000: cuerpo exacto con importe, comercio, fechas y referencias); `test_a_double_reception_receipt_shows_the_covering_transfer_under_review`; `test_history_detail_and_receipt_agree_on_coverage` | PASS |
| B28-UC02 | B28-AC02 | B28-TC02 | `test_a_sale_without_a_confirmed_reception_has_no_receipt[pending\|short]`; `test_receipts_are_never_shown_for_another_merchant` (otro comercio e id inexistente `404`, administrador `200`, sin sesión `401`) | PASS |
| B28-UC03 | B28-AC03 | B28-TC03 | `test_the_receipt_keeps_useful_evidence_but_no_payer_data_or_secrets` (sí: transacción y referencia; no: CLABE, nombre y clave de rastreo del pagador, `apiKeyId`, API key, secreto de webhooks, id de cuenta y CLABE del receptor) | PASS |

## TDD

**Red:** los tests se escribieron antes del código. Fallan los 6 porque la ruta no existía.

```
E       assert 404 == <HTTPStatus.OK: 200>
E       assert 'TX-SENSITIVE' in '{"detail":"Not Found"}'
E       KeyError: 'provider_transaction_id'
FAILED tests/sales/test_receipts.py::test_a_validated_own_transfer_produces_its_receipt
FAILED tests/sales/test_receipts.py::test_a_sale_without_a_confirmed_reception_has_no_receipt[pending]
FAILED tests/sales/test_receipts.py::test_a_sale_without_a_confirmed_reception_has_no_receipt[short]
FAILED tests/sales/test_receipts.py::test_receipts_are_never_shown_for_another_merchant
FAILED tests/sales/test_receipts.py::test_the_receipt_keeps_useful_evidence_but_no_payer_data_or_secrets
FAILED tests/sales/test_receipts.py::test_a_double_reception_receipt_shows_the_covering_transfer_under_review
6 failed in 2.97s
```

| Comportamiento | Red | Green |
| --- | --- | --- |
| Comprobante, alcance y campos | Ver arriba | `read_receipt`, `ReceiptResponse`, `GET /sales/{id}/receipt` |
| Una sola regla de cobertura (review) | Test de consistencia entre historial, detalle y comprobante | `covering_reception`, y la misma condición en el historial |
| Mutaciones | Sin exigir importe exacto e intento pagado: falla `[short]`. Sin alcance: falla `never_shown_for_another_merchant` | — |

## Aplicabilidad por superficie

| Superficie | Aplica | Justificación |
| --- | --- | --- |
| API | Sí | Endpoint nuevo |
| Panel | No aplica | Sin vistas en este alcance |
| Comandos | No aplica | Sin comandos nuevos |

## B28-VC01 — Resultado inicial del comprobante

Proceso real `python -m tappy` con `TAPPY_PAYMENT_PROVIDER=pey` y un pey falso local. Los webhooks firmados llevan en `metadata` datos de pagador ficticios: CLABE, nombre y clave de rastreo. Revisión `368696a`. Valores sintéticos.

**TC01 y TC03: transferencia propia validada de 450.00 con datos sensibles del pagador en el evento**

- Intento QR → 201 `{"status": "pending", "provider_request_id": "QRVC28A001", "previous_attempt_id": null, "late_payment_possible": false, "verified_at": null, "next_action": "show_qr"}`
- Webhook firmado con CLABE, nombre y clave de rastreo del pagador en metadata → 204
- Comprobante → 200 `{"sale_id":"be0b698c-fcae-4158-ba50-b1ac45284f59","sale_reference":"2HYSE78JEY","merchant_name":"Tienda Demo A","beneficiary_name":"Tienda Demo A SA de CV","masked_account":"**************6782","amount_cents":45000,"currency":"MXN","concept":"Comida","provider_transaction_id":"01M3QR8H0RH0XBCKYYD242YXNV","paid_at":"2026-11-18T11:06:40Z","received_at":"2026-11-25T14:20:13.664653Z","simulated":false,"under_review":false}`
  - ¿Aparece CLABE del pagador? no
  - ¿Aparece nombre del pagador? no
  - ¿Aparece clave de rastreo? no
  - ¿Aparece apiKeyId? no
  - ¿Aparece id de cuenta del receptor? no
  - ¿Aparece CLABE del receptor? no

**TC02: cobro pendiente, importe distinto e identificador ajeno**

- Intento QR pendiente → 201 `{"status": "pending", "provider_request_id": "QRVC28B001", "previous_attempt_id": null, "late_payment_possible": false, "verified_at": null, "next_action": "show_qr"}`
- Comprobante de un cobro pendiente → 404 `{"detail":"The sale has no confirmed reception"}`
- Intento QR → 201 `{"status": "pending", "provider_request_id": "QRVC28C001", "previous_attempt_id": null, "late_payment_possible": false, "verified_at": null, "next_action": "show_qr"}`
- Webhook de 250.00 (importe distinto) → 204
- Comprobante con solo un pago corto → 404 `{"detail":"The sale has no confirmed reception"}`
- Operador B pidiendo el comprobante de A → 404 `{"detail":"Sale not found"}`
- Identificador inexistente → 404 `{"detail":"Sale not found"}`
- Sin sesión → 401

Validación:

- **TC01:** el comprobante de la transferencia validada de 450.00 trae la referencia, el comercio, el beneficiario con la cuenta enmascarada, el importe, el concepto, la transacción de pey y las fechas.
- **TC03:** no aparece ningún dato del pagador, ni `apiKeyId`, ni el id de cuenta, ni la CLABE del receptor.
- **TC02:**
  - Un cobro pendiente o con solo un pago corto da `404` «no confirmed reception».
  - El operador de otro comercio y un id inexistente dan `404` «Sale not found».
  - Sin sesión da `401`.

Los datos se eliminaron al terminar. Estado VC01: **PASS**.

## Checks

`uv run python -m quality.check` sobre `368696a`, con `.env` exportado: PASS en todos los pasos.

- format, lint y types (mypy strict).
- hygiene.
- migrations: sin migraciones nuevas.
- tests: 510 passed, Postgres real aislado.
- api: 16 contratos sin diferencias.
- evidence: B01–B27 APPROVED.

## Supresiones

Sin supresiones nuevas.

## Umbral

AC PASS / AC aplicables = 3/3 = **100%**.

## Review Standards/Spec

| Ronda | Revisión | Standards | Spec | Hallazgos |
| --- | --- | --- | --- | --- |
| 1 | `43b3ac5` | APPROVE | APPROVE | Sin violaciones ni defectos. Nota aplicada en `368696a`: una sola regla de cobertura para historial, detalle y comprobante (con test de consistencia); `covering_reception` devuelve también el intento. Registrados: falta un test con `simulated: true` (no alcanzable) y la clave de rastreo para un futuro comprobante compartible |

Hallazgos pendientes: 0.
