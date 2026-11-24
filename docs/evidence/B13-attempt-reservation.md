# Evidencia — B13 Reservar un único intento activo

Ticket: [#21](https://github.com/luisjrez/Tappy/issues/21) · Historia: [H4 #4](https://github.com/luisjrez/Tappy/issues/4) · Protocolo: [TICKET_QUALITY_PROTOCOL](../planning/TICKET_QUALITY_PROTOCOL.md) · Manifiesto: [B13-attempt-reservation.toml](B13-attempt-reservation.toml)

## Revisiones y escenario

- Ticket, UC/AC/TC y comprobación: B13-UC01–UC03, B13-AC01–AC03, B13-TC01–TC03, B13-VC01.
- Modalidad: **resultado inicial** para la reserva de intentos (ruta nueva) y **antes/después** para la respuesta de cobro, que gana el campo `attempts` (cambio aditivo; ver «Contrato»). Contratos aprobados sin diferencias; nuevo `attempt-reserve-unauthenticated` (401) aprobado en `b875cb0`. Cambios esperados en tests existentes: el cuerpo exacto de `test_operator_creates_and_reads_sale_with_exact_amount` incluye `"attempts": []` y la lista fija de rutas POST públicas incluye `/sales/{sale_id}/attempts`.
- Base: rama B12 `28e7058` (PR #67), stack de H4 #68. Revisiones: candidato `b875cb0` → correcciones de review `c8cf0cf` (revisión final). La VC01 se ejecutó sobre `b875cb0`; `c8cf0cf` no cambia ninguna de sus respuestas (relee el estado del cobro bajo el bloqueo, simplifica una consulta y corrige el downgrade).
- Entorno: macOS, Colima + Compose (Postgres 18), Python 3.14.8. Fecha: 2026-11-24. Ejecutor: sesión local de desarrollo del autor del PR.
- Datos: comercio «Tienda Demo A», identidades sintéticas, receptor ficticio. **Simulación sin llamadas externas**: reservar un intento no contacta al proveedor ni pide dinero; la creación del QR llega en B14 (simulado) y B15 (pey).

## Diseño

- `PaymentAttempt` (migración `0009_payment_attempts`): `sale_id`, `created_by`, `method` (`qr`/`phone`/`link`), `status` con los estados de `docs/02-arquitectura.md` §7 (`creating`, `pending`, `reconciling`, `expired`, `paid`, `failed`), `created_at`/`updated_at` y `version` (control optimista de SQLAlchemy para las transiciones de B14+).
- Límite en Postgres: índice único parcial `uq_payment_attempts_active_sale` sobre `sale_id` cuando el estado es `creating`, `pending` o `reconciling`. Un intento `expired` o `failed` permite reservar otro (reintento controlado, B25).
- `POST /sales/{id}/attempts {"method"}` con `Idempotency-Key` (operación `create_attempt`; la migración amplía el check `idempotent_operation`). Orden de la reserva: cobro accesible (`404` si no) → clave idempotente (repetición → `200` con el mismo intento; otro método con la misma clave → `409`) → **bloqueo corto** de la fila del cobro (`FOR NO KEY UPDATE` con `populate_existing`, para decidir con el estado confirmado y no con la copia cargada antes del bloqueo) → cobro `open` (`409` si no) → receptor habilitado con la regla única de B10 (`409` con su explicación) → sin intento activo (`409`) → inserción `creating` y commit. Solo operadores (`403` admin).
- Refactor pedido («reducir duración de bloqueos y separar reserva de red externa»): la reserva es una transacción corta sin red; el bloqueo dura solo la comprobación e inserción. El proveedor se invocará después del commit (B14/B15), por lo que una interrupción deja el intento `creating` recuperable.
- El downgrade de `0009` borra primero las claves `create_attempt` para poder restaurar el check anterior sin fallar.
- Lectura: `GET /sales/{id}` (y la respuesta de creación) incluyen `attempts` ordenados por creación. `accessible_sale` comparte el alcance de lectura.
- Tests: `tests/sales/support.py` gana `app_client` (reiniciar la app sin recrear identidades) y `actor_of` (usado también por la carrera de B12).

## Trazabilidad UC → AC → TC → test

| UC | AC | TC | Test real | Resultado |
| --- | --- | --- | --- | --- |
| B13-UC01 | B13-AC01 | B13-TC01 | `test_reserving_an_attempt_leaves_it_creating_on_the_sale` (201 `creating`; el cobro sigue `open` y lista el intento); `test_repeating_a_reservation_returns_the_same_attempt`; `test_reservation_requires_an_open_sale_and_an_enabled_receiver`; `test_reservation_is_limited_to_operators_of_the_sale`; `test_malformed_reservations_are_rejected` (5 casos) | PASS |
| B13-UC02 | B13-AC02 | B13-TC02 | `test_second_attempt_with_another_key_or_channel_conflicts` (qr/phone/link → 409, sigue un solo intento); `test_pending_and_reconciling_attempts_stay_active`; `test_finished_attempts_allow_a_new_reservation`; `test_database_allows_only_one_active_attempt_per_sale` (el índice rechaza un segundo activo insertado directamente) | PASS |
| B13-UC03 | B13-AC03 | B13-TC03 | `test_concurrent_reservations_leave_a_single_active_attempt` (una transacción reserva sin confirmar; la petición HTTP con otra clave y canal queda bloqueada —`pg_stat_activity`— y tras el commit recibe 409; el cobro lista solo el intento retenido); `test_interrupted_reservation_stays_recoverable_after_a_restart` (nueva instancia de la app y mismo token persistido: reintentar con la **misma clave** devuelve 200 con el mismo intento, que sigue `creating`); `test_reservation_interrupted_before_commit_leaves_no_trace` (una reserva revertida antes del commit no deja intento ni consume la clave: la misma clave reserva después con 201); `test_reservation_waits_for_a_concurrent_status_change_and_honours_it` (el cobro pasa a `paid` en una transacción que la reserva espera; tras el commit, 409 «The sale is not open» y ningún intento) | PASS |

## TDD

| Comportamiento | Red | Green |
| --- | --- | --- |
| Primera ejecución de los tests | Colección fallida: `ModuleNotFoundError: tappy.sales.attempts`. La review señaló que no es un Red de comportamiento (protocolo: un error de instalación no prueba la falta del comportamiento), así que cada TC tiene abajo su Red de comportamiento | Modelo + índice parcial, `reserve_attempt`, ruta, migración `0009` |
| TC01 reserva y consulta | Con la reserva deshabilitada (la ruta responde «Sale not found»): `assert <HTTPStatus.NOT_FOUND: 404> == <HTTPStatus.CREATED: 201>` | `reserve_attempt` |
| TC02 segundo intento | Sin `ensure_no_active_attempt`: `IntegrityError ... UniqueViolation uq_payment_attempts_active_sale` (500 en vez de 409) | Comprobación de intento activo bajo el bloqueo |
| TC03 cambio de estado concurrente (review) | `assert 201 == <HTTPStatus.CONFLICT: 409>`: el estado se leía de la copia cargada antes del bloqueo y se reservaba sobre un cobro ya `paid` | `populate_existing=True` en la lectura bloqueada |
| Respuesta de cobro con intentos | El test de B11 de cuerpo exacto falló al añadir `attempts` (cambio aditivo esperado) | Aserción actualizada con `"attempts": []` |
| Carrera sin bloqueo del cobro | Mutación sin `with_for_update(key_share=True)`: `UniqueViolation uq_payment_attempts_active_sale` (500): la segunda petición no veía el intento sin confirmar y chocaba con el índice | Bloqueo corto de la fila del cobro antes de comprobar e insertar |

## B13-VC01 — Resultado inicial de API e interrupción

Proceso real `python -m tappy` sobre `b875cb0`, DB de desarrollo en `0009_payment_attempts`; ids, referencias y fechas normalizados. La interrupción se ejecutó con `kill -9` sobre el PID que escuchaba en `:8000` (47838) **después** de confirmarse la reserva (lo que demuestra que una caída posterior, como la que podría ocurrir durante la futura llamada al proveedor, conserva el intento), comprobando que `/health` dejó de responder, y reinicio en un proceso nuevo (47920); el token del operador sigue siendo válido porque las sesiones viven en Postgres. La interrupción antes del commit está cubierta por `test_reservation_interrupted_before_commit_leaves_no_trace`.

| Petición | Status | Respuesta |
| --- | --- | --- |
| `POST /sales {A, 30000}` | 201 | `{"id": "<id-1>", "merchant_id": "<id-2>", "reference": "<ref>", "amount_cents": 30000, "currency": "MXN", "concept": null, "status": "open", "beneficiary_name": "Tienda Demo A SA de CV", "masked_account": "**************6782", "created_at": "<fecha UTC>", "attempts": []}` |
| `POST /sales/{id}/attempts {qr}` con K | 201 | `{"id": "<id-3>", "sale_id": "<id-1>", "method": "qr", "status": "creating", "created_at": "<fecha UTC>"}` |
| `POST /sales/{id}/attempts {qr}` con K (repetición) | 200 | `{"id": "<id-3>", "sale_id": "<id-1>", "method": "qr", "status": "creating", "created_at": "<fecha UTC>"}` |
| `POST /sales/{id}/attempts {phone}` con otra clave | 409 | `{"detail": "The sale already has an active payment attempt"}` |
| 9 × `POST /sales/{otro}/attempts` en paralelo (qr/phone/link, claves distintas) | [201, 409, 409, 409, 409, 409, 409, 409, 409] | 1 intento reservado |
| Servidor (PID que escuchaba en :8000) terminado con `kill -9`; `/health` sin respuesta | — | — |
| `GET /sales/{id}` tras `kill -9` y reinicio | 200 | `{"id": "<id-1>", "merchant_id": "<id-2>", "reference": "<ref>", "amount_cents": 30000, "currency": "MXN", "concept": null, "status": "open", "beneficiary_name": "Tienda Demo A SA de CV", "masked_account": "**************6782", "created_at": "<fecha UTC>", "attempts": [{"id": "<id-3>", "sale_id": "<id-1>", "method": "qr", "status": "creating", "created_at": "<fecha UTC>"}]}` |

En la base quedaron 2 intentos, ambos `creating` (uno por cobro): ninguno de los 9 intentos concurrentes duplicó la reserva. Datos de prueba eliminados al terminar. Estado VC01: **PASS** (resultado inicial; ningún intento implica pago).

### Contrato: `SaleResponse` gana `attempts` (`28e7058` → `b875cb0`)

```diff
--- sale_schema_before.json	2026-11-24 11:58:51
+++ sale_schema_after.json	2026-11-24 11:58:52
@@ -4,6 +4,13 @@
       "title": "Amount Cents",
       "type": "integer"
     },
+    "attempts": {
+      "items": {
+        "$ref": "#/components/schemas/AttemptResponse"
+      },
+      "title": "Attempts",
+      "type": "array"
+    },
     "beneficiary_name": {
       "title": "Beneficiary Name",
       "type": "string"
@@ -58,7 +65,8 @@
     "status",
     "beneficiary_name",
     "masked_account",
-    "created_at"
+    "created_at",
+    "attempts"
   ],
   "title": "SaleResponse",
   "type": "object"
```

Clasificación: **cambio aditivo** (campo nuevo en respuestas de `POST /sales` y `GET /sales/{id}`); los clientes que ignoran campos desconocidos no se ven afectados y aún no hay consumidores (B40).

## Checks

`uv run python -m quality.check` sobre `c8cf0cf` (con `.env` exportado): PASS format, lint, types (mypy strict), hygiene, migrations (upgrade/downgrade/upgrade + `alembic check`), tests (256 passed, Postgres real aislado), api (15 contratos sin diferencias). Una ejecución intermedia tuvo un error de infraestructura ajeno a B13 (`test_readiness_turns_unavailable_when_local_postgres_stops`, de B02: `docker compose up --wait` de su Postgres temporal devolvió 1); la repetición inmediata pasó completa y se limpió el contenedor sobrante. Mutaciones comprobadas: sin bloqueo del cobro → falla la carrera; sin comprobación de intento activo → falla TC02.

## Supresiones

Sin supresiones nuevas.

## Umbral

AC PASS / AC aplicables = 3/3 = **100%**.

## Review Standards/Spec

Pendiente.
