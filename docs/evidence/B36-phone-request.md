# Evidencia — B36 Crear solicitud al celular

Ticket: [#44](https://github.com/luisjrez/Tappy/issues/44) · Historia: [H8 #8](https://github.com/luisjrez/Tappy/issues/8) · Protocolo: [TICKET_QUALITY_PROTOCOL](../planning/TICKET_QUALITY_PROTOCOL.md) · Manifiesto: [B36-phone-request.toml](B36-phone-request.toml)

> Verificado con números sintéticos (los del ejemplo oficial de pey), un pey falso que responde con el ejemplo oficial de `POST /codi/pn` y Postgres aislado. **No hubo llamadas a pey real; una simulación no demuestra la integración.** La habilitación real depende del contrato y de los accesos de pey (requisito externo de #44, y B35 bloqueado).

## Revisiones y escenario

- **Trazabilidad:** B36-UC01–UC03, B36-AC01–AC03 y B36-VC01. Superficie: API de solicitudes al celular y contrato de pey.
- **Modalidad:** resultado inicial. El canal `phone` existía en el enum, pero no llamaba a ningún proveedor.
- **Base y revisiones:**
  - Base: rama B34 `6a474a8` ([PR #110](https://github.com/luisjrez/Tappy/pull/110)), stack #68.
  - Candidato de la ronda 1: `9dfb78e` (función) + `669f3da` (ajuste de tests anteriores).
  - Candidato de la ronda 2: `3698a3f` (correcciones de la ronda 1).
- **Entorno:** macOS, Postgres 18.6 aislado (Colima + Compose) y Python 3.14.8. Fecha: 2026-11-25 (UTC). Ejecutor: sesión local de desarrollo del autor del PR.

## Contrato de pey usado

- **Fixture:** `tests/fixtures/pey/codi-pn.json` se generó desde `https://docs.pey.mx/openapi.json`, versión `2026-10-20`, el mismo `sha256` (`568e0255…5c5a`) que el fixture de QR.
- **Petición:** `POST /codi/pn` con `amount` y `phoneNumber` (`^[0-9]{10}$`) obligatorios, más `expiration` (mínimo y valor por defecto 360), `bankAccountId`, `metadata` y `concept`.
- **Respuestas:**
  - `200` con `transactionId` (ULID) y `codiId` (folio Banxico de 20 dígitos);
  - `400` (`INVALID_PARAMETER`, `INVALID_STATE`, …) y `429` (`CALL_LIMIT_REACHED`);
  - `500` y `503`.
- **Lo que pey no documenta:** idempotencia de creación y eventos de entrega, lectura, rechazo o vencimiento. Solo documenta `codi.pn.payment_received`, que llega en B37. Por eso la API nunca afirma entrega ni lectura.

## Diseño

- **Formato del número aislado** (`tappy.platform.phones`):
  - acepta espacios, puntos, guiones y el prefijo `52`/`+52`, y reduce a 10 dígitos ASCII;
  - todo lo demás (9 u 11 dígitos, letras, otros países, dígitos de ancho completo) se rechaza.
- **Habilitación condicionada:** `TAPPY_PHONE_REQUEST_NUMBERS` es la lista de números de prueba consentidos, de 10 dígitos cada uno y validados al arrancar.
  - **Solo en `TAPPY_ENVIRONMENT=test` hasta que exista verificación** (B37). En cualquier otro ambiente la aplicación no arranca con la lista.
  - El motivo: hoy un intento `phone` no se puede consultar, así que si vence sin pago o pierde la respuesta bloquearía la venta para siempre. Un intento vencido exige verificación antes de otro, y uno `reconciling` sigue activo.
  - Permitir otro intento sin verificar podría cobrar dos veces, así que el canal no se puede habilitar en vivo.
  - Vacía (el valor por defecto) → `409 Phone payment requests are not enabled`.
  - Un número fuera de la lista → `422`.
  - Ningún mensaje repite el número.
- **Validación antes de reservar:**
  - número ausente en `phone`, número presente en otro método, número mal formado o no permitido → error;
  - en todos esos casos no se reserva intento, no se consume cuota y no se llama a pey.
- **Mismo motor de intentos:** clave de idempotencia, cuota, receptor e intento activo.
  - La huella de la clave incluye un HMAC del número con `TAPPY_SECRET_KEY`, así que la misma clave con otro número da `409`.
  - La huella no se puede invertir probando los 10^10 números (arquitectura §11: «hash con clave»).
- **Proveedor:**
  - `QrProvider.request_phone_payment(PhoneOrder) -> IssuedPhoneRequest`;
  - el simulador devuelve ids `SIM-…`;
  - el adaptador de pey llama a `POST /codi/pn` con el mismo cuerpo que el QR más `phoneNumber`;
  - con `200` válido el intento pasa a `pending`;
  - `400`/`429` es un rechazo definitivo: el intento queda `failed` con el código, y la API responde `502`;
  - un timeout, un fallo de conexión, un `5xx` o una respuesta inválida dejan el intento en `reconciling` con su trabajo (`202`), sin inventar ids.
- **Lo que se conserva:**
  - `provider_request_id` = `transactionId`, y `provider_folio` = `codiId` (migración `0025`);
  - solo los últimos 4 dígitos del número (`payer_phone_suffix`), que la API muestra como `payer_phone: "******5678"`;
  - el número completo no se guarda en la base, ni en respuestas ni en logs, y además la redacción de B34 enmascararía cualquier teléfono.
- **Estado:** `pending` con `next_action: wait_for_payment` (`wait_for_request` mientras se crea, `none` si se retira). No hay campos de entrega ni de lectura.
- **Un solo camino de registro:** `record_issued` y `attach_issued` sirven a QR y a celular, con la misma retención del id, el mismo conflicto y el mismo aviso cuando el id llega tarde. Los nombres compartidos son neutros (`creation_body`, `record_rejected`, `conflicting_request`, `post(path, body)`).
- **Fuera de alcance (B37):** confirmar el pago y consultarlo en pey. Para no consultar el endpoint de QR con un id de push, la conciliación trata los intentos `phone` como no consultables (`not_queryable`).

## Trazabilidad UC → AC → TC

| UC | AC | TC | Tests | Resultado |
| --- | --- | --- | --- | --- |
| B36-UC01 | B36-AC01 | B36-TC01 | `test_a_consented_number_creates_a_pending_request_that_keeps_the_provider_ids`:<br>• `201`, `pending`, `wait_for_payment`, `transactionId` y `codiId` conservados, referencia de venta y `******5678`;<br>• sin campos de entrega o lectura;<br>• el cuerpo enviado a pey cumple el esquema oficial;<br>• ninguna fila de intentos contiene el número completo.<br>Además `test_the_simulated_provider_creates_a_marked_pending_request`, `test_a_phone_number_is_normalized_to_ten_digits`, `test_the_number_is_only_kept_behind_a_keyed_fingerprint` (la huella guardada es el HMAC, no un `sha256` sin clave, y ninguna fila de idempotencia contiene el número) y `test_a_withdrawn_phone_request_asks_for_no_action` | PASS |
| B36-UC02 | B36-AC02 | B36-TC02 | `test_an_invalid_number_is_rejected_without_an_attempt_or_a_provider_request`, `test_the_number_is_required_for_phone_requests_and_refused_for_qr`, `test_a_number_outside_the_demo_list_is_refused_without_a_provider_request`, `test_phone_requests_stay_disabled_until_numbers_are_configured`, `test_a_malformed_phone_number_is_refused`, `test_the_demo_list_only_accepts_ten_digit_numbers`, `test_phone_requests_cannot_be_enabled_until_their_payments_can_be_verified` y `test_a_phone_request_conflicts_with_an_active_attempt_without_calling_the_provider`. En todos, 0 intentos y 0 peticiones a pey | PASS |
| B36-UC03 | B36-AC03 | B36-TC03 | `test_a_lost_provider_answer_keeps_one_verifying_attempt_and_the_retry_does_not_resend`:<br>• timeout → `202 reconciling` con trabajo `timeout:pending`;<br>• misma clave → `200`, el mismo intento y una sola petición a pey;<br>• misma clave con otro número → `409`.<br>Además `test_a_server_error_or_an_unusable_answer_keeps_the_request_verifying`, `test_a_definitive_rejection_fails_the_phone_request_with_its_code` `test_a_phone_request_is_never_queried_through_the_qr_payments_endpoint` y `test_an_expired_phone_request_blocks_new_attempts_until_payments_can_be_verified`, que documenta el bloqueo por el que el canal queda solo para tests | PASS |

## TDD

**Red** sobre la base, con un módulo `phones` que rechaza todo: fallan 18 de 32.

```
FAILED tests/sales/test_phone_requests.py::test_a_consented_number_creates_a_pending_request_that_keeps_the_provider_ids
FAILED tests/sales/test_phone_requests.py::test_the_number_is_required_for_phone_requests_and_refused_for_qr[payload0]
FAILED tests/sales/test_phone_requests.py::test_a_number_outside_the_demo_list_is_refused_without_a_provider_request
FAILED tests/sales/test_phone_requests.py::test_phone_requests_stay_disabled_until_numbers_are_configured
FAILED tests/sales/test_phone_requests.py::test_a_lost_provider_answer_keeps_one_verifying_attempt_and_the_retry_does_not_resend
FAILED tests/sales/test_phone_requests.py::test_a_definitive_rejection_fails_the_phone_request_with_its_code[400-example0-INVALID_PARAMETER]
FAILED tests/sales/test_phone_requests.py::test_a_definitive_rejection_fails_the_phone_request_with_its_code[400-example1-INVALID_STATE]
FAILED tests/sales/test_phone_requests.py::test_a_definitive_rejection_fails_the_phone_request_with_its_code[429-example2-CALL_LIMIT_REACHED]
FAILED tests/sales/test_phone_requests.py::test_a_server_error_or_an_unusable_answer_keeps_the_request_verifying[answer0]
FAILED tests/sales/test_phone_requests.py::test_a_server_error_or_an_unusable_answer_keeps_the_request_verifying[answer1]
FAILED tests/sales/test_phone_requests.py::test_a_server_error_or_an_unusable_answer_keeps_the_request_verifying[answer2]
FAILED tests/sales/test_phone_requests.py::test_a_server_error_or_an_unusable_answer_keeps_the_request_verifying[answer3]
FAILED tests/sales/test_phone_requests.py::test_the_simulated_provider_creates_a_marked_pending_request
FAILED tests/sales/test_phone_requests.py::test_a_phone_number_is_normalized_to_ten_digits[5512345678-5512345678]
FAILED tests/sales/test_phone_requests.py::test_a_phone_number_is_normalized_to_ten_digits[55 1234 5678-5512345678]
FAILED tests/sales/test_phone_requests.py::test_a_phone_number_is_normalized_to_ten_digits[55-1234-5678-5512345678]
FAILED tests/sales/test_phone_requests.py::test_a_phone_number_is_normalized_to_ten_digits[+52 55 1234 5678-5512345678]
FAILED tests/sales/test_phone_requests.py::test_a_phone_number_is_normalized_to_ten_digits[525512345678-5512345678]
18 failed, 14 passed in 9.22s
```

- **Los 14 que ya pasaban, por un motivo ajeno a la función:**
  - el esquema rechazaba cualquier campo desconocido (`phone_number`) con `422`;
  - la configuración rechazaba un ajuste desconocido.
- **Su eficacia:** la prueban las mutaciones M1–M4, M10 y M12.
- **Test añadido después:** `test_a_phone_request_is_never_queried_through_the_qr_payments_endpoint` falló primero (`IndexError`: la conciliación consultaba a pey) y después pasó con la guarda.
- **Conflicto con intento activo:** se escribió al mover el caso desde B13 y pasa sin cambios, porque lo da el motor de intentos.

**Mutaciones** sobre `9dfb78e`, con `tests/sales/test_phone_requests.py`:

```
M1 numero fuera de la lista aceptado: 1 failed, 32 passed in 10.23s
M2 canal sin lista habilitado: 1 failed, 32 passed in 10.19s
M3 formato sin fullmatch: 2 failed, 31 passed in 10.04s
M4 clave sin el numero: 1 failed, 32 passed in 9.98s
M5 accion de QR para celular: 2 failed, 31 passed in 10.13s
M6 respuesta 200 de pey tratada como incierta: 1 failed, 32 passed in 10.33s
M7 sin numero en la peticion a pey: 1 failed, 32 passed in 10.42s
M8 celular consultado por el endpoint de QR: 1 failed, 32 passed in 10.26s
M9 folio no guardado: 2 failed, 31 passed in 10.38s
M10 numero aceptado en un QR: 1 failed, 32 passed in 12.16s
M11 rechazo de pey tratado como incierto: 3 failed, 30 passed in 10.53s
M12 lista sin validar: 1 failed, 32 passed in 11.64s
```

**Ronda 2 (`3698a3f`):** el Red sobre `669f3da` no aísla las correcciones, porque los tests nuevos pasan la lista como `frozenset`, el tipo nuevo del ajuste, y el código anterior responde `500`. Por eso el Red de esta ronda se demuestra revirtiendo cada corrección sobre el candidato (R1–R4), y las M1–M12 se repiten sobre `3698a3f`:

```
R1 sin restriccion de ambiente: 3 failed, 37 passed in 12.85s
R2 huella sin clave: 1 failed, 39 passed in 12.88s
R3 retirado de celular con accion de QR: 1 failed, 39 passed in 12.71s
R4 pending_order sin numero en silencio: 40 passed in 13.05s
M1 numero fuera de la lista aceptado: 1 failed, 39 passed in 12.94s
M2 canal sin lista habilitado: 1 failed, 39 passed in 13.24s
M3 formato sin fullmatch: 2 failed, 38 passed in 13.02s
M4 clave sin el numero: 2 failed, 38 passed in 12.92s
M5 accion de QR para celular: 2 failed, 38 passed in 13.49s
M6 respuesta 200 de pey tratada como incierta: 3 failed, 37 passed in 13.48s
M7 sin numero en la peticion a pey: 1 failed, 39 passed in 12.95s
M8 celular consultado por el endpoint de QR: 1 failed, 39 passed in 13.05s
M9 folio no guardado: 2 failed, 38 passed in 12.68s
M10 numero aceptado en un QR: 1 failed, 39 passed in 13.07s
M11 rechazo de pey tratado como incierto: 3 failed, 37 passed in 12.61s
M12 lista sin validar: 1 failed, 39 passed in 12.80s
```

- **R4 sobrevive a propósito.** El router ya exige el número para `phone`, así que la excepción de `pending_order` es una comprobación defensiva sin camino posible desde la API.
- **Hallazgo de la ronda 1 confirmado:** con R1 revertido, el canal se podría habilitar en `local`, `integration` o `production`.

## Cambios esperados en tests anteriores (`669f3da`)

B13 y B14 usaban `phone` como canal «inerte» que se reserva sin llamar a ningún proveedor. B36 es justo lo que lo activa:

- `test_attempt_reservation.py` (reserva en `creating`, concurrencia y reinicio) y `test_simulated_qr.py` (canal sin proveedor) pasan a usar `link`, que sigue inerte.
- El JSON esperado del intento añade `provider_folio` y `payer_phone`, ambos `null`.
- El conflicto con un intento activo, que se probaba para `phone` sin número, ahora lo prueba B36 con un número válido: `409` y ninguna llamada a pey.

## Aplicabilidad por superficie

| Superficie | Aplica | Justificación |
| --- | --- | --- |
| API | Sí | Petición, status y JSON de solicitudes al celular. Los contratos existentes no cambian: los 15 son sin autenticación. El OpenAPI añade campos y una respuesta `422` documentada |
| Contrato de pey | Sí, con pey falso | Fixture oficial. Sin pey real |
| Base de datos | Sí | Migración `0025` con dos columnas nulas |
| Panel | No aplica | El back office no cambia |

## B36-VC01 — API celular

Script local de la sesión, con pey falso y bases aisladas desechables. Repetido sobre `3698a3f`. Los cuerpos son extractos de los campos relevantes. El test es la forma reproducible del mismo recorrido.

**TC01 número consentido (pey falso con el ejemplo oficial de `POST /codi/pn`)**

- `POST /sales/{id}/attempts` `{"method": "phone", "phone_number": "55 1234 5678"}` → **201** · `{"method": "phone", "status": "pending", "next_action": "wait_for_payment", "provider_request_id": "01J5KXYZ1234567890ABCD", "provider_folio": "12345678901234567890", "payer_phone": "******5678", "qr_payload": null, "expires_at": "<created_at + 360 s>"}` · peticiones a pey: 1
- intentos en la base: 1
- cuerpo enviado a pey: `{"amount": 300.0, "bankAccountId": "bank-account-demo-a", "expiration": 360, "metadata": "<id de intento y referencia>", "phoneNumber": "5512345678"}`
- `GET /sales/{id}` → intentos `[('pending', 'wait_for_payment', '******5678')]`
- filas de `payment_attempts` que contienen el número completo: 0

**TC02 número inválido, ausente, en un QR o fuera de la lista**

- `POST /sales/{id}/attempts` `{"method": "phone", "phone_number": "551234567"}` → **422** · `{"detail": "The phone number must have 10 digits"}` · peticiones a pey: 0
- `POST /sales/{id}/attempts` `{"method": "phone"}` → **422** · `{"detail": "Phone requests need a phone number"}` · peticiones a pey: 0
- `POST /sales/{id}/attempts` `{"method": "qr", "phone_number": "5512345678"}` → **422** · `{"detail": "A phone number is only accepted for phone requests"}` · peticiones a pey: 0
- `POST /sales/{id}/attempts` `{"method": "phone", "phone_number": "5599990000"}` → **422** · `{"detail": "The phone number is not permitted for payment requests"}` · peticiones a pey: 0
- intentos en la base: 0

**TC02 canal sin números configurados**

- `POST /sales/{id}/attempts` `{"method": "phone", "phone_number": "5512345678"}` → **409** · `{"detail": "Phone payment requests are not enabled"}` · peticiones a pey: 0
- intentos en la base: 0

**TC03 pey acepta pero la respuesta se pierde (timeout), reintento con la misma clave**

- `POST /sales/{id}/attempts` `{"method": "phone", "phone_number": "5512345678"}` → **202** · `{"method": "phone", "status": "reconciling", "next_action": "wait_for_verification", "provider_request_id": null, "provider_folio": null, "payer_phone": "******5678", "qr_payload": null, "expires_at": null}` · peticiones a pey: 1
- `POST /sales/{id}/attempts` `{"method": "phone", "phone_number": "5512345678"}` → **200** · `{"method": "phone", "status": "reconciling", "next_action": "wait_for_verification", "provider_request_id": null, "provider_folio": null, "payer_phone": "******5678", "qr_payload": null, "expires_at": null}` · peticiones a pey: 1
- `POST /sales/{id}/attempts` `{"method": "phone", "phone_number": "5587650000"}` → **409** · `{"detail": "Idempotency key already used with different content"}` · peticiones a pey: 1
- `GET /sales/{id}` → intentos `[('reconciling', 'wait_for_verification')]`
- trabajo de conciliación: `timeout:pending`

**Validación:**

- **TC01:** se conservan el id (`transactionId`) y la referencia (folio `codiId` y referencia de venta); el estado es pendiente, sin afirmar entrega ni lectura; el número aparece enmascarado y nunca completo en la base.
- **TC02:** cuatro entradas inválidas y el canal sin configurar dan error, con 0 intentos y 0 peticiones a pey.
- **TC03:** la respuesta perdida deja un solo intento verificándose; el reintento no vuelve a emitir y otra solicitud con la misma clave se rechaza.

Estado VC01: **PASS**.

## Checks

`uv run python -m quality.check` sobre `3698a3f`, con `.env` exportado (en la ronda 1, sobre `669f3da`, dio PASS con 649 tests):

- format, lint, types (mypy strict) y hygiene: PASS;
- migrations: PASS, con `0025` aplicada, revertida hasta la base, reaplicada e igual a los modelos;
- tests: PASS, 655 passed, con Postgres real aislado;
- api: PASS, 15 contratos sin diferencias;
- evidence: B01–B34 APPROVED. B35 está BLOQUEADO a propósito y vive en su PR borrador fuera de esta rama, así que su manifiesto no está aquí. B36 queda bloqueado solo porque la review está `PENDING`.

El primer `quality.check`, sobre `9dfb78e`, falló en los 6 tests de B13/B14 que usaban `phone` como canal inerte. Se ajustaron en `669f3da` (ver «Cambios esperados en tests anteriores»).

## Umbral

AC PASS / AC aplicables = 3/3 = **100 %**.

## Review Standards/Spec

| Ronda | Revisión | Standards | Spec | Hallazgos |
| --- | --- | --- | --- | --- |
| 1 | `669f3da` | REQUEST_CHANGES | REQUEST_CHANGES | Standards 3 + 4 notas, Spec 2 + 2 notas (ver abajo) |
| 2 | `3698a3f` | PENDING | PENDING | — |

### Hallazgos de la ronda 1 y su corrección (`3698a3f`)

1. **Una venta queda sin salida tras un intento `phone` vencido o sin respuesta** (Standards 1 y Spec 1). Se eligió la opción 1 de Spec: el canal solo se acepta en `TAPPY_ENVIRONMENT=test` hasta que B37 permita verificar.
   - `test_phone_requests_cannot_be_enabled_until_their_payments_can_be_verified` comprueba el rechazo en `local`, `integration` y `production`.
   - `test_an_expired_phone_request_blocks_new_attempts_until_payments_can_be_verified` documenta el bloqueo.
   - README y evidencia explican el motivo. La opción 2 (dejar pasar sin verificar) se descartó por el riesgo de cobrar dos veces.
2. **Número recuperable desde la huella de idempotencia** (Standards 2 y Spec 2) → HMAC con `TAPPY_SECRET_KEY` (`phone_fingerprint`). El test comprueba que la huella guardada es la con clave, no la sin clave, y que ninguna fila de `idempotency_requests` contiene el número.
3. **Registro duplicado sin el aviso de llegada tardía** (Standards 3) → un solo `record_issued`/`attach_issued`, que conserva el aviso.
4. **Nombres de QR en caminos compartidos** (Standards, nota) → `creation_body`, `record_rejected`, `conflicting_request`, `record_uncertain` y `post(path, body)`.
5. **Lista parseada en cada petición** (Standards, nota) → el campo ya es `frozenset[str]` (`NoDecode` y un validador `before`).
6. **Constante literal en la máscara** (Standards, nota) → `PHONE_DIGITS - VISIBLE_DIGITS`.
7. **`pending_order` callaba la falta de número** (Standards, nota) → ahora lanza un error explícito (R4).
8. **`429` de `/codi/pn` tratado como definitivo** (Spec, nota). Es la misma pregunta abierta que B15 arrastró a B35, y se suma a su paso 4 (comentario en #43): si un `429` de `/codi/pn` pudo crear la solicitud, reintentar enviaría otra al pagador.
9. **Intento retirado con `hide_qr`** (Spec, nota) → para `phone` es `none`, con su test.
