# Evidencia — B15 Crear QR auténtico mediante pey

Ticket: [#23](https://github.com/luisjrez/Tappy/issues/23) · Historia: [H4 #4](https://github.com/luisjrez/Tappy/issues/4) · Protocolo: [TICKET_QUALITY_PROTOCOL](../planning/TICKET_QUALITY_PROTOCOL.md) · Manifiesto: [B15-pey-qr.toml](B15-pey-qr.toml)

> **Alcance de la verificación.** Todo se verificó contra el **contrato HTTP oficial** de pey (OpenAPI `2026-10-20`) con fixtures oficiales, en tests y en un pey falso local. **No se llamó a la API real de pey** ni se usó una credencial real: eso no demuestra integración bancaria real. La verificación de extremo a extremo con un QR real es B35 (requisito externo: acceso y receptor habilitado).

## Revisiones y escenario

- Ticket, UC/AC/TC y comprobación: B15-UC01–UC03, B15-AC01–AC03, B15-TC01–TC03, B15-VC01.
- Modalidad: **resultado inicial** (adaptador nuevo). Cambios aditivos en la respuesta de intentos (`failure_code`) y en los mensajes `503`, que ahora incluyen el motivo clasificado (el test de B14 se actualizó). Contratos aprobados sin diferencias.
- Base: rama B14 `0f2f0e9` (PR #70), stack de H4 #68. Revisiones: candidato `83d61d6` → `4983d4a` (id de proveedor duplicado encontrado en la VC01, más refactor del chequeo de unicidad).
- Contrato versionado: `tests/fixtures/pey/codi-qr.json`, extraído de `https://docs.pey.mx/openapi.json` (versión `2026-10-20`, sha256 `568e0255…5c5a`) con la petición de ejemplo y todas las respuestas de `POST /codi/qr` (201, 400×5, 429, 500×2, 503).
- Entorno: macOS, Colima + Compose (Postgres 18), Python 3.14.8, httpx2 2.16.2 (movido a dependencias de ejecución; mismo lockfile). Fecha: 2026-11-24. Ejecutor: sesión local de desarrollo del autor del PR.
- Datos: receptor ficticio con `bankAccountId` de forma ULID (`01HZY3K8Q4N6V7W8X9Y0Z1A2B3`), clave sintética de prueba generada por ejecución (nunca guardada).

## Diseño

- `tappy.payments.pey.PeyQrProvider` (`name=pey`, `simulated=False`) implementa la frontera `QrProvider` de B14; la traducción del proveedor queda fuera de cobros y routers. `POST {TAPPY_PEY_BASE_URL}/codi/qr` con `Authorization: Bearer <TAPPY_PEY_API_KEY>`, timeout `TAPPY_PEY_TIMEOUT_SECONDS` y cuerpo `amount` (pesos), `bankAccountId` (instantánea del receptor del cobro), `metadata` (`tappy_attempt_id`, `tappy_reference`, para asociar eventos en H5) y `concept` si existe.
- Centavos → pesos sin floats en el dominio: `Decimal(centavos) / 100` y comprobación de que el número JSON enviado representa exactamente ese decimal (si no, no se envía).
- Respuesta 201 validada (`id` 1–64 caracteres, `qrString` no vacío): se guardan **exactos**. Clasificación: `400`/`429` con `error.type` válido → `ProviderRejectedError(code)` (definitivo: el intento pasa a `failed` con `failure_code`, API `502`); timeout, conexión, 5xx, cuerpo de error desconocido, 201 inválido o `id` ya vinculado a otro intento → `ProviderUnavailableError(reason)` (incierto: el intento queda `creating`, API `503` con el motivo; su recuperación es B16, arrastre en [#24](https://github.com/luisjrez/Tappy/issues/24#issuecomment)). Nunca se inventa un ID ni se confirma un pago.
- Configuración solo de servidor: `TAPPY_PAYMENT_PROVIDER=pey` exige `TAPPY_PEY_API_KEY` (`SecretStr`, ≥16 caracteres); `TAPPY_PEY_BASE_URL` exige `https://` salvo loopback (`127.0.0.1`/`localhost`) para no enviar la clave por HTTP; `provider_from` (ahora en `tappy.payments.factory`) construye el adaptador. La clave no aparece en respuestas, errores, `repr` ni logs.
- Migración `0011_pey_provider`: `pey` en el check de `payment_provider` y `failure_code` en los intentos.
- Refactor: `is_unique_violation` compartido en `tappy.platform.persistence` (referencia de cobro, cuenta de receptor e id de proveedor).

## Trazabilidad UC → AC → TC → test

| UC | AC | TC | Test real | Resultado |
| --- | --- | --- | --- | --- |
| B15-UC01 | B15-AC01 | B15-TC01 | `test_sends_exact_peso_amounts_and_keeps_the_official_id_and_payload` (1 → `0.01` y 30010 → `300.10` leídos como `Decimal`; id/payload oficiales intactos); `test_amounts_that_would_lose_precision_are_never_sent`; `test_omits_the_concept_when_the_sale_has_none`; `test_pey_qr_is_stored_with_the_official_id_and_payload` (API: `pending`, `simulated: false`, id y payload oficiales, proveedor `pey`) | PASS |
| B15-UC02 | B15-AC02 | B15-TC02 | `test_invalid_creation_responses_never_invent_an_identifier` (6 casos); `test_official_rejections_are_classified_by_type` (5 fixtures 400); `test_rate_limit_is_a_definitive_rejection`; `test_server_errors_and_unknown_errors_are_uncertain` (503, 500×2, 400 desconocido); `test_timeouts_and_connection_failures_are_uncertain`; `test_definitive_rejection_fails_the_attempt_with_its_code` (API 502, `failed`, `INVALID_AMOUNT`); `test_uncertain_response_keeps_the_attempt_creating`; `test_a_provider_id_already_linked_to_another_attempt_is_uncertain` | PASS |
| B15-UC03 | B15-AC03 | B15-TC03 | `test_request_targets_the_snapshotted_receiver_and_links_the_attempt` (cuerpo exacto con `bankAccountId` y metadatos); `test_credentials_never_reach_logs_errors_or_representations` (hay registros y ninguno contiene la clave); `test_adapter_is_labelled_as_the_real_provider`; `test_pey_settings_require_a_server_side_key`; `test_pey_base_url_requires_tls_outside_loopback` (6 casos) | PASS |

## TDD

| Comportamiento | Red | Green |
| --- | --- | --- |
| Adaptador, clasificación, flujo y configuración | Con la frontera y un `PeyQrProvider` vacío (sin petición), 28 tests fallan por comportamiento: no se enviaba nada, no había id/payload, ni rechazos clasificados, ni `502`, ni configuración `pey` | `PeyQrProvider`, `provider_from`, `failure_code`, mapeo `502`/`503` |
| URL con TLS salvo loopback | `String should match pattern '^https://'` para `http://127.0.0.1:8899` y `http://localhost:8899` | Patrón `PEY_BASE_URL` |
| Id de proveedor ya vinculado (hallado en la VC01) | `UniqueViolation uq_payment_attempts_provider_request` sin manejar (500) | `duplicate_provider_id` → `503`, intento `creating` |
| Precisión al serializar | Escrito tras la comprobación; mutación sin ella: `Failed: DID NOT RAISE ValueError` | Comprobación `Decimal(repr(sent)) == exact` |
| Clasificación 400 | Mutación que trata 400 como incierto: 5 tests fallan | `REJECTED_STATUSES = {400, 429}` |

Mutación sin efecto, registrada: `strict=False` en `CreatedQr` no cambia ningún resultado (Pydantic v2 tampoco convierte `int` a `str` en modo laxo); `strict=True` se conserva como defensa, sin atribuirle cobertura.

## B15-VC01 — Resultado inicial contra el contrato HTTP

Proceso real `python -m tappy` sobre `4983d4a` con `TAPPY_PAYMENT_PROVIDER=pey`, `TAPPY_PEY_BASE_URL=http://127.0.0.1:8899` y una clave sintética generada para la ejecución; un pey falso local responde con las respuestas del fixture oficial (o con la forma oficial y otro `id`) y registra cada petición recibida. Valores sintéticos sin normalizar.

| Petición | Status | Respuesta |
| --- | --- | --- |
| QR de 1 centavo (pey responde 201 oficial) | 201 | `{"id": "d1d14c64-21d0-497d-9c7b-8a396639a690", "sale_id": "9f7d8d89-98e3-4f2e-ac6f-00379da5d42e", "sale_reference": "1BPW03PZ50", "method": "qr", "status": "pending", "simulated": false, "provider_request_id": "AB12CD34EF", "qr_payload": "{\"TYP\":1,\"v\":\"01\",\"ic\":0,\"IDC\":\"AB12CD34EF\"}", "failure_code": null, "created_at": "2026-11-24T18:51:06.491840Z"}` |
| QR de 30010 centavos con concepto (201 con la forma oficial y otro id) | 201 | `{"id": "cbbaf88c-5351-4be1-90ec-5b97bcb6368b", "sale_id": "c4d5df3a-c98b-4400-bfc7-36b1c9ca17db", "sale_reference": "PH2N2RKHMX", "method": "qr", "status": "pending", "simulated": false, "provider_request_id": "CD34EF56GH", "qr_payload": "{\"TYP\":1,\"v\":\"01\",\"ic\":0,\"IDC\":\"CD34EF56GH\"}", "failure_code": null, "created_at": "2026-11-24T18:51:06.536467Z"}` |
| `GET /sales/{id}` del cobro de 30010 | 200 | `{"id": "c4d5df3a-c98b-4400-bfc7-36b1c9ca17db", "merchant_id": "c70f71db-1572-47b9-b5e6-9e373c3834ab", "reference": "PH2N2RKHMX", "amount_cents": 30010, "currency": "MXN", "concept": "Dos tacos", "status": "open", "beneficiary_name": "Tienda Demo A SA de CV", "masked_account": "**************6782", "created_at": "2026-11-24T18:51:06.529965Z", "attempts": [{"id": "cbbaf88c-5351-4be1-90ec-5b97bcb6368b", "sale_id": "c4d5df3a-c98b-4400-bfc7-36b1c9ca17db", "sale_reference": "PH2N2RKHMX", "method": "qr", "status": "pending", "simulated": false, "provider_request_id": "CD34EF56GH", "qr_payload": "{\"TYP\":1,\"v\":\"01\",\"ic\":0,\"IDC\":\"CD34EF56GH\"}", "failure_code": null, "created_at": "2026-11-24T18:51:06.536467Z"}]}` |
| QR al que pey devuelve un id ya vinculado (CD34EF56GH) | 503 | `{"detail": "The QR provider is unavailable (duplicate_provider_id); the attempt is kept for reconciliation"}` |
| QR con rechazo oficial 400 `INVALID_AMOUNT` | 502 | `{"detail": "The QR provider rejected the request (INVALID_AMOUNT)"}` |
| `GET /sales/{id}` del cobro rechazado | 200 | `{"id": "c8b1afff-0307-45ef-bc0c-6e7f787c79cf", "merchant_id": "c70f71db-1572-47b9-b5e6-9e373c3834ab", "reference": "W87Y4QPYNN", "amount_cents": 1500, "currency": "MXN", "concept": null, "status": "open", "beneficiary_name": "Tienda Demo A SA de CV", "masked_account": "**************6782", "created_at": "2026-11-24T18:51:06.575125Z", "attempts": [{"id": "8a8fe419-08c5-4665-be4e-ebd83b2c405d", "sale_id": "c8b1afff-0307-45ef-bc0c-6e7f787c79cf", "sale_reference": "W87Y4QPYNN", "method": "qr", "status": "failed", "simulated": false, "provider_request_id": null, "qr_payload": null, "failure_code": "INVALID_AMOUNT", "created_at": "2026-11-24T18:51:06.581328Z"}]}` |
| QR con respuesta 201 sin `id` | 503 | `{"detail": "The QR provider is unavailable (invalid_response); the attempt is kept for reconciliation"}` |
| `GET /sales/{id}` del cobro incierto | 200 | `{"id": "be761b80-4549-4520-9f42-43fd51ced9e5", "merchant_id": "c70f71db-1572-47b9-b5e6-9e373c3834ab", "reference": "DBEBKS7KMC", "amount_cents": 2500, "currency": "MXN", "concept": null, "status": "open", "beneficiary_name": "Tienda Demo A SA de CV", "masked_account": "**************6782", "created_at": "2026-11-24T18:51:06.597779Z", "attempts": [{"id": "d21e8e19-7a38-4021-bbab-03b6d408c71c", "sale_id": "be761b80-4549-4520-9f42-43fd51ced9e5", "sale_reference": "DBEBKS7KMC", "method": "qr", "status": "creating", "simulated": false, "provider_request_id": null, "qr_payload": null, "failure_code": null, "created_at": "2026-11-24T18:51:06.605518Z"}]}` |

Peticiones recibidas por el pey falso (`auth_matches`: el Bearer coincide con la clave configurada; la clave no se registra):

```json
{"path": "/codi/qr", "auth_matches": true, "body": "{\"amount\":0.01,\"bankAccountId\":\"01HZY3K8Q4N6V7W8X9Y0Z1A2B3\",\"metadata\":{\"tappy_attempt_id\":\"d1d14c64-21d0-497d-9c7b-8a396639a690\",\"tappy_reference\":\"1BPW03PZ50\"}}"}
{"path": "/codi/qr", "auth_matches": true, "body": "{\"amount\":300.1,\"bankAccountId\":\"01HZY3K8Q4N6V7W8X9Y0Z1A2B3\",\"metadata\":{\"tappy_attempt_id\":\"cbbaf88c-5351-4be1-90ec-5b97bcb6368b\",\"tappy_reference\":\"PH2N2RKHMX\"},\"concept\":\"Dos tacos\"}"}
{"path": "/codi/qr", "auth_matches": true, "body": "{\"amount\":40.0,\"bankAccountId\":\"01HZY3K8Q4N6V7W8X9Y0Z1A2B3\",\"metadata\":{\"tappy_attempt_id\":\"82de2d45-51ed-4920-96d9-c9e7f40f458e\",\"tappy_reference\":\"Z66FA8JPJF\"}}"}
{"path": "/codi/qr", "auth_matches": true, "body": "{\"amount\":15.0,\"bankAccountId\":\"01HZY3K8Q4N6V7W8X9Y0Z1A2B3\",\"metadata\":{\"tappy_attempt_id\":\"8a8fe419-08c5-4665-be4e-ebd83b2c405d\",\"tappy_reference\":\"W87Y4QPYNN\"}}"}
{"path": "/codi/qr", "auth_matches": true, "body": "{\"amount\":25.0,\"bankAccountId\":\"01HZY3K8Q4N6V7W8X9Y0Z1A2B3\",\"metadata\":{\"tappy_attempt_id\":\"d21e8e19-7a38-4021-bbab-03b6d408c71c\",\"tappy_reference\":\"DBEBKS7KMC\"}}"}
```

Comprobaciones: `amount` `0.01` y `300.1` (= 300.10 MXN) para 1 y 30010 centavos; `bankAccountId` = cuenta del receptor del cobro; la clave aparece **0** veces en el log del servidor de Tappy y en las respuestas. Estado final en la base: `attempts [('pending', 'pey', 'AB12CD34EF', None), ('pending', 'pey', 'CD34EF56GH', None), ('creating', 'pey', None, None), ('failed', 'pey', None, 'INVALID_AMOUNT'), ('creating', 'pey', None, None)]`. Las líneas INFO del adaptador no aparecen en el log del proceso porque la app aún no configura logging (fuera de alcance; B34); el test las comprueba con `caplog`. Datos y procesos eliminados al terminar. Estado VC01: **PASS** (resultado inicial; sin pago confirmado).

## Checks

`uv run python -m quality.check` sobre `4983d4a` (con `.env` exportado): PASS format, lint, types (mypy strict), hygiene, migrations (upgrade/downgrade/upgrade + `alembic check`), tests (305 passed, Postgres real aislado), api (15 contratos sin diferencias).

## Supresiones

Sin supresiones nuevas.

## Umbral

AC PASS / AC aplicables = 3/3 = **100%**.

## Review Standards/Spec

Pendiente.
