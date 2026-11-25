# Evidencia — B24 Vencer QR sin inventar cancelación

Ticket: [#32](https://github.com/luisjrez/Tappy/issues/32) · Historia: [H5 #5](https://github.com/luisjrez/Tappy/issues/5) · Protocolo: [TICKET_QUALITY_PROTOCOL](../planning/TICKET_QUALITY_PROTOCOL.md) · Manifiesto: [B24-qr-expiration.toml](B24-qr-expiration.toml)

> Verificado con el contrato oficial de pey (`expiration` de `POST /codi/qr`, OpenAPI `2026-10-20`) y con un pey falso local. **No hubo QR, pagos ni webhooks reales.** «Vencido» significa que terminó la ventana de uso que muestra Tappy. No es una revocación bancaria ni un rechazo.

## Revisiones y escenario

- **Trazabilidad:** B24-UC01–UC03, B24-AC01–AC03, B24-TC01–TC03 y B24-VC01.
- **Modalidad: antes/después.**
  - El seguimiento del intento cambia: pasa de no vencer nunca a vencer por reloj del servidor.
  - `AttemptResponse` gana `expires_at` y `next_action`; es un cambio aditivo y el diff está abajo.
  - La petición a pey gana `expiration`.
- **Cambios esperados en tests anteriores:**
  - El cuerpo exacto de la reserva (B13) y el del QR simulado (B14) incluyen `expires_at` y `next_action`.
  - El cuerpo exacto enviado a pey (B15) incluye `expiration`, y el `IssuedQr` del adaptador incluye su vigencia.
- **Base y revisiones:**
  - Base: rama B23 `7ad3520` ([PR #79](https://github.com/luisjrez/Tappy/pull/79)), stack #68.
  - Candidato: `14b117a`.
  - Notas de la review: `4e4573a`, revisión final. La VC01 se repitió sobre ella.
- **Entorno:** macOS, Colima + Compose (Postgres 18), Python 3.14.8. Fecha: 2026-11-25 (UTC). Ejecutor: sesión local de desarrollo del autor del PR.

## Diseño

### Ventana de uso

- `TAPPY_QR_EXPIRATION_SECONDS`: 900 por defecto, con un mínimo de 360 (el mínimo del contrato de pey) y un máximo de un día.
- Se envía a pey como `expiration`. Hasta ahora no se enviaba, y según el contrato eso significa «sin vencimiento» y que el QR se puede pagar más de una vez (arrastre de B15).
- El proveedor informa la vigencia del QR emitido (`IssuedQr.valid_for`). El simulador usa la misma ventana.
- `payment_attempts.expires_at` (migración `0019`, con índice parcial sobre los `pending`) se cuenta desde **antes** de llamar a pey. Así nunca dura más que la ventana real de pey.

### Autoridad del servidor (`tappy.sales.expiration.expire_due_attempts`)

- Un intento `pending` cuyo `expires_at` ya pasó según el reloj del servidor (`Clock`) pasa a `expired` por `move()`.
- Esto ocurre al leer el cobro (`GET /sales/{id}`) y en cada lote `run-jobs`.
- El reloj, la cabecera `Date` o los parámetros del cliente nunca intervienen.
- Decisión: el `GET` escribe el vencimiento. Es idempotente y solo toma `FOR UPDATE SKIP LOCKED` sobre el intento, así que no espera ni invierte el orden de locks consultivo → intento → cobro de la aplicación de evidencia. Si el intento está bloqueado, el `GET` lo muestra `pending` hasta el siguiente lote.
- Solo vencen los `pending`:
  - Un `paid` nunca vence: su recepción no se borra.
  - Un `reconciling` no vence por su ventana: su resultado es incierto y no se trata como rechazado.
- Vencer no pone `failure_code` ni cambia el cobro, que sigue `open`. Un pago auténtico tardío sigue confirmando (`expired → paid`, §7).

### Siguiente acción segura

`AttemptResponse.next_action` se deriva del estado en una sola tabla, junto a la vista:

| Estado | Siguiente acción |
| --- | --- |
| `creating` | `wait_for_qr` |
| `pending` | `show_qr` |
| `reconciling` | `wait_for_verification` |
| `expired` | `verify_before_retry` |
| `failed` | `new_attempt` |
| `paid` | `none` |

Ninguna acción sugiere cancelación ni revocación. «Revisar antes de generar otro intento» es la regla de PRODUCT_BASE para una solicitud vencida.

### Separación

El vencimiento está en su propio módulo. No toca transferencias ni recepciones, y la presentación se limita a leer el estado.

### Notas para B25

- Un intento `expired` no es activo (decisión de B13), así que ya permite reservar otro intento sin verificar. `verify_before_retry` es solo una indicación; hacerla obligatoria es B25.
- Un intento `reconciling` sin id de QR nunca vence y sigue bloqueando nuevos intentos.
- Una repetición idempotente de la reserva devuelve la vista guardada hasta que un `GET` o un lote aplique el vencimiento.

## Trazabilidad UC → AC → TC → test

Todos los tests están en `tests/sales/test_qr_expiration.py`.

| UC | AC | TC | Test real | Resultado |
| --- | --- | --- | --- | --- |
| B24-UC01 | B24-AC01 | B24-TC01 | `test_the_qr_window_is_sent_to_pey_and_shown_by_the_server`; `test_a_reached_server_expiration_shows_expired_and_a_safe_next_action` (`expired`, `verify_before_retry`, sin `failure_code`, cobro `open`, ningún texto de cancelación); `test_the_batch_expires_pending_attempts_by_the_server_clock`; `test_the_simulator_uses_the_same_server_window`; `test_the_qr_window_respects_the_provider_minimum` | PASS |
| B24-UC02 | B24-AC02 | B24-TC02 | `test_the_client_clock_never_changes_the_state[ahead\|behind]` (cliente ±2 h por `Date` y `?now=`, servidor 1 s antes del vencimiento: sigue `pending`); `test_an_uncertain_attempt_is_not_expired_by_its_window` | PASS |
| B24-UC03 | B24-AC03 | B24-TC03 | `test_a_paid_attempt_stays_confirmed_after_its_expiration` (lote tras el vencimiento: 0 vencidos, sigue `paid` con su transferencia); `test_an_authentic_late_payment_still_confirms_an_expired_attempt` | PASS |

## TDD

| Comportamiento | Red | Green |
| --- | --- | --- |
| Ventana, vencimiento y siguiente acción | Los tests se escribieron antes del código: 8 errores en la preparación (`Extra inputs are not permitted` para `qr_expiration_seconds`) y 1 fallo en el test del mínimo | `qr_expiration_seconds`, `expiration`, `expires_at`, `expire_due_attempts`, `next_action` |
| Vencer al leer | Mutación sin vencer en el `GET`: fallan `reached_server_expiration…` y `late_payment…` | `read_sale` vence con el reloj del servidor |
| Solo `pending` | Mutación que también vence `reconciling`: falla `uncertain_attempt_is_not_expired…` | Filtro por `pending` |
| Reloj del servidor exacto | Mutación que vence 3 h antes: fallan `client_clock…[ahead\|behind]` y `batch_expires…` | `expires_at <= now` |

## Aplicabilidad por superficie

| Superficie | Aplica | Justificación |
| --- | --- | --- |
| API | Sí | `expires_at`, `next_action` y el estado `expired` en el seguimiento |
| Comandos | Sí | `run-jobs` informa `pending attempts expired` |
| Panel | No aplica | Sin vistas en este alcance |

## B24-VC01 — Antes/después del vencimiento

Proceso real `python -m tappy` con `TAPPY_PAYMENT_PROVIDER=pey`, `TAPPY_QR_EXPIRATION_SECONDS=360` y un secreto de webhooks generado al vuelo. El pey falso local registra el cuerpo de la creación. Para no esperar la ventana real de 360 s, `expires_at` se adelanta por SQL a «ahora − 1 s». El vencimiento lo aplica el servidor al consultar. Valores sintéticos.

### Antes (B23 `7ad3520`)

**A: QR pendiente y vencimiento del servidor alcanzado (TC01)**

- Seguimiento recién creado → 200 `{"sale": "open", "confirmed_amount_cents": 0, "attempt": "pending", "failure_code": null}`
- Mismo seguimiento con reloj de cliente adelantado 2 h (`Date: Wed, 25 Nov 2026 14:31:51 GMT`, `?now=`) antes del vencimiento (TC02) → 200 `{"sale": "open", "confirmed_amount_cents": 0, "attempt": "pending", "failure_code": null}`
- (esta revisión no guarda `expires_at`: el intento no tiene vencimiento que adelantar)
- Seguimiento tras el vencimiento del servidor → 200 `{"sale": "open", "confirmed_amount_cents": 0, "attempt": "pending", "failure_code": null}`
- Webhook de pago auténtico TX-VC24-A → 204
- Seguimiento tras el pago tardío → 200 `{"sale": "paid", "confirmed_amount_cents": 30000, "attempt": "paid", "failure_code": null}`

**B: intento pagado y vencimiento posterior (TC03)**

- Webhook de pago auténtico TX-VC24-B → 204
- (esta revisión no guarda `expires_at`: el intento no tiene vencimiento que adelantar)
- Seguimiento del pagado después de su vencimiento → 200 `{"sale": "paid", "confirmed_amount_cents": 30000, "attempt": "paid", "failure_code": null}`

Cuerpo enviado a pey en la creación del QR A:

{"path": "/codi/qr", "auth_matches": true, "body": "{\"amount\":300.0,\"bankAccountId\":\"01HZY3K8Q4N6V7W8X9Y0Z1A2B3\",\"metadata\":{\"tappy_attempt_id\":\"324826e9-9dbb-4170-819e-3b26023be146\",\"tappy_reference\":\"6C5XRZVX37\"}}"}

### Después (revisión final `4e4573a`)

**A: QR pendiente y vencimiento del servidor alcanzado (TC01)**

- Seguimiento recién creado → 200 `{"sale": "open", "confirmed_amount_cents": 0, "attempt": "pending", "failure_code": null, "expires_at": "2026-11-25T12:43:30.921552Z", "next_action": "show_qr"}`
- Mismo seguimiento con reloj de cliente adelantado 2 h (`Date: Wed, 25 Nov 2026 14:37:30 GMT`, `?now=`) antes del vencimiento (TC02) → 200 `{"sale": "open", "confirmed_amount_cents": 0, "attempt": "pending", "failure_code": null, "expires_at": "2026-11-25T12:43:30.921552Z", "next_action": "show_qr"}`
- (se adelanta `expires_at` a «ahora − 1 s» por SQL para no esperar la ventana real de 360 s)
- Seguimiento tras el vencimiento del servidor → 200 `{"sale": "open", "confirmed_amount_cents": 0, "attempt": "expired", "failure_code": null, "expires_at": "2026-11-25T12:37:30.082577Z", "next_action": "verify_before_retry"}`
- Webhook de pago auténtico TX-VC24-A → 204
- Seguimiento tras el pago tardío → 200 `{"sale": "paid", "confirmed_amount_cents": 30000, "attempt": "paid", "failure_code": null, "expires_at": "2026-11-25T12:37:30.082577Z", "next_action": "none"}`

**B: intento pagado y vencimiento posterior (TC03)**

- Webhook de pago auténtico TX-VC24-B → 204
- (se adelanta `expires_at` a «ahora − 1 s» por SQL para no esperar la ventana real de 360 s)
- Seguimiento del pagado después de su vencimiento → 200 `{"sale": "paid", "confirmed_amount_cents": 30000, "attempt": "paid", "failure_code": null, "expires_at": "2026-11-25T12:37:30.156832Z", "next_action": "none"}`

Cuerpo enviado a pey en la creación del QR A:

{"path": "/codi/qr", "auth_matches": true, "body": "{\"amount\":300.0,\"bankAccountId\":\"01HZY3K8Q4N6V7W8X9Y0Z1A2B3\",\"expiration\":360,\"metadata\":{\"tappy_attempt_id\":\"59c35942-11d3-4b12-b270-9176cb953b5f\",\"tappy_reference\":\"WWR9P6E4ET\"}}"}

Validación:

- **TC01:** con el vencimiento del servidor alcanzado, el seguimiento muestra `expired` y `verify_before_retry`, sin `failure_code` y con el cobro `open`.
- **TC02:** con el reloj del cliente adelantado 2 h y antes del vencimiento, el intento sigue `pending`.
- **TC03:** un intento pagado cuyo vencimiento ya pasó sigue `paid` con su importe. Un pago auténtico después del vencimiento confirma A.
- **Contrato:** a pey se envía `expiration: 360`.
- **Antes:** no había vencimiento ni siguiente acción, y la petición iba sin `expiration`, es decir, sin vencimiento en pey.

Los datos se eliminaron al terminar. Estado VC01: **PASS**.

### Contrato: `AttemptResponse` (B23 → B24)

```diff
--- attempt24_before.json	2026-11-25 06:31:06
+++ attempt24_after.json	2026-11-25 06:31:07
@@ -6,6 +6,18 @@
         "title": "Created At",
         "type": "string"
       },
+      "expires_at": {
+        "anyOf": [
+          {
+            "format": "date-time",
+            "type": "string"
+          },
+          {
+            "type": "null"
+          }
+        ],
+        "title": "Expires At"
+      },
       "failure_code": {
         "anyOf": [
           {
@@ -24,6 +36,9 @@
       "method": {
         "$ref": "#/components/schemas/AttemptMethod"
       },
+      "next_action": {
+        "$ref": "#/components/schemas/NextAction"
+      },
       "provider_request_id": {
         "anyOf": [
           {
@@ -72,9 +87,23 @@
       "provider_request_id",
       "qr_payload",
       "failure_code",
-      "created_at"
+      "created_at",
+      "expires_at",
+      "next_action"
     ],
     "title": "AttemptResponse",
     "type": "object"
+  },
+  "NextAction": {
+    "enum": [
+      "wait_for_qr",
+      "show_qr",
+      "wait_for_verification",
+      "verify_before_retry",
+      "new_attempt",
+      "none"
+    ],
+    "title": "NextAction",
+    "type": "string"
   }
 }
```

### Diferencias y decisión

| TC/AC | Antes (B23) | Después | Clasificación | Decisión |
| --- | --- | --- | --- | --- |
| TC01 | El QR nunca vencía (ni en Tappy ni en pey) | Vence por reloj del servidor, con `verify_before_retry` y sin afirmar cancelación | Comportamiento | Aceptada |
| TC02 | Sin vencimiento | El reloj del cliente no influye | Comportamiento | Aceptada |
| TC03 | `paid` | `paid` también después del vencimiento | Sin cambio | Aceptada |
| Petición a pey | Sin `expiration` | `expiration` = ventana configurada | Comportamiento | Aceptada |
| `AttemptResponse` | — | `expires_at`, `next_action` | Aditiva | Aceptada |

## Checks

`uv run python -m quality.check` sobre `4e4573a`, con `.env` exportado: PASS en todos los pasos.

- format, lint y types (mypy strict).
- hygiene.
- migrations: upgrade/downgrade/upgrade de `0019` + `alembic check`.
- tests: 466 passed, Postgres real aislado.
- api: 16 contratos sin diferencias.
- evidence: B01–B23 APPROVED.

## Supresiones

Sin supresiones nuevas.

## Umbral

AC PASS / AC aplicables = 3/3 = **100%**.

## Review Standards/Spec

| Ronda | Revisión | Standards | Spec | Hallazgos |
| --- | --- | --- | --- | --- |
| 1 | `14b117a` | APPROVE | APPROVE | Sin violaciones ni defectos. Notas aplicadas en `4e4573a`: un solo tipo para la ventana en `PeySettings`, `NextAction` junto a la vista del intento y conteo explícito del vencimiento. Decisiones registradas: el `GET` escribe el vencimiento (idempotente, sin esperar locks); `valid_for` por omisión `None` solo en dobles de test. Notas para B25 publicadas en #33 |

Hallazgos pendientes: 0.
