# Evidencia — B12 Repetir creación sin duplicar venta

Ticket: [#20](https://github.com/luisjrez/Tappy/issues/20) · Historia: [H4 #4](https://github.com/luisjrez/Tappy/issues/4) · Protocolo: [TICKET_QUALITY_PROTOCOL](../planning/TICKET_QUALITY_PROTOCOL.md) · Manifiesto: [B12-idempotent-sale.toml](B12-idempotent-sale.toml)

## Revisiones y escenario

- Ticket, UC/AC/TC y comprobación: B12-UC01–UC03, B12-AC01–AC03, B12-TC01–TC03, B12-VC01.
- Modalidad: **antes/después** para `POST /sales` (contrato existente de B11: ahora exige `Idempotency-Key` y responde `200`/`409` en repeticiones) y **resultado inicial** para la repetición idempotente. Contratos aprobados sin diferencias (los 401 sin sesión no cambian).
- Base: rama B11 `f676cde` (PR #66), stack de H4. Revisiones: candidato `c4d292c` → correcciones de review `97333cf` (revisión final). La VC01 se ejecutó sobre `c4d292c`; `97333cf` no cambia ninguna de sus respuestas (solo añade la comprobación de pertenencia en la repetición, normaliza el digest y declara el esquema del `200`).
- Entorno: macOS, Colima + Compose (Postgres 18), Python 3.14.8. Fecha: 2026-11-24. Ejecutor: sesión local de desarrollo del autor del PR.
- Datos: comercio «Tienda Demo A», identidades sintéticas `@tappy.example`, receptor ficticio. Sin integración bancaria: crear un cobro no llama al proveedor.

## Diseño

- `tappy.sales.idempotency`: tabla `idempotency_requests` (migración `0008_idempotency_requests`) con `identity_id`, `operation` (`IdempotentOperation`, hoy `create_sale`; B13 añadirá la creación de intentos), `key`, `request_digest` (SHA-256 del contenido canónico), `resource_id` y restricción `uq_idempotency_requests_key (identity_id, operation, key)`.
- Resolución de conflictos sin memoria del proceso: `claim_or_replay` hace `INSERT … ON CONFLICT DO NOTHING RETURNING`. Si reserva, el cobro se crea con el `resource_id` reservado en la misma transacción; si la clave existe, compara el digest: igual → devuelve el cobro original (`200`), distinto → `IdempotencyConflictError` (`409`, sin tocar el original). Una petición concurrente con la misma clave espera en el índice único a que la primera confirme o revierta, y luego decide con el valor confirmado.
- El digest cubre el contenido **normalizado** que se guardaría (`merchant_id`, `amount_cents`, concepto con espacios colapsados): otro importe, otro concepto u otro comercio con la misma clave es conflicto; el mismo concepto con otros espacios es la misma petición.
- La pertenencia al comercio se comprueba **antes** de reservar o repetir: quien ya no pertenece al comercio recibe `404` aunque repita su clave (no se revela el cobro).
- Diferencia con `docs/02-arquitectura.md` §6 (orientativo): las claves se acotan por identidad (no por comercio) para que un operador nunca reciba el resultado de otro, y no se guarda `outcome` porque solo se registran creaciones exitosas (un fallo revierte la reserva).
- Las claves pertenecen a la identidad que las usó: otro operador con la misma clave crea su propio cobro.
- Un intento fallido (validación, receptor bloqueado, comercio ajeno) revierte la transacción y no consume la clave. Una repetición devuelve el cobro aunque después se haya deshabilitado el receptor: la obligación ya existe.
- `Idempotency-Key` es obligatorio: `^[A-Za-z0-9_-]{8,128}$` (un UUID sirve). `SaleRequest` agrupa operador, contenido y clave; una dependencia del router lo construye.
- Tests: los helpers de cobros pasaron a `tests/sales/support.py` + `conftest.py` para compartirlos con los nuevos tests; `create_sale` envía una clave nueva en cada llamada.

## Trazabilidad UC → AC → TC → test

| UC | AC | TC | Test real | Resultado |
| --- | --- | --- | --- | --- |
| B12-UC01 | B12-AC01 | B12-TC01 | `test_repeating_a_creation_returns_the_same_sale` (201 y luego 200 con el mismo cuerpo, 1 cobro y 1 clave); `test_repetition_returns_the_sale_even_after_the_receiver_is_disabled`; `test_keys_belong_to_the_identity_that_used_them`; `test_failed_creation_does_not_consume_the_key`; `test_creation_requires_a_well_formed_key` (5 casos, sin filas); `test_repetition_after_losing_the_membership_reveals_nothing`; `test_whitespace_only_differences_in_the_concept_are_the_same_request` | PASS |
| B12-UC02 | B12-AC02 | B12-TC02 | `test_reusing_a_key_with_other_content_conflicts_without_touching_the_sale` (45000 y otro concepto → 409; original intacto); `test_reusing_a_key_for_another_merchant_conflicts` | PASS |
| B12-UC03 | B12-AC03 | B12-TC03 | `test_concurrent_repetition_waits_and_returns_the_single_sale` (una transacción reserva K y crea el cobro sin confirmar; la petición HTTP con K queda bloqueada —comprobado en `pg_stat_activity`— y tras el commit devuelve 200 con el mismo id; 1 cobro); `test_concurrent_reuse_with_other_content_conflicts` | PASS |

«Crear y después listar cobros» (TC03): todavía no existe listado (historial paginado = B27). Se verifica con lo que existe en la frontera de B12: número de cobros en la base, lectura por id y, en la VC01, 8 peticiones paralelas reales que devuelven el mismo cobro.

## TDD

| Comportamiento | Red | Green |
| --- | --- | --- |
| Repetición, conflicto, clave obligatoria y carrera | 12 de 14 tests fallan antes de implementar (aún no existían la cabecera obligatoria, la tabla de claves ni la repetición) | `idempotency_requests`, `claim_or_replay`, cabecera obligatoria |
| Claves por identidad / fallo no consume la clave | Pasaban antes de implementar (no había claves): son guardas de regresión | Mutación con clave sin `identity_id` → `assert 200 == 201` en `test_keys_belong_to_the_identity_that_used_them` |
| Repetición sin pertenencia / digest normalizado (review) | `assert 200 == 404` (la repetición devolvía el cobro tras perder la membresía) y `assert 409 == 200` (otros espacios en el concepto) | `accessible_merchant` antes de `claim_or_replay`; digest sobre el contenido normalizado |
| Carrera sin esperar al índice | Mutación sin `ON CONFLICT DO NOTHING` (insertar y fallar): `UniqueViolation uq_idempotency_requests_key` (500) en los dos tests concurrentes | `INSERT … ON CONFLICT DO NOTHING RETURNING` + relectura |

Refactor con suite verde: `SaleRequest` agrupa operador, contenido y clave (evita la lista larga de argumentos en servicio y router); helpers de tests compartidos; tras la review, idempotencia movida a `tappy.sales` (sus operaciones son de cobros y `platform` no depende de identidades) y `held_issuing_receiver` recibe el comercio ya autorizado.

## B12-VC01 — Antes/después de la creación

**Antes** (última evidencia aprobada, [B11-VC01](B11-sale.md#b11-vc01--resultado-inicial-de-api), revisión `6629897`): `POST /sales {A, 30000, …}` sin cabecera → `201`. Repetirla creaba otra venta con otra referencia (en B11 la creación no era idempotente; `test_each_sale_gets_its_own_reference`).

**Después** (proceso real `python -m tappy` sobre `c4d292c`, DB en `0008_idempotency_requests`; ids y fechas normalizados):

| Petición | Status | Respuesta |
| --- | --- | --- |
| `POST /sales {A, 30000}` sin `Idempotency-Key` | 422 | `{"detail": [{"type": "missing", "loc": ["header", "idempotency-key"], "msg": "Field required"}]}` |
| `POST /sales {A, 30000}` con `Idempotency-Key: short` | 422 | `{"detail": [{"type": "string_pattern_mismatch", "loc": ["header", "idempotency-key"], "msg": "String should match pattern '^[A-Za-z0-9_-]{8,128}$'"}]}` |
| `POST /sales {A, 30000}` con K (primera vez) | 201 | `{"id": "<sale-1>", "merchant_id": "<uuid>", "reference": "NJ5ND61YY5", "amount_cents": 30000, "currency": "MXN", "concept": null, "status": "open", "beneficiary_name": "Tienda Demo A SA de CV", "masked_account": "**************6782", "created_at": "<fecha UTC>"}` |
| `POST /sales {A, 30000}` con K (repetición) | 200 | `{"id": "<sale-1>", "merchant_id": "<uuid>", "reference": "NJ5ND61YY5", "amount_cents": 30000, "currency": "MXN", "concept": null, "status": "open", "beneficiary_name": "Tienda Demo A SA de CV", "masked_account": "**************6782", "created_at": "<fecha UTC>"}` |
| `POST /sales {A, 45000}` con K | 409 | `{"detail": "Idempotency key already used with different content"}` |
| 8 × `POST /sales {A, 1500}` con K2 en paralelo | [200, 200, 200, 200, 200, 200, 200, 201] | 1 cobro distinto en las 8 respuestas |
| `GET /sales/{id}` del cobro de K | 200 | `{"id": "<sale-1>", "merchant_id": "<uuid>", "reference": "NJ5ND61YY5", "amount_cents": 30000, "currency": "MXN", "concept": null, "status": "open", "beneficiary_name": "Tienda Demo A SA de CV", "masked_account": "**************6782", "created_at": "<fecha UTC>"}` |

En la base quedaron 2 cobros (30000 y 1500) y 2 claves. Logs sin CLABE. Datos de prueba eliminados al terminar. Diferencias esperadas frente a B11: sin clave → `422` (`loc: header.idempotency-key`); repetir → `200` con el mismo cobro; mismo K con otro contenido → `409`. Estado VC01: **PASS**.

### Contrato OpenAPI de `POST /sales` (`f676cde` → `97333cf`)

```diff
--- openapi_sales_before.json	2026-11-24 11:42:58
+++ openapi_sales_after.json	2026-11-24 11:43:08
@@ -1,5 +1,17 @@
 {
   "operationId": "create_sales_post",
+  "parameters": [
+    {
+      "in": "header",
+      "name": "idempotency-key",
+      "required": true,
+      "schema": {
+        "pattern": "^[A-Za-z0-9_-]{8,128}$",
+        "title": "Idempotency-Key",
+        "type": "string"
+      }
+    }
+  ],
   "requestBody": {
     "content": {
       "application/json": {
@@ -11,6 +23,16 @@
     "required": true
   },
   "responses": {
+    "200": {
+      "content": {
+        "application/json": {
+          "schema": {
+            "$ref": "#/components/schemas/SaleResponse"
+          }
+        }
+      },
+      "description": "Repeated request: the sale created with this key"
+    },
     "201": {
       "content": {
         "application/json": {
@@ -25,7 +47,7 @@
       "description": "Merchant not found or not accessible"
     },
     "409": {
-      "description": "New charges are blocked"
+      "description": "New charges are blocked or the key was used with other content"
     },
     "422": {
       "content": {
```

Clasificación: **cambio incompatible** para clientes de `POST /sales` (cabecera nueva obligatoria). Impacto: todavía no hay clientes que consuman la API (la app móvil y su contrato común llegan en B40), y B11 aún no está en `main`; ambos PRs se revisan juntos en el stack de H4. Los clientes deben generar la clave al confirmar el cobro y reenviarla en cada reintento.

## Checks

`uv run python -m quality.check` sobre `97333cf` (con `.env` exportado): PASS format, lint, types (mypy strict), hygiene, migrations (upgrade/downgrade/upgrade + `alembic check`), tests (235 passed, Postgres real aislado), api (14 contratos sin diferencias: cubren respuestas sin sesión; el cambio autenticado está en el diff OpenAPI de arriba). Mutaciones comprobadas: sin `ON CONFLICT` → fallan las carreras; clave sin `identity_id` → falla el aislamiento por identidad.

## Supresiones

Sin supresiones nuevas.

## Umbral

AC PASS / AC aplicables = 3/3 = **100%**.

## Review Standards/Spec

Pendiente.
