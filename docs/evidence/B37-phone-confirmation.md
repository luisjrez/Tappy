# Evidencia — B37 Conciliar y confirmar pago al celular

Ticket: [#45](https://github.com/luisjrez/Tappy/issues/45) · Historia: [H8 #8](https://github.com/luisjrez/Tappy/issues/8) · Protocolo: [TICKET_QUALITY_PROTOCOL](../planning/TICKET_QUALITY_PROTOCOL.md) · Manifiesto: [B37-phone-confirmation.toml](B37-phone-confirmation.toml)

> Verificado con números sintéticos, un pey falso que responde con los ejemplos oficiales (`POST /codi/pn`, `GET /transaction/{id}` y el webhook `codi.pn.payment_received`) y Postgres aislado. **No hubo llamadas a pey real; una simulación no demuestra la integración.** La parte externa de B37-TC03 («prueba real registra banco/dispositivo observados») salió a [#112](https://github.com/luisjrez/Tappy/issues/112) por la decisión del responsable del producto del 2026-11-26, y sigue BLOCKED.

## Revisiones y escenario

- **Trazabilidad:** B37-UC01–UC03, B37-AC01–AC03 y B37-VC01. Superficie: confirmación y consulta de pagos al celular (webhook, `reconcile`/`run-jobs`, detalle de venta y resumen diario).
- **Modalidad:** resultado inicial. Antes de B37 un intento `phone` no se confirmaba ni se consultaba (`not_queryable`), y el canal solo se aceptaba en `TAPPY_ENVIRONMENT=test`.
- **Base y revisiones:**
  - Base: rama B42 `78f646f` ([PR #61](https://github.com/luisjrez/Tappy/pull/61)), stack #68.
  - Candidato de la ronda 1: `7f97772` (función) + `4169172` (expectativa de `test_reception`) + `e916498` (evidencia).
  - Candidato de la ronda 2: `838e033` (correcciones de la ronda 1).
- **Entorno:** macOS, Postgres 18.6 aislado (Colima + Compose) y Python 3.14.8. Fecha: 2026-11-27 (UTC). Ejecutor: sesión local de desarrollo del autor del PR.

## Contrato de pey usado

- **Consulta:** `tests/fixtures/pey/transaction.json`, generado desde `https://docs.pey.mx/openapi.json`, versión `2026-10-20`, el mismo `sha256` (`568e0255…5c5a`) que los fixtures de QR y de `/codi/pn`.
  - `GET /transaction/{id}` → `200` con `id`, `status` (`PENDING` | `PAID`), `amount`, `amountBreakdown`, `datePaid`, …;
  - errores documentados: `404`, `429` y `500`.
- **Webhook:** `tests/fixtures/pey/webhook-codi-pn.json`, con el ejemplo de `https://docs.pey.mx/docs/webhooks/codi/pn/` (consultado el 2026-11-26). Trae `transactionId` (el mismo id que devuelve `POST /codi/pn`), `amount`, `bankAccountId`, `datePaid` y `metadata`; no trae `codiQrId`. Los datos del integrador llegan anidados en `metadata.externalMetadata`, así que los tests de celular entregan el ejemplo con su `metadata` intacta y la identificación descansa solo en `transactionId`.
- **Lo que pey no documenta:** eventos de entrega, lectura, rechazo o falta de enrolamiento. Por eso la ausencia de push nunca se interpreta como rechazo.

## Diseño

- **Evidencia común:** el webhook `codi.pn.payment_received` entra por el mismo camino que `codi.qr.payment_received`. Lo único propio del canal es el campo que identifica la solicitud: `REQUEST_ID_FIELDS = {qr: "codiQrId", pn: "transactionId"}`. Firma, deduplicación por mensaje y por transacción, comparación de importe, cuenta y fecha, y aplicación son las de QR.
- **Consulta:** `QrProvider.phone_payments(provider_request_id)`.
  - pey llama a `GET /transaction/{transactionId}` (id escapado). `PAID` devuelve el pago con su importe y fecha; `PENDING` devuelve `[]` (sin evidencia). Una respuesta con otro `id` es inválida (`invalid_response`).
  - Un `404`, `429`, `500`, un timeout o una respuesta inválida lanzan `PaymentsQueryError`. La conciliación los trata como incertidumbre (`uncertain`, con el problema), nunca como rechazo.
  - El simulador devuelve `[]`.
- **Conciliación:** `QueryTarget` lleva el método del intento. Solo QR y celular son consultables (`QUERYABLE_METHODS`), con un mapa explícito: QR → `qr_payments`, celular → `phone_payments`. Un intento `link` sigue `not_queryable`. El resto (deduplicación, verificación de vencidos, reprogramación, agotamiento) es el mismo.
- **Evento antes de la respuesta:** si el pago llega antes de que pey responda a `POST /codi/pn`, el evento queda como excepción `unassociated` con su `transactionId`; al guardar la respuesta se reaplica igual que en QR (`apply_waiting_events` ya no se limita a QR).
- **Reglas retiradas (refactor):**
  - la restricción «solo `test` con el simulador» de B36 (`phone_requests_wait_for_verification`), que existía porque un intento `phone` vencido no se podía verificar;
  - la guarda `not_queryable` para `phone` en la conciliación.
- **Comisión:** en el ejemplo de pey, `amount` de la transacción puede incluir la comisión cobrada al pagador. Tappy compara `amount` con el importe de la venta: si difiere, la venta va a revisión (`amount_mismatch`) y nunca se confirma de más. La confirmación con pey real se suma a #112.
- **Cuota:** las solicitudes al celular cuentan contra `TAPPY_ATTEMPT_CREATION_QUOTA` como cualquier intento (motor de B33), así que los reenvíos por encima de la cuota responden `429` sin llamar a pey.

## Trazabilidad UC → AC → TC

| UC | AC | TC | Tests | Resultado |
| --- | --- | --- | --- | --- |
| B37-UC01 | B37-AC01 | B37-TC01 | `test_an_exact_phone_payment_event_confirms_the_sale_once` (evento exacto con la `metadata` documentada ×3 → venta `paid`, una transferencia, `applied,duplicate`), `test_a_query_finds_the_paid_phone_payment_through_its_transaction` (consulta `/transaction/{id}` → `confirmed`), `test_a_payment_event_before_the_phone_request_answer_ends_confirmed` (evento antes de la respuesta → `paid` al guardarla), `test_a_link_attempt_is_never_queried_as_another_channel`, `test_phone_requests_can_be_enabled_outside_tests_once_payments_are_verifiable` y `test_a_phone_request_is_never_queried_through_the_qr_payments_endpoint` (adaptado: consulta `/transaction/{id}`, nunca `/codi/qr/…`) | PASS |
| B37-UC02 | B37-AC02 | B37-TC02 | `test_a_pending_transaction_is_not_read_as_a_rejection` (`no_evidence`, intento `pending` sin `failure_code`), `test_an_unanswered_query_keeps_the_doubt_and_never_fails_the_request` (`404`, `429`, `500`, respuesta inválida u otro `id` → `uncertain`), `test_a_lost_query_answer_never_sends_a_new_request_to_the_phone`, `test_an_expired_unpaid_phone_request_is_verified_and_allows_a_new_attempt` y `test_the_jobs_runner_verifies_an_expired_phone_request` | PASS |
| B37-UC03 | B37-AC03 | B37-TC03 | Parte automatizada: `test_an_exact_phone_payment_event_confirms_the_sale_once` (evento repetido), `test_a_webhook_and_a_query_for_the_same_phone_payment_count_once`, `test_a_different_amount_goes_to_review_instead_of_confirming`, `test_new_phone_requests_over_the_quota_get_429_without_reaching_pey` y `test_a_lost_provider_answer_keeps_one_verifying_attempt_and_the_retry_does_not_resend` (B36). Parte externa (banco/dispositivo observados): **movida a #112**, BLOCKED | PASS (automatizada) |

### B37-TC03 — parte externa movida a #112

- El 2026-11-26 el responsable del producto decidió sacar las pruebas reales a su propio ticket. La parte externa de TC03 se suma a la prueba real con pey de #112 ([comentario de arrastre](https://github.com/luisjrez/Tappy/issues/112)).
- Lo que debe registrar, sanitizado: banco y tipo de dispositivo donde se vio la solicitud (sin datos del pagador), si llegó y si se pagó con el importe acordado; si `amount` incluye la comisión; y dónde llega la `metadata` propia (los ejemplos la anidan en `metadata.externalMetadata`).
- Hasta entonces la integración bancaria real del canal no está demostrada. AC03 se aprueba solo por su parte automatizada, que cubre «el dinero no se duplica y la cuota limita reenvíos».

## TDD

**Red** sobre `78f646f` con los tests nuevos: fallan 13 de 14.

```
FAILED tests/sales/test_phone_confirmation.py::test_an_exact_phone_payment_event_confirms_the_sale_once
FAILED tests/sales/test_phone_confirmation.py::test_a_query_finds_the_paid_phone_payment_through_its_transaction
FAILED tests/sales/test_phone_confirmation.py::test_a_webhook_and_a_query_for_the_same_phone_payment_count_once
FAILED tests/sales/test_phone_confirmation.py::test_a_different_amount_goes_to_review_instead_of_confirming
FAILED tests/sales/test_phone_confirmation.py::test_a_pending_transaction_is_not_read_as_a_rejection
FAILED tests/sales/test_phone_confirmation.py::test_an_unanswered_query_keeps_the_doubt_and_never_fails_the_request[page0-not_found]
FAILED tests/sales/test_phone_confirmation.py::test_an_unanswered_query_keeps_the_doubt_and_never_fails_the_request[page1-rate_limited]
FAILED tests/sales/test_phone_confirmation.py::test_an_unanswered_query_keeps_the_doubt_and_never_fails_the_request[page2-server_error]
FAILED tests/sales/test_phone_confirmation.py::test_an_unanswered_query_keeps_the_doubt_and_never_fails_the_request[page3-invalid_response]
FAILED tests/sales/test_phone_confirmation.py::test_a_lost_query_answer_never_sends_a_new_request_to_the_phone
FAILED tests/sales/test_phone_confirmation.py::test_an_expired_unpaid_phone_request_is_verified_and_allows_a_new_attempt
FAILED tests/sales/test_phone_confirmation.py::test_phone_requests_can_be_enabled_outside_tests_once_payments_are_verifiable
FAILED tests/sales/test_phone_confirmation.py::test_the_jobs_runner_verifies_an_expired_phone_request
13 failed, 1 passed in 7.57s
```

- Motivos: el evento `codi.pn.payment_received` no se aplicaba, la conciliación devolvía `not_queryable`, y la configuración rechazaba la lista fuera de `test`.
- **El que ya pasaba:** `test_new_phone_requests_over_the_quota_get_429_without_reaching_pey`, porque la cuota de B33 ya cubría cualquier intento: documenta que el canal la hereda. Su eficacia la prueba M7 (abajo).

**Mutaciones** sobre `7f97772`, con `tests/sales/test_phone_confirmation.py` y `tests/sales/test_phone_requests.py` (51 tests):

```
M1 evento de celular ignorado: 3 failed, 48 passed
M2 id de celular leido de codiQrId: 3 failed, 48 passed
M3 celular consultado como QR: 5 failed, 46 passed
M4 PENDING tomado como pagado: 3 failed, 48 passed
M5 consulta fallida tomada como sin evidencia: 5 failed, 46 passed
M6 celular no consultable: 11 failed, 40 passed
M7 intento sin cuota (con test_phone_confirmation.py): 1 failed, 13 passed
```

**Ronda 2 (`838e033`):** el Red se demuestra revirtiendo cada corrección sobre el candidato (R1–R3), y las M1–M6 se repiten sobre `838e033` (54 tests):

```
R1 eventos en espera solo para QR: 1 failed, 53 passed in 25.08s
    test_a_payment_event_before_the_phone_request_answer_ends_confirmed
R2 sin comprobar el id consultado: 1 failed, 53 passed in 24.88s
    test_an_unanswered_query_keeps_the_doubt_and_never_fails_the_request[page4-invalid_response]
R3 enlace consultable: 1 failed, 53 passed in 24.97s
    test_a_link_attempt_is_never_queried_as_another_channel
M1 evento de celular ignorado: 4 failed, 50 passed in 25.30s
    test_an_exact_phone_payment_event_confirms_the_sale_once
    test_a_webhook_and_a_query_for_the_same_phone_payment_count_once
    test_a_different_amount_goes_to_review_instead_of_confirming
M2 id de celular leido de codiQrId: 4 failed, 50 passed in 24.72s
    test_an_exact_phone_payment_event_confirms_the_sale_once
    test_a_webhook_and_a_query_for_the_same_phone_payment_count_once
    test_a_different_amount_goes_to_review_instead_of_confirming
M3 celular consultado como QR: 5 failed, 49 passed in 25.11s
    test_a_query_finds_the_paid_phone_payment_through_its_transaction
    test_a_webhook_and_a_query_for_the_same_phone_payment_count_once
    test_a_pending_transaction_is_not_read_as_a_rejection
M4 PENDING tomado como pagado: 3 failed, 51 passed in 25.05s
    test_a_pending_transaction_is_not_read_as_a_rejection
    test_an_expired_unpaid_phone_request_is_verified_and_allows_a_new_attempt
    test_a_phone_request_is_never_queried_through_the_qr_payments_endpoint
M5 consulta fallida tomada como sin evidencia: 5 failed, 49 passed in 25.17s
    test_an_unanswered_query_keeps_the_doubt_and_never_fails_the_request[page0-not_found]
    test_an_unanswered_query_keeps_the_doubt_and_never_fails_the_request[page1-rate_limited]
    test_an_unanswered_query_keeps_the_doubt_and_never_fails_the_request[page2-server_error]
M6 celular no consultable: 12 failed, 42 passed in 24.61s
    test_a_query_finds_the_paid_phone_payment_through_its_transaction
    test_a_webhook_and_a_query_for_the_same_phone_payment_count_once
    test_a_pending_transaction_is_not_read_as_a_rejection
```

## Cambios esperados en tests anteriores

B37 es justo lo que levanta las limitaciones que B36 documentaba:

- `test_phone_requests.py` (B36):
  - se retiran `test_phone_requests_cannot_be_enabled_until_their_payments_can_be_verified`, `test_phone_requests_stay_off_the_real_provider_until_verifiable` y `test_an_expired_phone_request_blocks_new_attempts_until_payments_can_be_verified`, que fijaban la restricción provisional. Los sustituyen `test_phone_requests_can_be_enabled_outside_tests_once_payments_are_verifiable` y `test_an_expired_unpaid_phone_request_is_verified_and_allows_a_new_attempt`;
  - `test_a_phone_request_is_never_queried_through_the_qr_payments_endpoint` pasa de `not_queryable` sin consultas a `no_evidence` con una consulta a `/transaction/{id}`;
  - el manifiesto de B36 deja de listar los tres tests retirados (su revisión aprobada, `59b3566`, no cambia).
- Los helpers de celular (`CONSENTED`, `ALLOWED`, `phone_settings`, `demo_list_settings`, `open_sale`, `request_phone`, `posted`) pasan de `test_phone_requests.py` a `tests/sales/phone_support.py`, sin cambiar su comportamiento.
- `test_out_of_order.py`: el proveedor de prueba `EarlyPaymentProvider` implementa `phone_payments` (nuevo método del protocolo).
- `test_reception.py` (`changes8`): un `codi.pn.payment_received` construido sobre el ejemplo de QR pasaba a `unmatched` porque el tipo no se reconocía. Ahora se reconoce y su `transactionId` no coincide con ninguna solicitud, así que va a revisión como un `codiQrId` desconocido. La venta sigue `open` y sin transferencias.

## Aplicabilidad por superficie

| Superficie | Aplica | Justificación |
| --- | --- | --- |
| API | Sí | Webhook, detalle de venta y resumen diario con pagos al celular. Los contratos OpenAPI no cambian (15 sin diferencias) |
| Contrato de pey | Sí, con pey falso | Fixtures oficiales de `GET /transaction/{id}` y del webhook. Sin pey real |
| Comandos | Sí | `run-jobs` verifica un intento `phone` vencido (test) |
| Base de datos | No aplica | Sin migraciones |
| Panel | No aplica | El back office no cambia |

## B37-VC01 — API confirmación al celular

Script local de la sesión, con pey falso, bases aisladas desechables y el número sintético `5512345678`, sobre `838e033`. Los cuerpos son extractos de los campos relevantes. Los tests son la forma reproducible del mismo recorrido.

**TC01 evidencia exacta por webhook, repetida**

- `POST /sales/{id}/attempts` `{"method": "phone", "phone_number": "5512345678"}` → **201** · `{"method": "phone", "status": "pending", "next_action": "wait_for_payment", "provider_request_id": "01J5KXYZ1234567890ABCD"}`
- `GET /sales/{id}` → **200** · `{"status": "open", "confirmed_amount_cents": 0, "transfers": [], "exceptions": []}` · intentos `[('pending', 'wait_for_payment', None)]`
- `POST /webhooks/pey` `codi.pn.payment_received` exacto ×3 (mensajes `msg_vc_1`, `msg_vc_1`, `msg_vc_2`) → **[204, 204, 204]**
- `GET /sales/{id}` → **200** · `{"status": "paid", "confirmed_amount_cents": 30000, "transfers": ["01J5KXYZ1234567890ABCD"], "exceptions": []}` · intentos `[('paid', 'none', None)]`
- `GET /merchants/{id}/summary/daily?date=2026-09-29` → `{"received_amount_cents": 30000, "transfer_count": 1, "covered_sale_count": 1}`
- `transactions`: 1 · `webhook_events`: `applied,duplicate` · peticiones POST a pey: 1

**TC01 evidencia por consulta `GET /transaction/{transactionId}`**

- `POST /sales/{id}/attempts` `{"method": "phone", "phone_number": "5512345678"}` → **201** · `{"method": "phone", "status": "pending", "next_action": "wait_for_payment", "provider_request_id": "01J5KXYZ1234567890ABCD"}`
- conciliación (`GET /transaction/{id}` → `PAID`) → `confirmed` · encontrados 1, aplicados 1, duplicados 0, problema `None` · consultas `['GET /transaction/01J5KXYZ1234567890ABCD']`
- `GET /sales/{id}` → **200** · `{"status": "paid", "confirmed_amount_cents": 30000, "transfers": ["01J5KXYZ1234567890ABCD"], "exceptions": []}` · intentos `[('paid', 'none', None)]`

**TC02 sin push y transacción `PENDING`**

- `POST /sales/{id}/attempts` `{"method": "phone", "phone_number": "5512345678"}` → **201** · `{"method": "phone", "status": "pending", "next_action": "wait_for_payment", "provider_request_id": "01J5KXYZ1234567890ABCD"}`
- conciliación (`PENDING`, sin push) → `no_evidence` · encontrados 0, aplicados 0, duplicados 0, problema `None` · consultas `['GET /transaction/01J5KXYZ1234567890ABCD']`
- `GET /sales/{id}` → **200** · `{"status": "open", "confirmed_amount_cents": 0, "transfers": [], "exceptions": []}` · intentos `[('pending', 'wait_for_payment', None)]`

**TC02 consulta sin respuesta útil (404, 429, 500, timeout)**

- `POST /sales/{id}/attempts` `{"method": "phone", "phone_number": "5512345678"}` → **201** · `{"method": "phone", "status": "pending", "next_action": "wait_for_payment", "provider_request_id": "01J5KXYZ1234567890ABCD"}`
- conciliación (`404`) → `uncertain` · encontrados 0, aplicados 0, duplicados 0, problema `not_found` · consultas `['GET /transaction/01J5KXYZ1234567890ABCD']`
- conciliación (`429`) → `uncertain` · encontrados 0, aplicados 0, duplicados 0, problema `rate_limited` · consultas `['GET /transaction/01J5KXYZ1234567890ABCD']`
- conciliación (`500`) → `uncertain` · encontrados 0, aplicados 0, duplicados 0, problema `server_error` · consultas `['GET /transaction/01J5KXYZ1234567890ABCD']`
- conciliación (timeout) → `uncertain` · encontrados 0, aplicados 0, duplicados 0, problema `timeout` · consultas `['GET /transaction/01J5KXYZ1234567890ABCD']`
- `GET /sales/{id}` → **200** · `{"status": "open", "confirmed_amount_cents": 0, "transfers": [], "exceptions": []}` · intentos `[('pending', 'wait_for_payment', None)]`
- peticiones a pey en todo el escenario: 1 POST y 4 GET

**TC02 solicitud vencida sin pago: verificación y recuperación**

- `POST /sales/{id}/attempts` `{"method": "phone", "phone_number": "5512345678"}` → **201** · `{"method": "phone", "status": "pending", "next_action": "wait_for_payment", "provider_request_id": "01J5KXYZ1234567890ABCD"}`
- vence el intento (`expires_at` en el pasado)
- `GET /sales/{id}` → **200** · `{"status": "open", "confirmed_amount_cents": 0, "transfers": [], "exceptions": []}` · intentos `[('expired', 'verify_before_retry', None)]`
- conciliación (vencido, `PENDING`) → `verified` · encontrados 0, aplicados 0, duplicados 0, problema `None` · consultas `['GET /transaction/01J5KXYZ1234567890ABCD']`
- `GET /sales/{id}` → **200** · `{"status": "open", "confirmed_amount_cents": 0, "transfers": [], "exceptions": []}` · intentos `[('expired', 'new_attempt', None)]`
- `POST /sales/{id}/attempts` `{"method": "phone", "phone_number": "5512345678"}` → **201** · `{"method": "phone", "status": "pending", "next_action": "wait_for_payment", "provider_request_id": "01J5KXYZ1234567890ABCE"}`
- `previous_attempt_id` del nuevo intento = intento vencido: True

**TC03 webhook y consulta del mismo pago**

- `POST /sales/{id}/attempts` `{"method": "phone", "phone_number": "5512345678"}` → **201** · `{"method": "phone", "status": "pending", "next_action": "wait_for_payment", "provider_request_id": "01J5KXYZ1234567890ABCD"}`
- `POST /webhooks/pey` `codi.pn.payment_received` → **204**
- conciliación (misma transacción `PAID`) → `confirmed` · encontrados 1, aplicados 0, duplicados 1, problema `None` · consultas `['GET /transaction/01J5KXYZ1234567890ABCD']`
- `GET /sales/{id}` → **200** · `{"status": "paid", "confirmed_amount_cents": 30000, "transfers": ["01J5KXYZ1234567890ABCD"], "exceptions": []}` · intentos `[('paid', 'none', None)]`
- `transactions`: 1

**TC03 monto distinto (comisión incluida en `amount`)**

- `POST /sales/{id}/attempts` `{"method": "phone", "phone_number": "5512345678"}` → **201** · `{"method": "phone", "status": "pending", "next_action": "wait_for_payment", "provider_request_id": "01J5KXYZ1234567890ABCD"}`
- `POST /webhooks/pey` con `amount` = venta + 2.50 → **204**
- `GET /sales/{id}` → **200** · `{"status": "review", "confirmed_amount_cents": 30250, "transfers": ["01J5KXYZ1234567890ABCD"], "exceptions": ["amount_mismatch"]}` · intentos `[('pending', 'none', None)]`

**TC01 metadata anidada como en los ejemplos de pey, evento antes de la respuesta de `POST /codi/pn`**

- el pey falso entrega `codi.pn.payment_received` (con `metadata.externalMetadata`, sin datos de Tappy) antes de responder a `POST /codi/pn`
- `POST /sales/{id}/attempts` `{"method": "phone", "phone_number": "5512345678"}` → **201** · `{"method": "phone", "status": "paid", "next_action": "none", "provider_request_id": "01J5KXYZ1234567890ABCD"}`
- `GET /sales/{id}` → **200** · `{"status": "paid", "confirmed_amount_cents": 30000, "transfers": ["01J5KXYZ1234567890ABCD"], "exceptions": ["unassociated"]}` · intentos `[('paid', 'none', None)]`
- `webhook_events`: `applied` · excepciones abiertas: 0

**TC03 reenvíos por encima de la cuota (`TAPPY_ATTEMPT_CREATION_QUOTA=1`)**

- `POST /sales/{id}/attempts` `{"method": "phone", "phone_number": "5512345678"}` → **201** · `{"method": "phone", "status": "pending", "next_action": "wait_for_payment", "provider_request_id": "01J5KXYZ1234567890ABCD"}`
- `POST /sales/{id}/attempts` `{"method": "phone", "phone_number": "5512345678"}` → **429** · `{"detail": "Quota exceeded; try again in 58 seconds", "retry_after_seconds": 58}`
- peticiones POST a pey: 1

**Validación:**

- **TC01:** el evento exacto confirma la venta una vez (`paid`, 30000 centavos, una transferencia), el resumen diario cuenta una recepción, y la consulta `GET /transaction/{id}` con `PAID` llega al mismo resultado. Un evento con la `metadata` anidada de pey que llega antes de la respuesta de `POST /codi/pn` confirma la venta al guardar la respuesta, y su excepción `unassociated` queda resuelta.
- **TC02:** `PENDING`, `404`, `429`, `500` y un timeout dejan el intento `pending` sin `failure_code` y sin nuevas solicitudes al celular (1 POST en todo el escenario); el vencido sin pago se verifica y permite un intento nuevo enlazado al anterior.
- **TC03:** el evento repetido y la consulta del mismo pago dejan una sola transacción; un importe distinto va a revisión; la cuota limita los reenvíos sin llamar a pey. La observación real de banco/dispositivo está en #112 (BLOCKED).

Estado VC01: **PASS** (con la parte externa de TC03 fuera de alcance por decisión de producto).

## Checks

`uv run python -m quality.check` sobre la ronda 2 (`838e033` + evidencia), con `.env` exportado:

- format, lint, types (mypy strict) y hygiene: PASS;
- migrations: PASS (sin migraciones nuevas; cadena hasta `0027`);
- tests: PASS, 725 passed, con Postgres real aislado;
- api: PASS, 15 contratos sin diferencias;
- evidence: B01–B36 y B41–B42 APPROVED. B37 al 100 % y bloqueado solo porque la review está `PENDING`.

En la ronda 1 (`4169172`): format, lint, types, hygiene, migrations, tests (722 passed) y api PASS; evidence FAIL porque el manifiesto de B36 listaba los tres tests retirados (corregido en `e916498`) y B37 estaba `PENDING`. El primer `quality.check`, sobre `7f97772`, falló en `test_reception::…[changes8]` (ver «Cambios esperados en tests anteriores») y en un error intermitente de Docker Compose en `test_backup_restore` (contenedores atascados en `Created`), que pasa al repetirse.

## Umbral

AC PASS / AC aplicables = 3/3 = **100 %** (AC03 por su parte automatizada; la externa está en #112).

## Review Standards/Spec

| Ronda | Revisión | Standards | Spec | Hallazgos |
| --- | --- | --- | --- | --- |
| 1 | `e916498` | APPROVE | REQUEST_CHANGES | Standards 6 notas; Spec 3 (should-fix) + 3 notas |
| 2 | `838e033` | pendiente | pendiente | — |

### Hallazgos de la ronda 1 y su corrección (`838e033`)

1. **Evento de celular anterior a la respuesta nunca aplicado** (Spec 1; también encontrado al revisar `record_issued`). `record_issued` reaplicaba eventos en espera solo para QR → ahora para los dos canales. `test_a_payment_event_before_the_phone_request_answer_ends_confirmed` (R1).
2. **Ningún test usaba la `metadata` documentada** (Spec 2) → `push_paid_event` entrega el ejemplo oficial con su `metadata.externalMetadata` intacta, y el test de evento temprano también.
3. **Decisión de producto sin registrar en #45** (Spec 3) → [comentario en #45](https://github.com/luisjrez/Tappy/issues/45#issuecomment-7225460493).
4. **`open_sale_again` duplicaba `create_sale`** (Standards 1) → se usa `create_sale` con el comercio de la primera venta.
5. **`PAID_AT`/`PAID_DAY` sin uso y dependientes de la zona horaria** (Standards 2) → eliminados.
6. **Helpers importados desde otro módulo de tests** (Standards 3) → `tests/sales/phone_support.py`.
7. **Ajustes duplicados en el test de habilitación** (Standards 4) → `demo_list_settings("production", CONSENTED, provider="pey")`.
8. **Conteo de POST duplicado** (Standards 5) → `posted(fake)`.
9. **Despacho implícito, validación repetida e id sin comprobar** (Standards 6) → `QUERYABLE_METHODS` + mapa explícito (R3, `link` sigue `not_queryable`), un `answered(response, Model)` genérico, y una respuesta con otro `id` es `invalid_response` (R2).

Notas aceptadas sin cambio: comparar el `amount` total (con comisión) manda a revisión y nunca confirma de más (se confirma en #112); `PENDING` en un intento vencido se lee como verificado sin pago, el mismo margen que QR; renombrar `QrProvider`/`QrPayment` queda para un cambio propio.
