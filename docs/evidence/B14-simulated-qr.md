# Evidencia — B14 Mostrar QR pendiente con proveedor simulado

Ticket: [#22](https://github.com/luisjrez/Tappy/issues/22) · Historia: [H4 #4](https://github.com/luisjrez/Tappy/issues/4) · Protocolo: [TICKET_QUALITY_PROTOCOL](../planning/TICKET_QUALITY_PROTOCOL.md) · Manifiesto: [B14-simulated-qr.toml](B14-simulated-qr.toml)

> **Simulación.** Todo QR de este ticket sale del simulador local (`"simulated": true`, payload `SIMULATED-CODI-QR|…`): no es un QR CoDi, no puede pagarse y **no demuestra integración bancaria real**. La integración con pey es B15 y la verificación real de extremo a extremo es B35.

## Revisiones y escenario

- Ticket, UC/AC/TC y comprobación: B14-UC01–UC03, B14-AC01–AC03, B14-TC01–TC03, B14-VC01.
- Modalidad: **resultado inicial** para el QR simulado (flujo nuevo) y **antes/después** para el intento QR de B13: antes quedaba en `creating` sin payload ([B13-VC01](B13-attempt-reservation.md#b13-vc01--resultado-inicial-de-api-e-interrupción)), ahora pasa a `pending` con ID y payload; `AttemptResponse` gana campos (diff abajo). Contratos aprobados sin diferencias.
- Cambios esperados en tests de B13: los que comprueban el estado `creating` (reserva, reinicio) usan ahora el canal `phone`, que todavía no llama a ningún proveedor; el INSERT directo del test del índice copia las columnas nuevas.
- Base: rama B13 `0a0cb9c` (PR #69), stack de H4 #68. Revisiones: candidato `e8b4f54` → correcciones de review `41b4b1f` (revisión final; VC01 repetida sobre ella).
- Entorno: macOS, Colima + Compose (Postgres 18), Python 3.14.8. Fecha: 2026-11-24. Ejecutor: sesión local de desarrollo del autor del PR.
- Datos: comercio «Tienda Demo A», identidades sintéticas, receptor ficticio (`bank-account-demo-a`).

## Diseño

- Frontera de proveedor por capacidades (`tappy.payments.provider`): `QrProvider` (`name`, `simulated`, `create_qr(QrOrder) -> IssuedQr`), `QrOrder` (intento, importe en centavos, concepto, cuenta del proveedor) e `IssuedQr` (ID del proveedor y payload). El simulador (`tappy.payments.simulator.SimulatedQrProvider`) implementa esa frontera; los tests lo inyectan en `create_app` (como el reloj) para fijar «Q1», sin simular módulos internos. `TAPPY_PAYMENT_PROVIDER` elige el proveedor (`simulated` es el único valor hasta B15).
- Flujo en `request_attempt`: (1) transacción corta que reserva el intento `creating` y lo confirma; (2) llamada al proveedor **fuera** de toda transacción; (3) transacción que bloquea el intento (`FOR UPDATE` + `populate_existing`) y, si sigue `creating`, guarda `provider_request_id`, el payload exacto y pasa a `pending` (con `version`). Una repetición con la misma clave devuelve el intento guardado sin llamar al proveedor.
- Migración `0010_attempt_provider_fields`: en `sales`, `receiver_account` (instantánea de la cuenta del proveedor al crear el cobro, rellenada desde el receptor para filas previas y añadida al trigger de inmutabilidad); en `payment_attempts`, `provider`, `simulated`, `receiver_account` (copiada de la instantánea del cobro), `provider_request_id`, `qr_payload` y unicidad `(provider, provider_request_id)`. El downgrade elimina esas columnas (los QR guardados se pierden al volver a un esquema que no los tiene) y restaura el trigger anterior.
- Seguridad del destino del dinero (decisión registrada en [#22](https://github.com/luisjrez/Tappy/issues/22)): el QR se pide para la cuenta de la instantánea del cobro y la reserva exige que el receptor vigente coincida con ella (cuenta del proveedor, beneficiario y últimos 4 dígitos); si se reconfiguró, `409` y no se llama al proveedor.
- Referencia: cada intento expone `sale_reference` (la referencia del cobro) y el simulador la incluye en el payload (`ref=…`); es la misma al crear, repetir y reabrir sesión.
- Sin pago implícito: el cobro sigue `open`, el intento `pending`; no existen campos de recepción ni transferencias. `phone`/`link` quedan reservados hasta B36/B38. Si el proveedor no está disponible (`ProviderUnavailableError`), la respuesta es `503` y el intento queda `creating` sin payload, **activo** (bloquea nuevas reservas); repetir con la misma clave devuelve ese intento sin volver a llamar al proveedor (falla cerrado: no repetir una creación ambigua, §8.7). Su recuperación a `reconciling` queda como arrastre obligatorio en [#24 (B16)](https://github.com/luisjrez/Tappy/issues/24), junto con la caída entre la llamada al proveedor y el registro.
- La frontera vive en `tappy.payments` (protocolo, simulador y dependencia `QrProviderDependency`); el simulador de producción no guarda estado: los tests que cuentan órdenes usan una subclase propia.

## Trazabilidad UC → AC → TC → test

| UC | AC | TC | Test real | Resultado |
| --- | --- | --- | --- | --- |
| B14-UC01 | B14-AC01 | B14-TC01 | `test_creating_a_qr_returns_the_simulated_payload_pending` (payload exacto con la referencia, ID Q1, `sale_reference`, `simulated: true`, `pending`; el proveedor recibió referencia, importe, concepto, cuenta e intento); `test_stored_qr_keeps_the_exact_payload_and_identifier`; `test_default_simulator_issues_distinct_labelled_identifiers`; `test_reservation_is_committed_before_the_provider_is_called`; `test_unavailable_provider_fails_closed_and_keeps_the_reservation` | PASS |
| B14-UC02 | B14-AC02 | B14-TC02 | `test_simulated_acceptance_never_shows_a_payment` (cobro `open`, intento `pending`; la respuesta no contiene «paid», «received» ni «transaction») | PASS |
| B14-UC03 | B14-AC03 | B14-TC03 | `test_repeating_or_reopening_the_session_reuses_the_same_qr` (repetir con la misma clave → 200 mismo QR; logout `204` y el token anterior da `401`; con la sesión nueva, mismo intento y misma referencia; otra clave → 409; el simulador recibió una sola orden; 1 intento) | PASS |

## TDD

| Comportamiento | Red | Green |
| --- | --- | --- |
| QR simulado, payload, etiqueta, repetición | Con la frontera y el simulador creados pero sin conectar al flujo, 7 de 7 fallan: `assert ['creating'] == ['pending']`, `assert 0 == 1` (el simulador no recibía órdenes), `KeyError: 'simulated'`/`'qr_payload'` | `request_attempt` (reserva → proveedor → registro), migración `0010`, campos en la respuesta |
| Selección por configuración | Primero `ImportError` (no es Red de comportamiento); Red de comportamiento por mutación con `payment_provider: str`: `Failed: DID NOT RAISE ValueError` | `payment_provider: Literal["simulated"]` + `provider_from` |
| Receptor cambiado tras el cobro | Primera versión escrita tras la regla (mutación sin `ensure_same_receiver`: `assert 201 == 409`). Tras la review, cambio solo de la cuenta del proveedor con mismo beneficiario y últimos 4: `assert 201 == <HTTPStatus.CONFLICT: 409>` antes de añadir la instantánea al cobro | Instantánea `sales.receiver_account` comparada en la reserva |
| Referencia junto al QR (review) | `KeyError: 'sale_reference'` y payload sin `ref=` | `sale_reference` en el intento y en el payload |
| Proveedor no disponible (review) | `tappy.payments.provider.ProviderUnavailableError` sin manejar (500) | `503` explícito; intento `creating` conservado |
| Reserva confirmada antes de la red | Mutación que llama al proveedor dentro de la transacción de reserva: `sqlalchemy.exc.NoResultFound` (el intento aún no era visible fuera de la transacción) | Llamada al proveedor fuera de transacción |

Refactor con suite verde: frontera de proveedor separada del dominio de cobros; orquestación en `request_attempt` para mantener el router delgado.

## B14-VC01 — Resultado inicial del QR simulado

Proceso real `python -m tappy` sobre `41b4b1f`, DB de desarrollo recreada y migrada a `0010_attempt_provider_fields` (la anterior tenía la versión previa de `0010`, sin publicar), proveedor `simulated` por configuración. Valores **sin normalizar** (todos sintéticos): ids, referencia, ID del simulador y payload completo, para que ningún cambio en el contenido del QR quede oculto.

| Petición | Status | Respuesta |
| --- | --- | --- |
| `POST /sales {A, 30000, "Dos tacos"}` | 201 | id `c1320d79-9a81-4b99-81ca-dbfe817f5085`, referencia `MSPE6WGBSK` |
| `POST /sales/{sale}/attempts {qr}` con K | 201 | `{"id": "857c57e1-e77a-4401-9b5f-33ad45ab8cf9", "sale_id": "c1320d79-9a81-4b99-81ca-dbfe817f5085", "sale_reference": "MSPE6WGBSK", "method": "qr", "status": "pending", "simulated": true, "provider_request_id": "SIM-923EF24D3C2BC761", "qr_payload": "SIMULATED-CODI-QR|ref=MSPE6WGBSK|attempt=857c57e1-e77a-4401-9b5f-33ad45ab8cf9|amount_cents=30000|concept=Dos tacos", "created_at": "2026-11-24T18:31:07.791219Z"}` |
| `POST /sales/{sale}/attempts {qr}` con K (repetición) | 200 | `{"id": "857c57e1-e77a-4401-9b5f-33ad45ab8cf9", "sale_id": "c1320d79-9a81-4b99-81ca-dbfe817f5085", "sale_reference": "MSPE6WGBSK", "method": "qr", "status": "pending", "simulated": true, "provider_request_id": "SIM-923EF24D3C2BC761", "qr_payload": "SIMULATED-CODI-QR|ref=MSPE6WGBSK|attempt=857c57e1-e77a-4401-9b5f-33ad45ab8cf9|amount_cents=30000|concept=Dos tacos", "created_at": "2026-11-24T18:31:07.791219Z"}` |
| `GET /sales/{sale}` tras cerrar y reabrir sesión | 200 | `{"id": "c1320d79-9a81-4b99-81ca-dbfe817f5085", "merchant_id": "736b6f0e-74fd-4269-b731-243e1d5d4b75", "reference": "MSPE6WGBSK", "amount_cents": 30000, "currency": "MXN", "concept": "Dos tacos", "status": "open", "beneficiary_name": "Tienda Demo A SA de CV", "masked_account": "**************6782", "created_at": "2026-11-24T18:31:07.779421Z", "attempts": [{"id": "857c57e1-e77a-4401-9b5f-33ad45ab8cf9", "sale_id": "c1320d79-9a81-4b99-81ca-dbfe817f5085", "sale_reference": "MSPE6WGBSK", "method": "qr", "status": "pending", "simulated": true, "provider_request_id": "SIM-923EF24D3C2BC761", "qr_payload": "SIMULATED-CODI-QR|ref=MSPE6WGBSK|attempt=857c57e1-e77a-4401-9b5f-33ad45ab8cf9|amount_cents=30000|concept=Dos tacos", "created_at": "2026-11-24T18:31:07.791219Z"}]}` |
| `POST /sales/{sale}/attempts {qr}` con otra clave | 409 | `{"detail": "The sale already has an active payment attempt"}` |
| `POST /sales/{sale-2}/attempts {qr}` tras cambiar el receptor | 409 | `{"detail": "The receiving account changed after the sale was created; create a new sale"}` |

En la base quedó 1 intento (`pending`, `simulated`, cuenta `bank-account-demo-a`). Datos de prueba eliminados al terminar. Estado VC01: **PASS** (resultado inicial; ninguna respuesta indica pago).

### Contrato: `AttemptResponse` (`c8cf0cf` → `41b4b1f`)

```diff
--- attempt_before.json	2026-11-24 12:31:46
+++ attempt_after.json	2026-11-24 12:31:47
@@ -12,10 +12,40 @@
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
+    "sale_reference": {
+      "title": "Sale Reference",
+      "type": "string"
+    },
+    "simulated": {
+      "title": "Simulated",
+      "type": "boolean"
+    },
     "status": {
       "$ref": "#/components/schemas/AttemptStatus"
     }
@@ -23,8 +53,12 @@
   "required": [
     "id",
     "sale_id",
+    "sale_reference",
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

`uv run python -m quality.check` sobre `41b4b1f` (con `.env` exportado): PASS format, lint, types (mypy strict), hygiene, migrations (upgrade/downgrade/upgrade + `alembic check`), tests (269 passed, Postgres real aislado), api (15 contratos sin diferencias). Mutaciones comprobadas: proveedor llamado dentro de la transacción → `NoResultFound`; sin la regla de receptor → 201; `payment_provider: str` → acepta valores desconocidos.

Tests complementarios fuera de la matriz de AC (no cuentan para el umbral): `test_qr_is_refused_when_the_receiver_changed_after_the_sale` (2 casos), `test_other_channels_stay_reserved_without_calling_the_qr_provider` y `test_provider_setting_selects_the_simulator_and_rejects_unknown_values`.

## Supresiones

Sin supresiones nuevas.

## Umbral

AC PASS / AC aplicables = 3/3 = **100%**.

## Review Standards/Spec

Pendiente.
