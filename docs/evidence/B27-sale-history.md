# Evidencia — B27 Consultar historial paginado

Ticket: [#35](https://github.com/luisjrez/Tappy/issues/35) · Historia: [H6 #6](https://github.com/luisjrez/Tappy/issues/6) · Protocolo: [TICKET_QUALITY_PROTOCOL](../planning/TICKET_QUALITY_PROTOCOL.md) · Manifiesto: [B27-sale-history.toml](B27-sale-history.toml)

> Verificado con datos sintéticos y un pey falso local. **No hubo pagos reales.** El historial solo lee: no cambia estados ni expone ventas de comercios ajenos.

## Revisiones y escenario

- **Trazabilidad:** B27-UC01–UC03, B27-AC01–AC03, B27-TC01–TC03 y B27-VC01, más el arrastre obligatorio de B10 (#18, TC03).
- **Modalidad: resultado inicial.**
  - El endpoint `GET /sales` es nuevo y su contrato está abajo.
  - El detalle `GET /sales/{id}` no cambia de contrato. Solo se refactorizó su lectura autorizada (`scoped_sales`).
- **Base y revisiones:**
  - Base: rama B26 `0490ed2` ([PR #82](https://github.com/luisjrez/Tappy/pull/82)), stack #68.
  - Candidato: `675e62f`.
  - Correcciones de la review: `27d4eb2`, revisión final del código. La VC01 se repitió sobre ella. `9678241` solo renombra un test (nit de la ronda 2) y `80c9d7c` lo formatea, sin cambio de comportamiento.
- **Entorno:** macOS, Colima + Compose (Postgres 18), Python 3.14.8. Fecha: 2026-11-25 (UTC). Ejecutor: sesión local de desarrollo del autor del PR.

## Diseño

- **`GET /sales`.** El alcance autorizado es el mismo que el del detalle (`scoped_sales`, sobre `merchants.service.scoped_ids`): operadores ven sus comercios y administradores ven todos. Un `merchant_id` ajeno responde `404 Merchant not found`.
- **Una fila por venta.** Se consulta la tabla `sales`. El importe confirmado (suma de transferencias), `covered` (algún intento `paid`) y `attempt_count` salen de subconsultas correlacionadas en una sola sentencia, sin uniones que dupliquen filas ni N+1.
  - Cada fila lleva la instantánea del receptor (beneficiario y cuenta enmascarada).
- **Orden y paginación.**
  - Orden: `created_at DESC, id DESC`.
  - Paginación keyset por `(created_at, id)` con un cursor opaco (`next_cursor`).
  - Las ventas creadas entre páginas no desplazan ni repiten las siguientes. Los empates de `created_at` se desempatan por id.
  - El cursor solo fija una posición y el alcance se aplica siempre, así que manipularlo no expone otro negocio.
- **Filtros.**
  - `status`: `open` = pendiente, `paid`, `review`. Una venta en `review` puede estar ya `covered`.
  - `created_from` / `created_to`: marcas con zona horaria; `from` incluye y `to` excluye. Las fechas locales son B30.
  - `limit`: 1–50, el máximo de página de la arquitectura (§10); por defecto 20.
  - Filtro o límite inválido, cursor inválido, rango invertido, fecha sin zona o parámetro desconocido → `422`.
- **Pendiente para más adelante:** no hay índice `(created_at, id)`. Con volumen, cada página ordena el conjunto visible. Se registra para cuando se mida.

## Trazabilidad UC → AC → TC → test

Todos los tests están en `tests/sales/test_sale_history.py`.

| UC | AC | TC | Test real | Resultado |
| --- | --- | --- | --- | --- |
| B27-UC01 | B27-AC01 | B27-TC01 | `test_consecutive_pages_are_stable_without_repeats_or_gaps` (5 ventas, empate de `created_at` en el límite de página, páginas 2/2/1, sin repeticiones ni huecos, la página 2 no cambia al insertar una venta nueva); `test_rows_carry_the_sale_summary_without_attempt_duplication` | PASS |
| B27-UC02 | B27-AC02 | B27-TC02 | `test_invalid_history_requests_are_rejected` (estado inválido, límites 0 y 51, parámetro desconocido, cursor manipulado, fecha sin zona, rango invertido, `merchant_id` mal formado); `test_fifty_is_the_largest_accepted_limit`; `test_history_never_exposes_another_merchant` (filtro ajeno `404`, cursor de administrador reutilizado por un operador, administrador ve todo, sin sesión `401`); `test_history_filters_by_creation_time_and_merchant` | PASS |
| B27-UC03 | B27-AC03 | B27-TC03 | `test_status_filters_keep_pending_apart_from_confirmed_one_row_per_sale` (venta con dos intentos + pendiente adicional + confirmada; páginas de 1 con `open`; `paid` aparte; `attempt_count` 1/1/2) | PASS |
| Arrastre B10 | — | B10-TC03 | `test_history_keeps_confirmed_sales_after_the_receiver_is_disabled` (receptor deshabilitado: el historial muestra la venta pagada con su instantánea y una venta nueva da `409`) | PASS |

## TDD

**Red:** los tests se escribieron antes del código. Fallan los 13 porque la ruta no existía (`405` / `KeyError`).

```
FAILED tests/sales/test_sale_history.py::test_consecutive_pages_are_stable_without_repeats_or_gaps
FAILED tests/sales/test_sale_history.py::test_rows_carry_the_sale_summary_without_attempt_duplication
FAILED tests/sales/test_sale_history.py::test_invalid_history_requests_are_rejected[params0]
FAILED tests/sales/test_sale_history.py::test_invalid_history_requests_are_rejected[params1]
FAILED tests/sales/test_sale_history.py::test_invalid_history_requests_are_rejected[params2]
FAILED tests/sales/test_sale_history.py::test_invalid_history_requests_are_rejected[params3]
FAILED tests/sales/test_sale_history.py::test_invalid_history_requests_are_rejected[params4]
FAILED tests/sales/test_sale_history.py::test_invalid_history_requests_are_rejected[params5]
FAILED tests/sales/test_sale_history.py::test_invalid_history_requests_are_rejected[params6]
FAILED tests/sales/test_sale_history.py::test_history_never_exposes_another_merchant
FAILED tests/sales/test_sale_history.py::test_status_filters_keep_pending_apart_from_confirmed_one_row_per_sale
FAILED tests/sales/test_sale_history.py::test_history_filters_by_creation_time_and_merchant
FAILED tests/sales/test_sale_history.py::test_history_keeps_confirmed_sales_after_the_receiver_is_disabled
13 failed in 5.90s
```

| Comportamiento | Red | Green |
| --- | --- | --- |
| Historial, filtros y alcance | Ver arriba | `tappy.sales.history`, `HistoryParams`, `GET /sales`, `scoped_sales` |
| Máximo de 50 (review) | `test_invalid_history_requests_are_rejected[params2]` (`limit=51`) falla con `le=100` | `le=50` |
| Mutaciones | Cursor solo por `created_at`: falla TC01 (después de poner el empate en el límite de página, porque con el empate dentro de una página la mutación sobrevivía). Sin alcance: falla `never_exposes…`. Orden sin desempate por id: falla TC01 | — |

## Aplicabilidad por superficie

| Superficie | Aplica | Justificación |
| --- | --- | --- |
| API | Sí | `GET /sales` nuevo |
| Panel | No aplica | Las tablas del back office son B31 y reutilizarán `scoped_sales` |
| Comandos | No aplica | Sin comandos nuevos |

## B27-VC01 — Resultado inicial del historial

Proceso real `python -m tappy` con `TAPPY_PAYMENT_PROVIDER=pey` y un pey falso local.

- Comercio A con 5 ventas:
  - una con dos intentos (expirado y reintento);
  - una pendiente adicional;
  - una pagada por un webhook firmado;
  - dos sin intento.
- Comercio B con una venta.

Revisión `27d4eb2`. Valores sintéticos.

- Venta 1: primer intento → 201 `{"status": "pending", "provider_request_id": "QRVC27A001", "previous_attempt_id": null, "late_payment_possible": false, "verified_at": null, "next_action": "show_qr"}`
- Venta 1: reintento (dos intentos en la misma venta) → 201 `{"status": "pending", "provider_request_id": "QRVC27A002", "previous_attempt_id": "64961601…", "late_payment_possible": true, "verified_at": null, "next_action": "show_qr"}`
- Venta 2: intento pendiente adicional → 201 `{"status": "pending", "provider_request_id": "QRVC27B001", "previous_attempt_id": null, "late_payment_possible": false, "verified_at": null, "next_action": "show_qr"}`
- Venta 3: intento → 201 `{"status": "pending", "provider_request_id": "QRVC27C001", "previous_attempt_id": null, "late_payment_possible": false, "verified_at": null, "next_action": "show_qr"}`
- Venta 3: webhook de pago → 204
- Ventas de A: 1=CK4RXT9XE0, 2=AR6XVAE8MW, 3=03GV5533KY, 4=MCYX573Y5F, 5=A6HV8C68WM; venta de B: 26T4RFGZ2Q

**TC01: páginas consecutivas con límite 2**

- Página 1 `{"limit": 2}` → 200 `{"items": [{"reference": "A6HV8C68WM", "status": "open", "covered": false, "confirmed": 0, "attempts": 0}, {"reference": "MCYX573Y5F", "status": "open", "covered": false, "confirmed": 0, "attempts": 0}], "next_cursor": "…"}`
- Página 2 `{"limit": 2, "cursor": "<cursor opaco>"}` → 200 `{"items": [{"reference": "03GV5533KY", "status": "paid", "covered": true, "confirmed": 30000, "attempts": 1}, {"reference": "AR6XVAE8MW", "status": "open", "covered": false, "confirmed": 0, "attempts": 1}], "next_cursor": "…"}`
- (se crea una venta nueva entre páginas)
- Página 3 `{"limit": 2, "cursor": "<cursor opaco>"}` → 200 `{"items": [{"reference": "CK4RXT9XE0", "status": "open", "covered": false, "confirmed": 0, "attempts": 2}], "next_cursor": null}`
- Fin: `next_cursor` de la página 3 = None
- Página 2 repetida con el mismo cursor tras la venta nueva `{"limit": 2, "cursor": "<cursor opaco>"}` → 200 `{"items": [{"reference": "03GV5533KY", "status": "paid", "covered": true, "confirmed": 30000, "attempts": 1}, {"reference": "AR6XVAE8MW", "status": "open", "covered": false, "confirmed": 0, "attempts": 1}], "next_cursor": "…"}`

**TC03: filtros por estado (una fila por venta)**

- Pendientes `{"status": "open"}` → 200 `{"items": [{"reference": "Z32AXVP1RP", "status": "open", "covered": false, "confirmed": 0, "attempts": 0}, {"reference": "A6HV8C68WM", "status": "open", "covered": false, "confirmed": 0, "attempts": 0}, {"reference": "MCYX573Y5F", "status": "open", "covered": false, "confirmed": 0, "attempts": 0}, {"reference": "AR6XVAE8MW", "status": "open", "covered": false, "confirmed": 0, "attempts": 1}, {"reference": "CK4RXT9XE0", "status": "open", "covered": false, "confirmed": 0, "attempts": 2}], "next_cursor": null}`
- Confirmadas `{"status": "paid"}` → 200 `{"items": [{"reference": "03GV5533KY", "status": "paid", "covered": true, "confirmed": 30000, "attempts": 1}], "next_cursor": null}`

**TC02: entradas inválidas y comercio ajeno**

- `{"status": "cancelled"}` → 422
- `{"limit": 51}` → 422
- `{"limit": 0}` → 422
- `{"foo": "1"}` → 422
- `{"cursor": "manipulado"}` → 422
- `{"created_from": "2026-11-25T12:00:00"}` → 422
- `{"created_from": "2026-11-26T00:00:00Z", "created_to": "2026-11-25T00:00:00Z"}` → 422
- Operador A filtrando el comercio de B `{"merchant_id": "260e39dd-61d5-4448-9c55-2f9170cd75f0"}` → 404 `{"detail": "Merchant not found"}`
- Operador B (solo su comercio) `{}` → 200 `{"items": [{"reference": "26T4RFGZ2Q", "status": "open", "covered": false, "confirmed": 0, "attempts": 0}], "next_cursor": null}`
- Sin sesión → 401

**Arrastre de B10: receptor deshabilitado**

- Confirmadas con el receptor deshabilitado `{"status": "paid"}` → 200 `{"items": [{"reference": "03GV5533KY", "status": "paid", "covered": true, "confirmed": 30000, "attempts": 1}], "next_cursor": null}`
- Venta nueva con el receptor deshabilitado → 409 `{"detail":"The receiving account is disabled; new charges are blocked until it is enabled"}`

Validación contra el contrato y los AC:

- **TC01:** las páginas 2/2/1 recorren las 5 ventas de A en orden descendente, sin repetir ni omitir. Repetir la página 2 con el mismo cursor después de crear una venta nueva devuelve las mismas filas.
- **TC03:** `open` lista una fila por venta pendiente, incluida la de dos intentos (`attempts: 2`). `paid` lista solo la confirmada, con `covered: true` y 30000.
- **TC02:** las entradas inválidas o desconocidas dan `422`. El comercio ajeno da `404`, el operador B solo ve su venta y sin sesión hay `401`.
- **B10:** con el receptor deshabilitado, la venta pagada sigue en el historial y una venta nueva da `409`.

Los datos se eliminaron al terminar. Estado VC01: **PASS**.

### Contrato `GET /sales` (resultado inicial)

```json
{
 "HistoryResponse.required": [
  "items",
  "next_cursor"
 ],
 "SaleRowResponse.required": [
  "id",
  "merchant_id",
  "reference",
  "amount_cents",
  "currency",
  "concept",
  "status",
  "covered",
  "confirmed_amount_cents",
  "attempt_count",
  "beneficiary_name",
  "masked_account",
  "created_at"
 ],
 "parameters": [
  {
   "in": "query",
   "name": "merchant_id",
   "required": false,
   "schema": {
    "anyOf": [
     {
      "format": "uuid",
      "type": "string"
     },
     {
      "type": "null"
     }
    ],
    "title": "Merchant Id"
   }
  },
  {
   "in": "query",
   "name": "status",
   "required": false,
   "schema": {
    "anyOf": [
     {
      "$ref": "#/components/schemas/SaleStatus"
     },
     {
      "type": "null"
     }
    ],
    "title": "Status"
   }
  },
  {
   "in": "query",
   "name": "created_from",
   "required": false,
   "schema": {
    "anyOf": [
     {
      "format": "date-time",
      "type": "string"
     },
     {
      "type": "null"
     }
    ],
    "title": "Created From"
   }
  },
  {
   "in": "query",
   "name": "created_to",
   "required": false,
   "schema": {
    "anyOf": [
     {
      "format": "date-time",
      "type": "string"
     },
     {
      "type": "null"
     }
    ],
    "title": "Created To"
   }
  },
  {
   "in": "query",
   "name": "limit",
   "required": false,
   "schema": {
    "default": 20,
    "maximum": 100,
    "minimum": 1,
    "title": "Limit",
    "type": "integer"
   }
  },
  {
   "in": "query",
   "name": "cursor",
   "required": false,
   "schema": {
    "anyOf": [
     {
      "maxLength": 256,
      "type": "string"
     },
     {
      "type": "null"
     }
    ],
    "title": "Cursor"
   }
  }
 ],
 "responses": [
  "200",
  "404",
  "422"
 ]
}
```

Nota: el volcado del contrato se tomó sobre `675e62f`. En `27d4eb2` cambia solo `limit.maximum` de 100 a 50.

## Checks

`uv run python -m quality.check` sobre `27d4eb2`, con `.env` exportado: PASS en todos los pasos.

- format, lint y types (mypy strict).
- hygiene.
- migrations, sin migraciones nuevas.
- tests: 503 passed, Postgres real aislado.
- api: 16 contratos sin diferencias.
- evidence: B01–B26 APPROVED.

## Supresiones

Sin supresiones nuevas.

## Umbral

AC PASS / AC aplicables = 3/3 = **100%**. El arrastre de B10 también pasa.

## Review Standards/Spec

| Ronda | Revisión | Standards | Spec | Hallazgos |
| --- | --- | --- | --- | --- |
| 1 | `675e62f` | APPROVE | REQUEST_CHANGES | Ver detalle debajo de la tabla |
| 2 | `27d4eb2` + `d3d9f95` | APPROVE | APPROVE | Máximo de 50 corregido y probado; evidencia fiel. Nit aplicado en `9678241` + `80c9d7c`: el test del límite se llama `test_fifty_is_the_largest_accepted_limit` |

Detalle de la ronda 1, aplicado en `27d4eb2` con Red/Green:

- **Spec:** el máximo de página debía ser 50 según el §10 de la arquitectura, y no 100.
- **Notas de Standards:**
  - argumentos por nombre en `HistoryQuery`;
  - `filtered_sales`;
  - test de parámetro desconocido.

Registrados sin cambio:

- la regla de `covered` y de lo confirmado está tanto en SQL (historial) como en Python (detalle), para evitar N+1;
- falta un índice para paginar con volumen.

Hallazgos pendientes: 0.
