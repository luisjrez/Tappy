# Evidencia — B33 Limitar creación y consultas externas

Ticket: [#41](https://github.com/luisjrez/Tappy/issues/41) · Historia: [H7 #7](https://github.com/luisjrez/Tappy/issues/7) · Protocolo: [TICKET_QUALITY_PROTOCOL](../planning/TICKET_QUALITY_PROTOCOL.md) · Manifiesto: [B33-operation-quotas.toml](B33-operation-quotas.toml)

> Verificado con datos sintéticos y un pey falso local que registra cada petición. **No hubo llamadas a pey real ni pruebas de carga contra el proveedor.** Las cuotas protegen el entorno propio; los límites reales de pey siguen pendientes de confirmar (B35).

## Revisiones y escenario

- **Trazabilidad:** B33-UC01–UC03, B33-AC01–AC03 y B33-VC01. La superficie es la API.
- **Modalidad:** antes/después. Los endpoints ya existían; B33 añade el `429`, el `413` y la cuota de lectura.
- **Cambios esperados en tests anteriores:**
  - `SaleRequest` y `AttemptRequest` llevan ahora la política de cuota.
  - Cinco tests que llaman al servicio directamente pasan `AMPLE_QUOTA`.
  - No cambia ninguna aserción.
- **Base y revisiones:**
  - Base: rama B32 `dfab69b` ([PR #88](https://github.com/luisjrez/Tappy/pull/88)), stack #68.
  - Candidato: `cd109cb`.
- **Entorno:** macOS, Colima + Compose (Postgres 18) y Python 3.14.8. Fecha: 2026-11-25 (UTC). Ejecutor: sesión local de desarrollo del autor del PR.

## Diseño

### Reserva persistente (`tappy.platform.quotas`)

- La tabla `operation_quotas` (migración `0024`) guarda `scope`, `operation`, `window_start` y `used`. Su clave primaria son los tres primeros campos, y un check exige `used > 0`.
- `reserve_quota` es un `INSERT … ON CONFLICT DO UPDATE SET used = used + 1 WHERE used < limit RETURNING used`. Si no devuelve fila, la cuota está llena y se lanza `QuotaExceededError` con los segundos que faltan para que cierre la ventana, redondeados hacia arriba.
- **Concurrencia:** la reserva corre en la misma transacción que la creación.
  - Dos peticiones que compiten por el último lugar se serializan en el bloqueo de la fila.
  - Si la primera confirma, la segunda recibe `429`.
  - Si la primera se revierte, el lugar vuelve a quedar libre y lo toma la segunda.
  - No hay contadores en memoria de proceso.
- **Ventanas:** son fijas, de `TAPPY_QUOTA_WINDOW_SECONDS` (60 por defecto). Las ventanas anteriores de un mismo `scope` y operación se purgan en la siguiente reserva, así que la tabla no crece sin límite.

### Qué cuenta y a quién

| Operación | Ajuste (defecto) | Alcance | Dónde se reserva |
| --- | --- | --- | --- |
| `sale_creation` | `TAPPY_SALE_CREATION_QUOTA` (10) | Comercio | `create_sale`, después de la idempotencia y del receptor emisor y antes de insertar |
| `attempt_creation` | `TAPPY_ATTEMPT_CREATION_QUOTA` (10) | Comercio | `reserve_attempt`, después de las validaciones y antes de crear el intento. Es la única ruta que llama a `create_qr` |
| `sale_read` | `TAPPY_SALE_READ_QUOTA` (120) | Identidad autenticada | Dependencia de `GET /sales`, `GET /sales/{id}` y `GET /sales/{id}/receipt`, en su propia transacción |

Los valores por defecto son los de la propuesta de §11 de la arquitectura: 10 creaciones por minuto por comercio y 120 lecturas por minuto por operador. Son configurables.

- Una repetición con la misma `Idempotency-Key` devuelve el resultado guardado y no consume cuota. Un reintento tras perder la red nunca recibe `429`.
- Una petición rechazada antes de la reserva no consume nada: validación, receptor bloqueado, intento activo o sin sesión (`401`).
- **Respuesta `429`:** cabecera `Retry-After` y cuerpo `{"detail": "Quota exceeded; try again in N seconds", "retry_after_seconds": N}`. Está documentada en OpenAPI con el modelo `QuotaExceededResponse`.

### Límites de cuerpo y página

- Las rutas de la API usan el `max_body_size` nativo de FastAPI 0.165 con `TAPPY_API_MAX_BODY_BYTES` (16384 por defecto): `413` tanto si el tamaño viene declarado como si llega en streaming.
- El cuerpo del `413` lo pone Starlette: texto plano si el tamaño venía declarado y JSON si llegó en streaming. El contrato es el código.
- Los webhooks conservan su propio límite (`TAPPY_WEBHOOK_MAX_BODY_BYTES`).
- Las páginas de `GET /sales` siguen limitadas a 50 filas (B27).

### Lecturas sin llamadas bancarias (AC03)

Las lecturas solo usan el estado propio. En el código, `qr_payments` solo se llama desde `reconcile_attempt`, que usan los comandos `reconcile` y `run-jobs`, y `create_qr` solo desde `request_attempt`. El comportamiento ya era así antes de B33. El test de caracterización y VC01 lo fijan contra regresiones.

## Trazabilidad UC → AC → TC → test

| UC | AC | TC | Test real | Resultado |
| --- | --- | --- | --- | --- |
| B33-UC01 | B33-AC01 | B33-TC01 | `tests/sales/test_quotas.py::test_sales_within_the_quota_are_created_and_the_excess_gets_429_with_wait_guidance` (3 × `201`, `429` con `Retry-After: 50`, con `1` faltando 0.75 s y `201` en la ventana nueva; una sola fila de cuota tras la purga); `…::test_repeated_requests_replay_without_spending_the_quota`; `…::test_each_merchant_has_its_own_quota`; `…::test_qr_requests_over_the_quota_get_429_without_calling_the_provider`; `…::test_each_actor_has_a_read_quota_that_does_not_block_others`; `…::test_unauthenticated_reads_are_refused_before_spending_any_quota`; `…::test_oversized_bodies_are_refused_before_creating_anything` | PASS |
| B33-UC02 | B33-AC02 | B33-TC02 | `…::test_a_creation_waiting_for_the_last_slot_is_refused_once_another_takes_it` (la petición espera el bloqueo de fila; la otra transacción confirma → `429`, siguen 3 ventas); `…::test_a_slot_released_by_a_rolled_back_creation_goes_to_the_waiting_one` (se revierte → `201`); `…::test_simultaneous_qr_requests_never_exceed_the_quota` (3 QR simultáneos con cuota 2 → 2 × `201` + `429`; 2 llamadas al proveedor y 2 intentos) | PASS |
| B33-UC03 | B33-AC03 | B33-TC03 | `…::test_reading_a_pending_attempt_many_times_never_calls_the_provider` (100 lecturas `pending` más el historial: 1 `create_qr` y 0 `qr_payments`) | PASS |

## TDD

**Red:** los tests se escribieron antes del código y se corrieron sobre `dfab69b`, añadiendo solo el módulo `quotas.py`, sin conectarlo, para que el archivo importe.

- Fallan 9 de 11.
- Los 2 que pasan ya eran ciertos antes y se conservan como caracterización:
  - sin sesión, la respuesta es `401`;
  - leer no consulta al proveedor.

```
FAILED tests/sales/test_quotas.py::test_sales_within_the_quota_are_created_and_the_excess_gets_429_with_wait_guidance
FAILED tests/sales/test_quotas.py::test_repeated_requests_replay_without_spending_the_quota
FAILED tests/sales/test_quotas.py::test_each_merchant_has_its_own_quota
FAILED tests/sales/test_quotas.py::test_qr_requests_over_the_quota_get_429_without_calling_the_provider
FAILED tests/sales/test_quotas.py::test_each_actor_has_a_read_quota_that_does_not_block_others
FAILED tests/sales/test_quotas.py::test_oversized_bodies_are_refused_before_creating_anything
FAILED tests/sales/test_quotas.py::test_a_creation_waiting_for_the_last_slot_is_refused_once_another_takes_it
FAILED tests/sales/test_quotas.py::test_a_slot_released_by_a_rolled_back_creation_goes_to_the_waiting_one
FAILED tests/sales/test_quotas.py::test_simultaneous_qr_requests_never_exceed_the_quota
9 failed, 2 passed in 6.01s
```

**Mutaciones** (`tests/sales/test_quotas.py` sobre el candidato; cada una se revierte):

```
M1 sin tope en el upsert: 7 failed, 4 passed in 6.30s
M2 sin purga de ventanas: 1 failed, 10 passed in 6.31s
M3 espera truncada: 6 failed, 5 passed in 6.42s
M4 repeticion consume cuota: 1 failed, 10 passed in 6.55s
M5 sin cuota de QR: 2 failed, 9 passed in 6.46s
M6 lectura sin cuota: 1 failed, 10 passed in 6.31s
```

## Aplicabilidad por superficie

| Superficie | Aplica | Justificación |
| --- | --- | --- |
| API | Sí | `429` en las creaciones y lecturas de ventas, `413` en los cuerpos de la API |
| Panel | No aplica | El back office no crea cobros ni llama al proveedor |
| Comandos | No aplica | `reconcile` y `run-jobs` ya tienen sus propios límites de lote, intentos y espera (B23); no cambian |

## B33-VC01 — API antes/después

- Proceso real `python -m tappy` con `TAPPY_PAYMENT_PROVIDER=pey` y un pey falso local en `127.0.0.1:8899`, que escribe en un log cada `POST /codi/qr` y cada `GET`.
- Cuotas de la prueba: 3 ventas, 2 QR y 10 lecturas, con ventana de 3600 s para que el escenario no cruce de ventana.
- Mismo script en las dos revisiones; el "antes" ignora esas variables.
- Comercios, operadores y llaves son sintéticos. La salida del servidor no contiene la llave de pey ni tokens (`grep` = 0).

### Antes (B32 `dfab69b`)

#### TC01 · creación hasta el límite y exceso
- Venta 1 del comercio A → 201 `{"status": "open", "amount_cents": 30000}`
- Repetición de la venta 1 (misma Idempotency-Key) → 200 `{"status": "open", "amount_cents": 30000}`
- Venta 2 del comercio A → 201 `{"status": "open", "amount_cents": 30000}`
- Venta 3 del comercio A → 201 `{"status": "open", "amount_cents": 30000}`
- Venta 4 del comercio A (excede la cuota de 3) → 201 `{"status": "open", "amount_cents": 30000}`
- Venta 1 del comercio B (cuota propia) → 201 `{"status": "open", "amount_cents": 30000}`
- Ventas guardadas del comercio A: 4
- Llamadas al proveedor hasta aquí: `{}`
#### TC01/TC02 · QR concurrentes con cuota de 2
- QR simultáneo para la venta 1 → 201 `{"status": "pending", "provider_request_id": "QRVC330002"}`
- QR simultáneo para la venta 2 → 201 `{"status": "pending", "provider_request_id": "QRVC330001"}`
- QR simultáneo para la venta 3 → 201 `{"status": "pending", "provider_request_id": "QRVC330003"}`
- Intentos guardados: 3
- Llamadas al proveedor: `{"POST": 3}`
#### TC03 · lecturas de un intento pendiente
- 9 lecturas de GET /sales/{id} → `{"200 pending": 9}`
- Lectura 10 (última de la cuota de lectura de 10) → 200 `{"items": 4, "attempt_count": [0, 1, 1, 1]}`
- Lectura 11 del mismo operador (excede) → 200 `{"status": "open", "amount_cents": 30000}`
- Lectura del administrador (cuota propia) → 200 `{"status": "open", "amount_cents": 30000}`
- Llamadas al proveedor antes de leer `{"POST": 3}` y después `{"POST": 3}`
#### Límite de cuerpo
- POST /sales con cuerpo de 20 KB → 422 `{"detail": "Concept must have at most 40 characters"}`

### Después (candidato `cd109cb`)

#### TC01 · creación hasta el límite y exceso
- Venta 1 del comercio A → 201 `{"status": "open", "amount_cents": 30000}`
- Repetición de la venta 1 (misma Idempotency-Key) → 200 `{"status": "open", "amount_cents": 30000}`
- Venta 2 del comercio A → 201 `{"status": "open", "amount_cents": 30000}`
- Venta 3 del comercio A → 201 `{"status": "open", "amount_cents": 30000}`
- Venta 4 del comercio A (excede la cuota de 3) → 429 Retry-After: 3447 `{"detail": "Quota exceeded; try again in 3447 seconds", "retry_after_seconds": 3447}`
- Venta 1 del comercio B (cuota propia) → 201 `{"status": "open", "amount_cents": 30000}`
- Ventas guardadas del comercio A: 3
- Llamadas al proveedor hasta aquí: `{}`
#### TC01/TC02 · QR concurrentes con cuota de 2
- QR simultáneo para la venta 1 → 201 `{"status": "pending", "provider_request_id": "QRVC330001"}`
- QR simultáneo para la venta 2 → 201 `{"status": "pending", "provider_request_id": "QRVC330002"}`
- QR simultáneo para la venta 3 → 429 Retry-After: 3447 `{"detail": "Quota exceeded; try again in 3447 seconds", "retry_after_seconds": 3447}`
- Intentos guardados: 2
- Llamadas al proveedor: `{"POST": 2}`
- Filas de cuota: `[["attempt_creation", "2"], ["sale_creation", "3"], ["sale_creation", "1"]]`
#### TC03 · lecturas de un intento pendiente
- 9 lecturas de GET /sales/{id} → `{"200 pending": 9}`
- Lectura 10 (última de la cuota de lectura de 10) → 200 `{"items": 3, "attempt_count": [0, 1, 1]}`
- Lectura 11 del mismo operador (excede) → 429 Retry-After: 3447 `{"detail": "Quota exceeded; try again in 3447 seconds", "retry_after_seconds": 3447}`
- Lectura del administrador (cuota propia) → 200 `{"status": "open", "amount_cents": 30000}`
- Llamadas al proveedor antes de leer `{"POST": 2}` y después `{"POST": 2}`
#### Límite de cuerpo
- POST /sales con cuerpo de 20 KB → 413 `"Content Too Large"`


Log del pey falso después: `{"method": "POST", "path": "/codi/qr"}` ×2, ningún `GET`.

**Validación:**

- **TC01:**
  - dentro de la cuota se crea (`201`) y la repetición idempotente no consume (`200`);
  - el exceso da `429` con `Retry-After` y `retry_after_seconds`;
  - el comercio B tiene su propia cuota;
  - antes, la cuarta venta se creaba.
- **TC02:** de 3 QR simultáneos con cuota 2 salen 2 `201` y un `429`, con 2 llamadas al proveedor y 2 intentos. Antes salían 3 QR, con 3 llamadas.
- **TC03:**
  - 9 lecturas del intento `pending` más el historial no añaden ninguna llamada al proveedor (`POST` sigue en 2 y no hay `GET`);
  - la lectura 11 del operador da `429` y el administrador conserva su cuota;
  - antes no había límite de lectura.
- **Cuerpo:** 20 KB dan `413` sin procesarse. Antes se procesaba el cuerpo completo y respondía `422`.

Los datos se eliminaron al terminar. Estado VC01: **PASS**.

## Checks

`uv run python -m quality.check` sobre `cd109cb`, con `.env` exportado: PASS en todos los pasos.

- format, lint, types (mypy strict) y hygiene;
- migrations: upgrade/downgrade/upgrade de `0024` + `alembic check`;
- tests: 574 passed, Postgres real aislado;
- api: 15 contratos sin diferencias;
- evidence: B01–B32 APPROVED.

## Supresiones

Sin supresiones nuevas.

## Umbral

AC PASS / AC aplicables = 3/3 = **100%**.

## Review Standards/Spec

| Ronda | Revisión | Standards | Spec | Hallazgos |
| --- | --- | --- | --- | --- |
| 1 | `cd109cb` | PENDING | PENDING | — |
