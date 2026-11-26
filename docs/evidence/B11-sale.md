# Evidencia — B11 Crear y consultar un cobro

Ticket: [#19](https://github.com/luisjrez/Tappy/issues/19) · Historia: [H4 #4](https://github.com/luisjrez/Tappy/issues/4) · Protocolo: [TICKET_QUALITY_PROTOCOL](../planning/TICKET_QUALITY_PROTOCOL.md) · Manifiesto: [B11-sale.toml](B11-sale.toml)

## Revisiones y escenario

- Ticket, UC/AC/TC y comprobación: B11-UC01–UC03, B11-AC01–AC03, B11-TC01–TC03, B11-VC01.
- Modalidad: **resultado inicial** (API de cobros nueva). Contratos existentes sin diferencias; nuevos `sale-create-unauthenticated` y `sale-read-unauthenticated` (401) aprobados en `6629897`. Cambio esperado en un test existente: `test_there_is_no_public_sign_up_route` fija las rutas POST públicas y ahora incluye `/sales`.
- Base: `main` `9279430` (B01–B10 mergeados). Primer PR del stack de H4. Revisiones: candidato `6629897` → correcciones de review `f676cde` (revisión final). VC01 se ejecutó sobre `6629897`; `f676cde` no cambia ninguna respuesta (solo reintenta una colisión de referencia y comparte el formateo de la cuenta enmascarada).
- Entorno: macOS, Colima + Compose (Postgres 18), Python 3.14.8. Fecha: 2026-11-24. Ejecutor: sesión local de desarrollo del autor del PR.
- Datos: comercios «Tienda Demo A/B», identidades sintéticas `@tappy.example`, referencias `bank-account-demo-*` y CLABE ficticias con dígito verificador válido. Crear un cobro **no** emite ninguna solicitud bancaria ni implica pago (ver H4: B14/B15 crean el QR).

## Diseño

- Dominio `tappy.sales`: `Sale` (migración `0007_sales`) con `amount_cents` entero, `currency` fija `MXN`, `concept` opcional, `reference` única de 10 caracteres (alfabeto Crockford base32, `secrets`; restricción `uq_sales_reference` y hasta 3 referencias nuevas, cada una en su savepoint, si una colisiona), `status` `open` (los estados `paid`/`review` existen para B18+), `created_by` (operador que lo pidió) y una **instantánea del receptor** (`receiving_account_id`, `beneficiary_name`, `account_last4`).
- Reglas monetarias fuera del transporte: `tappy.sales.money.validated_amount` (1..máximo, solo enteros). El esquema usa `StrictInt` (rechaza `1.5`, `30000.0`, `"30000"`, `true`) y nunca se convierte a float. El máximo es `TAPPY_SALE_MAX_AMOUNT_CENTS` (por defecto y tope 100000000 = 1 000 000 MXN, el máximo documentado por pey para cobros; ver [OpenAPI de pey](https://docs.pey.mx/openapi.json), `/codi/pn` `amount.maximum`). El tope de la demo sigue pendiente de D18 y se baja por configuración.
- Concepto: espacios colapsados, vacío → `null`, máximo 40 caracteres (límite que pey documenta para el concepto mostrado al pagador en `/codi/qr`); nunca se trunca.
- Inmutabilidad del importe emitido: no hay ruta de modificación (`PATCH`/`PUT` → 405) y un trigger `sales_freeze_terms` rechaza en la base cualquier cambio de comercio, autor, importe, moneda, concepto, referencia o instantánea del receptor; `ck_sales_amount_cents_positive` y `ck_sales_currency_mxn` refuerzan los invariantes.
- Arrastre de B10 ([#19](https://github.com/luisjrez/Tappy/issues/19#issuecomment-7060992239)): la creación pasa por la regla única `issuance_block` (nuevo `held_issuing_receiver`, que comparte `issuable` con `issuing_receiver`) y bloquea la fila del receptor `FOR SHARE`: una deshabilitación concurrente (que actualiza esa fila) espera, o el cobro espera a que termine y respeta el nuevo estado. Sin receptor o deshabilitado → `409` con la explicación de `issuance_block`, sin filas nuevas. El cuerpo es estricto: el cliente no puede enviar receptor, moneda, estado ni referencia.
- Permisos: crear requiere rol operador (`current_operator`, admin → `403`) y pertenencia al comercio (`404` fuera de alcance). Leer usa el mismo alcance que comercios (`scoped_ids`): operadores de ese comercio y administradores (revisión de operaciones); cobros ajenos o inexistentes → `404` sin revelar existencia.
- Tests: el helper `wait_until_blocked_on_a_lock` pasó a `tests/support.py` (estaba duplicado en dos archivos de comercios).

## Trazabilidad UC → AC → TC → test

| UC | AC | TC | Test real | Resultado |
| --- | --- | --- | --- | --- |
| B11-UC01 | B11-AC01 | B11-TC01 | `test_operator_creates_and_reads_sale_with_exact_amount` (30000 exacto como entero JSON, MXN, referencia, concepto, `open`, beneficiario y cuenta enmascarada; el GET devuelve lo mismo; autor guardado); `test_concept_is_optional_and_normalized` (5 casos); `test_each_sale_gets_its_own_reference`; `test_reference_collision_is_retried_with_a_new_reference`; `test_sale_keeps_the_receiver_it_was_created_for`; `test_sale_is_blocked_without_an_enabled_receiver`; `test_sale_waits_for_a_concurrent_receiver_change_and_honours_it`; `test_sale_body_accepts_no_receiver_currency_status_or_reference` (5 casos); `test_only_operators_create_sales` | PASS |
| B11-UC02 | B11-AC02 | B11-TC02 | `test_invalid_amounts_are_rejected_without_rounding` (0, -1, 1.5, 30000.0, "30000", true, null, máximo+1, 2^63; 0 filas y sin `input` reflejado); `test_missing_amount_is_rejected`; `test_amount_range_messages_name_the_limits`; `test_bounds_of_the_configured_maximum` (1 y máximo aceptados, máximo+1 rechazado); `test_maximum_cannot_exceed_the_provider_limit`; `test_long_concept_is_rejected_without_truncation`; `test_database_rejects_non_positive_amounts` | PASS |
| B11-UC03 | B11-AC03 | B11-TC03 | `test_other_operator_cannot_read_create_for_or_change_a_sale` (B: GET 404, PATCH/PUT 405, crear para A 404; importe, comercio y lectura de A intactos); `test_issued_terms_cannot_be_changed_in_the_database` (7 columnas); `test_administrators_can_review_any_sale`; `test_unknown_or_malformed_sale_ids` | PASS |

## TDD

| Comportamiento | Red | Green |
| --- | --- | --- |
| Crear/leer, importes, concepto, permisos, inmutabilidad | 41 de 42 tests fallan (primer fallo registrado: `KeyError: 'id'`, porque `POST /sales` respondía 404; aún no existían ni la ruta ni la tabla `sales`) | Modelo, migración con trigger, `money.py`, servicio, esquemas y rutas |
| Tope configurable sin exceder el del proveedor | El único test que pasaba en Red lo hacía por la razón equivocada (Settings rechazaba un campo desconocido); se reescribió para exigir `less than or equal to 100000000` y falló hasta añadir el campo | `sale_max_amount_cents` con `le=PROVIDER_MAX_AMOUNT_CENTS` |
| Colisión de referencia (review) | `psycopg.errors.UniqueViolation: ... "sales_reference_key"` (500) con `new_reference` forzado a repetir | `insert_with_fresh_reference` sobre la restricción nombrada `uq_sales_reference` |
| Deshabilitación concurrente | Mutación sin `with_for_update(read=True)`: `Failed: the request never waited for a row lock` (el cobro leía la versión confirmada, habilitada). El test abre una transacción que deshabilita primero y espera en `pg_stat_activity` a que la petición quede bloqueada | `held_issuing_receiver` con `FOR SHARE` |

Refactor con suite verde: `issuable` compartido por `issuing_receiver` y `held_issuing_receiver`; `masked_account` compartido por receptor y cobro (review); `scoped_ids` reutiliza el alcance de comercios; helper de espera de locks movido a `tests/support.py`.

## B11-VC01 — Resultado inicial de API

Proceso real `python -m tappy` sobre `6629897`, DB de desarrollo migrada a `0007_sales`; UUIDs y fechas normalizados. Ninguna respuesta de creación implica pago: el cobro nace `open` y no se llama al proveedor.

| Petición | Status | Respuesta |
| --- | --- | --- |
| `POST /sales {A, 30000}` (operador A, sin receptor) | 409 | `{"detail": "No receiving account is configured; new charges are blocked"}` |
| `POST /sales {A, 30000, "Dos tacos al pastor"}` (operador A) | 201 | `{"id": "<uuid>", "merchant_id": "<uuid>", "reference": "1M7309Z3XK", "amount_cents": 30000, "currency": "MXN", "concept": "Dos tacos al pastor", "status": "open", "beneficiary_name": "Tienda Demo A SA de CV", "masked_account": "**************6782", "created_at": "<fecha UTC>"}` |
| `GET /sales/{id}` (operador A) | 200 | `{"id": "<uuid>", "merchant_id": "<uuid>", "reference": "1M7309Z3XK", "amount_cents": 30000, "currency": "MXN", "concept": "Dos tacos al pastor", "status": "open", "beneficiary_name": "Tienda Demo A SA de CV", "masked_account": "**************6782", "created_at": "<fecha UTC>"}` |
| `POST /sales {A, 1500}` sin concepto (operador A) | 201 | `{"id": "<uuid>", "merchant_id": "<uuid>", "reference": "XZXXA7QNVS", "amount_cents": 1500, "currency": "MXN", "concept": null, "status": "open", "beneficiary_name": "Tienda Demo A SA de CV", "masked_account": "**************6782", "created_at": "<fecha UTC>"}` |
| `POST /sales {A, 0}` (operador A) | 422 | `{"detail": "Amount must be a whole number of centavos between 1 and 100000000"}` |
| `POST /sales {A, -1}` (operador A) | 422 | `{"detail": "Amount must be a whole number of centavos between 1 and 100000000"}` |
| `POST /sales {A, 1.5}` (operador A) | 422 | `{"detail": [{"type": "int_type", "loc": ["body", "amount_cents"], "msg": "Input should be a valid integer"}]}` |
| `POST /sales {A, 100000001}` (operador A) | 422 | `{"detail": "Amount must be a whole number of centavos between 1 and 100000000"}` |
| `POST /sales {A, "30000"}` (operador A) | 422 | `{"detail": [{"type": "int_type", "loc": ["body", "amount_cents"], "msg": "Input should be a valid integer"}]}` |
| `POST /sales {A, 30000, concepto de 41}` (operador A) | 422 | `{"detail": "Concept must have at most 40 characters"}` |
| `POST /sales {A, 30000, "provider_account_id": "bank-account-demo-b"}` (operador A) | 422 | `{"detail": [{"type": "extra_forbidden", "loc": ["body", "provider_account_id"], "msg": "Extra inputs are not permitted"}]}` |
| `POST /sales {A, 30000}` (admin) | 403 | `{"detail": "Operator role required"}` |
| `GET /sales/{id}` (operador B) | 404 | `{"detail": "Sale not found"}` |
| `PATCH /sales/{id} {"amount_cents": 1}` (operador B) | 405 | `{"detail": "Method Not Allowed"}` |
| `POST /sales {A, 1}` (operador B) | 404 | `{"detail": "Merchant not found"}` |
| `GET /sales/{id}` (operador A, tras cambiar el receptor) | 200 | `{"id": "<uuid>", "merchant_id": "<uuid>", "reference": "1M7309Z3XK", "amount_cents": 30000, "currency": "MXN", "concept": "Dos tacos al pastor", "status": "open", "beneficiary_name": "Tienda Demo A SA de CV", "masked_account": "**************6782", "created_at": "<fecha UTC>"}` |
| `POST /sales {A, 30000}` (operador A, receptor deshabilitado) | 409 | `{"detail": "The receiving account is disabled; new charges are blocked until it is enabled"}` |
| `GET /sales/{id}` (admin) | 200 | `{"id": "<uuid>", "merchant_id": "<uuid>", "reference": "1M7309Z3XK", "amount_cents": 30000, "currency": "MXN", "concept": "Dos tacos al pastor", "status": "open", "beneficiary_name": "Tienda Demo A SA de CV", "masked_account": "**************6782", "created_at": "<fecha UTC>"}` |

En la base quedaron exactamente 2 cobros (30000 + 1500 centavos): ningún rechazo creó filas. Logs del servidor sin CLABE. Datos de prueba eliminados al terminar (identidades, sesiones, comercios, membresías, receptores y cobros en 0). Estado VC01: **PASS** (resultado inicial).

## Checks

`uv run python -m quality.check` sobre `f676cde` (con `.env` exportado): PASS format, lint, types (mypy strict), hygiene, migrations (upgrade/downgrade/upgrade + `alembic check`), tests (219 passed, Postgres real aislado), api (14 contratos sin diferencias). Mutación comprobada: sin `FOR SHARE` → falla la carrera.

## Supresiones

`tests/sales/test_sales_api.py` → `S608` en el UPDATE parametrizado por columna del test de inmutabilidad (valores fijos del propio test, sin entrada externa).

## Umbral

AC PASS / AC aplicables = 3/3 = **100%**.

## Review Standards/Spec

| Ronda | Revisión | Standards | Spec | Hallazgos |
| --- | --- | --- | --- | --- |
| 1 | `6629897` + `90eae8a` | APPROVE | APPROVE | Sin violaciones duras. Menores: colisión de referencia sin reintento (500 improbable), máscara de cuenta duplicada entre receptor y cobro. Juicios aceptados sin cambio: helpers de excepciones en el router, `money.py` (lo pide el Refactor del ticket), `clean_concept` separado (vacío → `null`), 422 y forma de errores según la convención del repo |
| 2 | `f676cde` | APPROVE | APPROVE | Reintento sobre `uq_sales_reference` con Red/Green y `masked_account` compartido; sin regresiones (70 tests de cobros y comercios en verde) |

Hallazgos pendientes: 0.
