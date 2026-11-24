# Evidencia — B14 Mostrar QR pendiente con proveedor simulado

Ticket: [#22](https://github.com/luisjrez/Tappy/issues/22) · Historia: [H4 #4](https://github.com/luisjrez/Tappy/issues/4) · Protocolo: [TICKET_QUALITY_PROTOCOL](../planning/TICKET_QUALITY_PROTOCOL.md) · Manifiesto: [B14-simulated-qr.toml](B14-simulated-qr.toml)

> **Simulación.** Todo QR de este ticket sale del simulador local (`"simulated": true`, payload `SIMULATED-CODI-QR|…`): no es un QR CoDi, no puede pagarse y **no demuestra integración bancaria real**. La integración con pey es B15 y la verificación real de extremo a extremo es B35.

## Revisiones y escenario

- Ticket, UC/AC/TC y comprobación: B14-UC01–UC03, B14-AC01–AC03, B14-TC01–TC03, B14-VC01.
- Modalidad: **resultado inicial** para el QR simulado (flujo nuevo) y **antes/después** para el intento QR de B13: antes quedaba en `creating` sin payload ([B13-VC01](B13-attempt-reservation.md#b13-vc01--resultado-inicial-de-api-e-interrupción)), ahora pasa a `pending` con ID y payload; `AttemptResponse` gana campos (diff abajo). Contratos aprobados sin diferencias.
- Cambios esperados en tests de B13: los que comprueban el estado `creating` (reserva, reinicio) usan ahora el canal `phone`, que todavía no llama a ningún proveedor; el INSERT directo del test del índice copia las columnas nuevas.
- Base: rama B13 `0a0cb9c` (PR #69), stack de H4 #68. Revisión evaluada: candidato `e8b4f54`.
- Entorno: macOS, Colima + Compose (Postgres 18), Python 3.14.8. Fecha: 2026-11-24. Ejecutor: sesión local de desarrollo del autor del PR.
- Datos: comercio «Tienda Demo A», identidades sintéticas, receptor ficticio (`bank-account-demo-a`).

## Diseño

- Frontera de proveedor por capacidades (`tappy.payments.provider`): `QrProvider` (`name`, `simulated`, `create_qr(QrOrder) -> IssuedQr`), `QrOrder` (intento, importe en centavos, concepto, cuenta del proveedor) e `IssuedQr` (ID del proveedor y payload). El simulador (`tappy.payments.simulator.SimulatedQrProvider`) implementa esa frontera; los tests lo inyectan en `create_app` (como el reloj) para fijar «Q1», sin simular módulos internos. `TAPPY_PAYMENT_PROVIDER` elige el proveedor (`simulated` es el único valor hasta B15).
- Flujo en `request_attempt`: (1) transacción corta que reserva el intento `creating` y lo confirma; (2) llamada al proveedor **fuera** de toda transacción; (3) transacción que bloquea el intento (`FOR UPDATE` + `populate_existing`) y, si sigue `creating`, guarda `provider_request_id`, el payload exacto y pasa a `pending` (con `version`). Una repetición con la misma clave devuelve el intento guardado sin llamar al proveedor.
- Migración `0010_attempt_provider_fields`: `provider`, `simulated`, `receiver_account` (instantánea de la cuenta del proveedor usada por el intento), `provider_request_id`, `qr_payload` y unicidad `(provider, provider_request_id)`.
- Arrastre de B10: el intento guarda la cuenta del proveedor que usa y la reserva exige que el receptor vigente coincida con la instantánea del cobro (beneficiario y últimos 4 dígitos); si se reconfiguró, `409` y no se llama al proveedor, para que el pagador nunca vea un beneficiario distinto del cobro.
- Sin pago implícito: el cobro sigue `open`, el intento `pending`; no existen campos de recepción ni transferencias. `phone`/`link` quedan reservados hasta B36/B38. Un fallo del proveedor deja el intento `creating` recuperable; su tratamiento (incertidumbre, conciliación) es B16.

## Trazabilidad UC → AC → TC → test

| UC | AC | TC | Test real | Resultado |
| --- | --- | --- | --- | --- |
| B14-UC01 | B14-AC01 | B14-TC01 | `test_creating_a_qr_returns_the_simulated_payload_pending` (payload exacto, ID Q1, `simulated: true`, `pending`; el proveedor recibió importe, concepto, cuenta e intento); `test_stored_qr_keeps_the_exact_payload_and_identifier`; `test_default_simulator_issues_distinct_labelled_identifiers`; `test_reservation_is_committed_before_the_provider_is_called`; `test_qr_is_refused_when_the_receiver_changed_after_the_sale`; `test_other_channels_stay_reserved_without_calling_the_qr_provider`; `test_provider_setting_selects_the_simulator_and_rejects_unknown_values` | PASS |
| B14-UC02 | B14-AC02 | B14-TC02 | `test_simulated_acceptance_never_shows_a_payment` (cobro `open`, intento `pending`; la respuesta no contiene «paid», «received» ni «transaction») | PASS |
| B14-UC03 | B14-AC03 | B14-TC03 | `test_repeating_or_reopening_the_session_reuses_the_same_qr` (repetir con la misma clave → 200 mismo QR; cerrar sesión, volver a entrar y leer → mismo intento; otra clave → 409; el simulador recibió una sola orden; 1 intento) | PASS |

## TDD

| Comportamiento | Red | Green |
| --- | --- | --- |
| QR simulado, payload, etiqueta, repetición | Con la frontera y el simulador creados pero sin conectar al flujo, 7 de 7 fallan: `assert ['creating'] == ['pending']`, `assert 0 == 1` (el simulador no recibía órdenes), `KeyError: 'simulated'`/`'qr_payload'` | `request_attempt` (reserva → proveedor → registro), migración `0010`, campos en la respuesta |
| Selección por configuración | `ImportError: cannot import name 'provider_from'` (aún no existía; error de importación, no de comportamiento) y después Green directo | `payment_provider` + `provider_from` |
| Receptor cambiado tras el cobro | Escrito tras implementar la regla; mutación sin `ensure_same_receiver`: `assert 201 == <HTTPStatus.CONFLICT: 409>` | `ensure_same_receiver` en la reserva |
| Reserva confirmada antes de la red | Mutación que llama al proveedor dentro de la transacción de reserva: `sqlalchemy.exc.NoResultFound` (el intento aún no era visible fuera de la transacción) | Llamada al proveedor fuera de transacción |

Refactor con suite verde: frontera de proveedor separada del dominio de cobros; orquestación en `request_attempt` para mantener el router delgado.

## B14-VC01 — Resultado inicial del QR simulado

Proceso real `python -m tappy` sobre `e8b4f54`, DB de desarrollo en `0010_attempt_provider_fields`, proveedor `simulated` por configuración; ids, referencias y fechas normalizados (el `provider_request_id` del simulador se muestra tal cual: es sintético).

| Petición | Status | Respuesta |
| --- | --- | --- |
| `POST /sales/{sale}/attempts {qr}` con K | 201 | `{"id": "<id-2>", "sale_id": "<sale>", "method": "qr", "status": "pending", "simulated": true, "provider_request_id": "SIM-5FF0B97865B3B487", "qr_payload": "SIMULATED-CODI-QR|attempt=<id-2>|amount_cents=30000|concept=Dos tacos", "created_at": "<fecha UTC>"}` |
| `POST /sales/{sale}/attempts {qr}` con K (repetición) | 200 | `{"id": "<id-2>", "sale_id": "<sale>", "method": "qr", "status": "pending", "simulated": true, "provider_request_id": "SIM-5FF0B97865B3B487", "qr_payload": "SIMULATED-CODI-QR|attempt=<id-2>|amount_cents=30000|concept=Dos tacos", "created_at": "<fecha UTC>"}` |
| `GET /sales/{sale}` tras cerrar y reabrir sesión | 200 | `{"id": "<sale>", "merchant_id": "<id-3>", "reference": "<ref>", "amount_cents": 30000, "currency": "MXN", "concept": "Dos tacos", "status": "open", "beneficiary_name": "Tienda Demo A SA de CV", "masked_account": "**************6782", "created_at": "<fecha UTC>", "attempts": [{"id": "<id-2>", "sale_id": "<sale>", "method": "qr", "status": "pending", "simulated": true, "provider_request_id": "SIM-5FF0B97865B3B487", "qr_payload": "SIMULATED-CODI-QR|attempt=<id-2>|amount_cents=30000|concept=Dos tacos", "created_at": "<fecha UTC>"}]}` |
| `POST /sales/{sale}/attempts {qr}` con otra clave | 409 | `{"detail": "The sale already has an active payment attempt"}` |
| `POST /sales/{sale-2}/attempts {qr}` tras cambiar el receptor | 409 | `{"detail": "The receiving account changed after the sale was created; create a new sale"}` |

En la base quedó 1 intento (`pending`, `simulated`). Datos de prueba eliminados al terminar. Estado VC01: **PASS** (resultado inicial; ninguna respuesta indica pago).

### Contrato: `AttemptResponse` (`c8cf0cf` → `e8b4f54`)

```diff
--- attempt_before.json	2026-11-24 12:22:46
+++ attempt_after.json	2026-11-24 12:22:47
@@ -12,10 +12,36 @@
     "method": {
       "$ref": "#/components/schemas/AttemptMethod"
     },
+    "provider_request_id": {
+      "anyOf": [
+        {
+          "type": "string"
+        },
+        {
+          "type": "null"
+        }
+      ],
+      "title": "Provider Request Id"
+    },
+    "qr_payload": {
+      "anyOf": [
+        {
+          "type": "string"
+        },
+        {
+          "type": "null"
+        }
+      ],
+      "title": "Qr Payload"
+    },
     "sale_id": {
       "title": "Sale Id",
       "type": "string"
     },
+    "simulated": {
+      "title": "Simulated",
+      "type": "boolean"
+    },
     "status": {
       "$ref": "#/components/schemas/AttemptStatus"
     }
@@ -25,6 +51,9 @@
     "sale_id",
     "method",
     "status",
+    "simulated",
+    "provider_request_id",
+    "qr_payload",
     "created_at"
   ],
   "title": "AttemptResponse",
```

Clasificación: **cambio aditivo** (campos nuevos en las respuestas de intentos y de cobro). Comportamiento modificado: un intento `qr` ya no se queda en `creating`, pasa a `pending` con payload; aún no hay consumidores (B40).

## Checks

`uv run python -m quality.check` sobre `e8b4f54` (con `.env` exportado): PASS format, lint, types (mypy strict), hygiene, migrations (upgrade/downgrade/upgrade + `alembic check`), tests (266 passed, Postgres real aislado), api (15 contratos sin diferencias).

## Supresiones

Sin supresiones nuevas.

## Umbral

AC PASS / AC aplicables = 3/3 = **100%**.

## Review Standards/Spec

Pendiente.
