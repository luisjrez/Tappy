# Evidencia — B29 Consultar resumen diario

Ticket: [#37](https://github.com/luisjrez/Tappy/issues/37) · Historia: [H6 #6](https://github.com/luisjrez/Tappy/issues/6) · Protocolo: [TICKET_QUALITY_PROTOCOL](../planning/TICKET_QUALITY_PROTOCOL.md) · Manifiesto: [B29-daily-summary.toml](B29-daily-summary.toml)

> Verificado con eventos sintéticos firmados localmente y con un pey falso local. **No hubo pagos reales.** El resumen informa el importe recibido. No es saldo bancario ni utilidad.

## Revisiones y escenario

- **Trazabilidad:** B29-UC01–UC03, B29-AC01–AC03 y B29-VC01.
- **Modalidad: resultado inicial.**
  - `GET /merchants/{id}/summary/daily` es nuevo.
  - El historial (B27) pasa a usar el criterio central de dinero recibido y cobertura. Su contrato no cambia.
- **Base y revisiones:**
  - Base: rama B28 `0f6c1ae` ([PR #84](https://github.com/luisjrez/Tappy/pull/84)), stack #68.
  - Candidato: `cfa7729`.
  - Correcciones de la review: `606b410` (ronda 1) y `0b9902d` (notas de la ronda 2), revisión final. La VC01 se repitió sobre ella con las mismas cifras.
- **Entorno:** macOS, Colima + Compose (Postgres 18), Python 3.14.8. Fecha: 2026-11-25 (UTC). Ejecutor: sesión local de desarrollo del autor del PR.

## Diseño

### Día del negocio

`BusinessDay` (`tappy.sales.periods`) va de medianoche a medianoche locales en `TAPPY_TIMEZONE`.

- El valor por defecto es `America/Mexico_City`. Se acepta cualquier zona IANA, y el validador rechaza las desconocidas.
- Si no se indica `date`, el día es hoy según el reloj del servidor.
- B30 ampliará el mismo `BusinessDay` a semana y mes.

### Criterio único de dinero recibido

Vive en `tappy.sales.received` y lo comparten el historial y el resumen:

- **Dinero recibido:** suma de las transferencias registradas. Todas son recepciones propias verificadas.
- **Asignación al día:** por la hora de pago de pey (`datePaid` → `occurred_at`), no por la de recepción. Así lo indica PRODUCT_BASE: la fecha bancaria validada determina el periodo.
- **Cobertura:** la primera transferencia exacta de un intento `paid`, ordenada por hora de pago, después por recepción y después por id. Es una sola regla SQL (`covering`, reutilizada por `covers_its_sale` y `sale_is_covered`), y `covering_reception` la aplica con el mismo orden en Python al detalle y al comprobante.

### Qué cuenta el resumen

- `received_amount_cents` y `transfer_count`.
- `covered_sale_count`: ventas cuya transferencia de cobertura se pagó ese día. Una segunda transferencia suma dinero, pero nunca otra venta cubierta, ni ese día ni otro.
- `review_sale_count`: ventas en `review` con transferencias ese día.
- `open_exception_count`: incidencias propias abiertas ese día, en ventas del comercio, con o sin transferencia.

Base de fechas: el dinero y la cobertura se asignan por la hora de pago de pey; las incidencias, por la hora del servidor en que se abrieron.

Las ventas pendientes y las solicitudes vencidas no suman: no tienen transferencias. Una notificación repetida tampoco suma, porque el `transactionId` es único.

### Acceso

Solo se consultan los comercios accesibles (operador miembro o administrador). Cualquier otro devuelve `404 Merchant not found`, y una fecha inválida devuelve `422`.

## Trazabilidad UC → AC → TC → test

Todos los tests están en `tests/sales/test_daily_summary.py`.

| UC | AC | TC | Test real | Resultado |
| --- | --- | --- | --- | --- |
| B29-UC01 | B29-AC01 | B29-TC01 | `test_received_money_counts_transfers_and_covered_sales_but_not_pending` (30000 + 15000 y pendiente de 20000 → cuerpo exacto: 45000, 2 transferencias, 2 ventas cubiertas); `test_redelivered_evidence_never_inflates_the_summary`; `test_the_day_follows_the_business_timezone_not_utc`; `test_the_default_day_is_todays_local_date_on_the_server_clock`; `test_the_business_timezone_must_be_a_known_iana_zone` | PASS |
| B29-UC02 | B29-AC02 | B29-TC02 | `test_a_day_without_confirmed_transfers_reports_nothing`; `test_invalid_days_are_rejected`; `test_summaries_are_limited_to_accessible_merchants` | PASS |
| B29-UC03 | B29-AC03 | B29-TC03 | `test_a_second_distinct_transfer_counts_money_but_not_another_sale` (60000, 2 transferencias, 1 venta cubierta, 1 en revisión, 1 incidencia `double_reception`); `test_a_covered_sale_counts_only_on_the_day_of_its_covering_transfer`; `test_own_incidents_opened_that_day_are_visible_even_without_a_transfer` | PASS |

## TDD

**Red:** los tests se escribieron antes del código. Fallan los 9 porque la ruta no existía. `test_the_default_day_is_todays_local_date_on_the_server_clock` se añadió después de ese Red, junto con el primer Green, así que no tiene Red propio.

```
FAILED tests/sales/test_daily_summary.py::test_received_money_counts_transfers_and_covered_sales_but_not_pending
FAILED tests/sales/test_daily_summary.py::test_a_day_without_confirmed_transfers_reports_nothing
FAILED tests/sales/test_daily_summary.py::test_a_second_distinct_transfer_counts_money_but_not_another_sale
FAILED tests/sales/test_daily_summary.py::test_redelivered_evidence_never_inflates_the_summary
FAILED tests/sales/test_daily_summary.py::test_the_day_follows_the_business_timezone_not_utc
FAILED tests/sales/test_daily_summary.py::test_invalid_days_are_rejected[2026-13-01]
FAILED tests/sales/test_daily_summary.py::test_invalid_days_are_rejected[25/11/2026]
FAILED tests/sales/test_daily_summary.py::test_invalid_days_are_rejected[yesterday]
FAILED tests/sales/test_daily_summary.py::test_summaries_are_limited_to_accessible_merchants
9 failed in 4.52s
```

| Comportamiento | Red | Green |
| --- | --- | --- |
| Resumen, día local y criterio central | Ver arriba | `periods`, `received`, `summaries`, `reports_router`, `TAPPY_TIMEZONE` |
| Venta cubierta una sola vez entre días (review) | `assert (30000, 1) == (30000, 0)`: el día 2 contaba otra vez la venta cubierta | `covers_its_sale`: la cobertura cuenta solo en el día de la transferencia que cubre |
| Incidencias propias del día (review) | `assert (0, 0) == (0, 1)`: una incidencia `receiver_mismatch` sin transferencia no aparecía | Incidencias del comercio abiertas ese día |
| Validador de zona (review) | Test nuevo de la zona IANA | `known_timezone`, `Settings.zone` |
| Mutaciones | Día en UTC: fallan 3. Contar transferencias en vez de ventas cubiertas: falla TC03 | — |

## Aplicabilidad por superficie

| Superficie | Aplica | Justificación |
| --- | --- | --- |
| API | Sí | Endpoint nuevo |
| Panel | No aplica | Sin vistas en este alcance |
| Comandos | No aplica | Sin comandos nuevos |

## B29-VC01 — Resultado inicial del resumen diario

Proceso real `python -m tappy` con `TAPPY_PAYMENT_PROVIDER=pey` y un pey falso local. Los webhooks firmados llevan un `datePaid` fijo del 25 de noviembre, hora de Ciudad de México: un pago a las 12:00 y otro a las 23:30, que en UTC ya es el 26. Las incidencias se fechan con el reloj real del servidor, que también era el 25. Revisión `0b9902d`; las cifras son idénticas a las de `606b410`. Valores sintéticos.

**Movimientos (pagos con fecha del 25 de noviembre, hora de Ciudad de México)**

- Venta de 300.00 → 201 `{"status": "pending", "provider_request_id": "QRVC29A001", "previous_attempt_id": null, "late_payment_possible": false, "verified_at": null, "next_action": "show_qr"}`
- Venta de 150.00 → 201 `{"status": "pending", "provider_request_id": "QRVC29B001", "previous_attempt_id": null, "late_payment_possible": false, "verified_at": null, "next_action": "show_qr"}`
- Venta de 200.00 (queda pendiente) → 201 `{"status": "pending", "provider_request_id": "QRVC29C001", "previous_attempt_id": null, "late_payment_possible": false, "verified_at": null, "next_action": "show_qr"}`
- Pago de 300.00 a las 12:00 → 204
- Pago de 150.00 a las 23:30 (ya es 26 en UTC) → 204
- Reenvío del pago de 300.00 con otro id de evento → 204

**TC01 y TC02**

- Resumen del 25 `{"date": "2026-11-25"}` → 200 `{"date":"2026-11-25","timezone":"America/Mexico_City","received_amount_cents":45000,"currency":"MXN","transfer_count":2,"covered_sale_count":2,"review_sale_count":0,"open_exception_count":0}`
- Resumen del 26 (ningún pago con esa fecha local) `{"date": "2026-11-26"}` → 200 `{"date":"2026-11-26","timezone":"America/Mexico_City","received_amount_cents":0,"currency":"MXN","transfer_count":0,"covered_sale_count":0,"review_sale_count":0,"open_exception_count":0}`

**TC03: segunda transferencia distinta para la venta de 300.00**

- Segundo pago de 300.00 por el mismo QR a las 12:00 → 204
- Resumen del 25 `{"date": "2026-11-25"}` → 200 `{"date":"2026-11-25","timezone":"America/Mexico_City","received_amount_cents":75000,"currency":"MXN","transfer_count":3,"covered_sale_count":2,"review_sale_count":1,"open_exception_count":1}`
- Detalle de la venta de 300.00 → `{"status": "review", "covered": true, "confirmed_amount_cents": 60000, "exceptions": ["double_reception"]}`

**Acceso y entradas**

- Operador de otro comercio `{"date": "2026-11-25"}` → 404 `{"detail":"Merchant not found"}`
- Fecha inválida `{"date": "2026-13-01"}` → 422 `{"detail":[{"type":"date_from_datetime_parsing","loc":["query","date"],"msg":"Input should be a valid date or datetime, month value is outside expected range of 1-12"}]}`
- Sin sesión → 401

Validación:

- **TC01:**
  - El día 25 suma 45000 en 2 transferencias y 2 ventas cubiertas.
  - El pendiente de 200.00 queda fuera.
  - El reenvío no suma.
  - El pago de las 23:30 cuenta en el 25 local.
- **TC02:** el día 26 sale todo en 0.
- **TC03:** el segundo pago distinto de la venta de 300.00 suma dinero y transferencia (75000 = 45000 + 30000, 3 transferencias), pero no otra venta cubierta (siguen 2). La revisión y la incidencia quedan visibles, y el detalle confirma `review`, `covered` y `double_reception`.
- **Acceso:** otro comercio da `404`, una fecha inválida da `422` y sin sesión da `401`.

Los datos se eliminaron al terminar. Estado VC01: **PASS**.

## Checks

`uv run python -m quality.check` sobre `606b410` y `0b9902d`, con `.env` exportado: PASS en todos los pasos.

- format, lint y types (mypy strict).
- hygiene.
- migrations: sin migraciones nuevas.
- tests: 523 passed, Postgres real aislado.
- api: 16 contratos sin diferencias.
- evidence: B01–B28 APPROVED.

Sobre `0b9902d` el gate vuelve a pasar 523 tests; el único fallo de evidencia es la review en curso, que se registra abajo. Una ejecución intermedia tuvo 1 error de infraestructura, ajeno al cambio: `test_local_data_survives_database_recreation…` falló al levantar un Compose temporal (`docker compose up … returned non-zero exit status 1`). Al repetirlo pasó 2/2, y la ejecución completa siguiente pasó entera.

## Supresiones

Sin supresiones nuevas.

## Umbral

AC PASS / AC aplicables = 3/3 = **100%**.

## Review Standards/Spec

| Ronda | Revisión | Standards | Spec | Hallazgos |
| --- | --- | --- | --- | --- |
| 1 | `cfa7729` | REQUEST_CHANGES | REQUEST_CHANGES | Ver detalle debajo de la tabla |
| 2 | `606b410` + `8f980ed` | APPROVE | APPROVE | Hallazgos resueltos. Notas aplicadas en `0b9902d`: una sola copia SQL de la regla de cobertura, la transferencia que cubre se elige por hora de pago en SQL y en Python, la base de fechas queda explícita y el Red se completa |

Detalle de la ronda 1. Todo se aplicó en `606b410` con Red/Green.

**Spec:**

- Una venta cubierta podía volver a contarse otro día.
- Las incidencias propias sin transferencia no aparecían, y las de otros días se contaban.

**Standards:**

- Faltaba un test del validador de zona.
- `BusinessDay.bounds` y `BusinessDay.today` reemplazan funciones sueltas.
- `Settings.zone` evita parsear la zona en cada petición.
- Las filas usan columnas con nombre.
- `paid_between` se renombró a `transfer_paid_between`.
- Se quitó un alias de paso en el historial.

**Registrado sin cambio:**

- La regla de cobertura existe en SQL (`received`) y en Python (`covering_reception`), y el test de consistencia de B28 compara historial, detalle y comprobante.
- La ruta difiere del boceto `/v1/reports/summary`: no hay `/v1` y la zona es del negocio, no del comercio. B30 debe extender esta misma ruta.

Hallazgos pendientes: 0.
