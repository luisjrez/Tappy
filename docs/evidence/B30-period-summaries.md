# Evidencia — B30 Consultar semana y mes con fechas locales

Ticket: [#38](https://github.com/luisjrez/Tappy/issues/38) · Historia: [H6 #6](https://github.com/luisjrez/Tappy/issues/6) · Protocolo: [TICKET_QUALITY_PROTOCOL](../planning/TICKET_QUALITY_PROTOCOL.md) · Manifiesto: [B30-period-summaries.toml](B30-period-summaries.toml)

> Verificado con eventos sintéticos firmados localmente y con un pey falso local. **No hubo pagos reales.** Los reportes solo leen la base de datos y nunca consultan al banco.

## Revisiones y escenario

- **Trazabilidad:** B30-UC01–UC03, B30-AC01–AC03 y B30-VC01.
- **Modalidad: antes/después.**
  - `GET /merchants/{id}/summary?period=` es nuevo; antes respondía 404.
  - Cambia el registro de evidencia válida sin `datePaid`: antes era una incidencia `incomplete_evidence` sin registro; ahora se registra fechada por la recepción.
  - Las transferencias y el comprobante ganan `dated_by`, y `occurred_at`/`paid_at` pueden ser nulos.
- **Cambios esperados en tests anteriores:**
  - En B18 y B20, el caso de «sin fecha» pasa a «fecha presente pero inválida», que sigue siendo evidencia incompleta.
  - Los cuerpos exactos de B18 y B28 incluyen `dated_by: bank`.
- **Base y revisiones:**
  - Base: rama B29 `00b3b31` ([PR #85](https://github.com/luisjrez/Tappy/pull/85)), stack #68.
  - Candidato: `3fd634e`.
  - Correcciones de la review: `34b2679`, revisión final. La VC01 se repitió sobre ella.
- **Entorno:** macOS, Colima + Compose (Postgres 18), Python 3.14.8. Fecha: 2026-11-25 (UTC). Ejecutor: sesión local de desarrollo del autor del PR.

## Diseño

### Periodos

`BusinessPeriod` (`tappy.sales.periods`) unifica el día de B29, la semana y el mes:

- **Día:** de medianoche a medianoche locales.
- **Semana:** de lunes a domingo.
- **Mes:** del día 1 al último, calculado con `calendar.monthrange`.
- **Zona:** `TAPPY_TIMEZONE`, por defecto `America/Mexico_City`.
- **Rangos:** `start` y `end` explícitos (fechas locales) y `bounds` con medianoches locales; `BusinessPeriod.at` toma el día pedido o el de hoy según el reloj del servidor.

### Endpoint

- `GET /merchants/{id}/summary?period=day|week|month&date=` devuelve los totales de B29, `reception_dated_transfer_count` y un desglose `days` con todos los días del periodo, también los que no tienen transferencias.
- `/summary/daily` (B29) queda como el periodo `day`, con el mismo contrato.
- Un periodo o parámetro desconocido responde `422`, y un comercio ajeno `404`.

### Fecha de una transferencia

La regla es una sola, `dated_at`, en SQL (`tappy.sales.received`) y en Python (`service`): la hora de pago de pey, o la de recepción si falta.

- Una evidencia válida sin `datePaid` (cuenta, importe, transacción y asociación verificados, como siempre) se registra con `occurred_at` nulo y `dated_by: reception`. No se inventa una fecha bancaria, y el periodo lo cuenta en `reception_dated_transfer_count`.
- Un `datePaid` presente pero inválido sigue siendo `incomplete_evidence` (`bank_time_invalid`).

### Evidencia tardía

Llega más evidencia de la misma transacción (webhook o conciliación) con la hora bancaria de una transferencia fechada por recepción:

- se rellena `occurred_at` una sola vez (`date_by_bank`) sin tocar el dinero;
- la transferencia pasa a su periodo bancario;
- un segundo dato distinto ya no la cambia.

La migración `0022` hace `occurred_at` anulable y ajusta el trigger de inmutabilidad: solo permite ese relleno de nulo a valor, con todas las demás columnas iguales. Cualquier otro UPDATE, DELETE o TRUNCATE sigue rechazado. El downgrade restaura el trigger y se niega si quedan transferencias sin hora bancaria.

### Sin doble conteo

- Un pago de fin de mes notificado al mes siguiente cuenta en su mes bancario.
- La conciliación lo ve como `duplicate`.
- Una venta cubierta cuenta una vez, en el día de su transferencia de cobertura, ordenada por `dated_at`.

## Trazabilidad UC → AC → TC → test

Todos los tests están en `tests/sales/test_period_summaries.py`.

| UC | AC | TC | Test real | Resultado |
| --- | --- | --- | --- | --- |
| B30-UC01 | B30-AC01 | B30-TC01 | `test_movements_follow_the_local_calendar_and_monday_to_sunday_weeks` (domingo 23:30, lunes 00:30, lunes 23:50 y martes 1 de diciembre 00:10: días, dos semanas, noviembre y diciembre con su desglose); `test_the_daily_endpoint_matches_the_day_period`; `test_invalid_periods_are_rejected`; `test_period_summaries_are_limited_to_accessible_merchants` | PASS |
| B30-UC02 | B30-AC02 | B30-TC02 | `test_a_valid_reception_without_a_bank_time_uses_the_reception_time_explicitly` (`occurred_at` nulo, `dated_by: reception`, contada por su recepción); `tests/sales/test_receipts.py::test_a_receipt_without_a_bank_time_says_it_is_dated_by_reception` | PASS |
| B30-UC03 | B30-AC03 | B30-TC03 | `test_a_month_end_payment_notified_next_month_counts_once_in_its_bank_month`; `test_a_late_bank_time_moves_a_reception_dated_transfer_to_its_bank_period_once` (febrero por recepción → enero por fecha bancaria, una vez; un segundo dato no la mueve); `test_the_database_only_lets_a_missing_bank_time_be_filled_once` | PASS |

## TDD

**Red:** los tests se escribieron antes del código y los 9 fallaban porque la ruta no existía.

```
E       KeyError: 'start'
E       KeyError: 'received_amount_cents'
E       KeyError: 'received_amount_cents'
E       assert 404 == <HTTPStatus.UNPROCESSABLE_CONTENT: 422>
E       assert 404 == <HTTPStatus.UNPROCESSABLE_CONTENT: 422>
E       assert 404 == <HTTPStatus.UNPROCESSABLE_CONTENT: 422>
E       assert 404 == <HTTPStatus.UNPROCESSABLE_CONTENT: 422>
FAILED tests/sales/test_period_summaries.py::test_movements_follow_the_local_calendar_and_monday_to_sunday_weeks
FAILED tests/sales/test_period_summaries.py::test_a_valid_reception_without_a_bank_time_uses_the_reception_time_explicitly
FAILED tests/sales/test_period_summaries.py::test_a_month_end_payment_notified_next_month_counts_once_in_its_bank_month
FAILED tests/sales/test_period_summaries.py::test_the_daily_endpoint_matches_the_day_period
FAILED tests/sales/test_period_summaries.py::test_invalid_periods_are_rejected[params0]
FAILED tests/sales/test_period_summaries.py::test_invalid_periods_are_rejected[params1]
FAILED tests/sales/test_period_summaries.py::test_invalid_periods_are_rejected[params2]
FAILED tests/sales/test_period_summaries.py::test_invalid_periods_are_rejected[params3]
FAILED tests/sales/test_period_summaries.py::test_period_summaries_are_limited_to_accessible_merchants
9 failed in 4.30s
```

| Comportamiento | Red | Green |
| --- | --- | --- |
| Periodos, desglose y respaldo de fecha | Ver arriba | `BusinessPeriod`, `period_summary`, `0022`, `dated_by`, `bank_time_invalid` |
| Corrección por fecha bancaria tardía (review) | `assert (0, 0) == (10000, 0)` y `RaiseException: recorded transfers are immutable` | `date_by_bank` y el trigger que solo admite el relleno único |
| Mutaciones | Sin respaldo por recepción: falla TC02. Semana que empieza en domingo: falla TC01. Periodo por recepción en vez de fecha bancaria: fallan TC01 y TC03. Sin `date_by_bank`: falla la corrección tardía | — |

## Aplicabilidad por superficie

| Superficie | Aplica | Justificación |
| --- | --- | --- |
| API | Sí | Endpoint de periodo nuevo y `dated_by` en transferencias y comprobante |
| Panel | No aplica | Sin vistas en este alcance |
| Comandos | Sí, sin cambios | `reconcile` corrige la fecha a través de la misma evidencia |

## B30-VC01 — Antes/después de periodos y fechas

Proceso real `python -m tappy` con `TAPPY_PAYMENT_PROVIDER=pey` y un pey falso local. Los webhooks firmados tienen un `datePaid` fijo, en hora de Ciudad de México:

- domingo 29 de noviembre, 23:30;
- lunes 30, 00:30 y 23:50;
- martes 1 de diciembre, 00:10;
- sábado 31 de octubre, 23:50 (notificado en noviembre);
- uno sin `datePaid`, recibido el 25 de noviembre según el reloj real.

Las conciliaciones se hacen con el comando real `reconcile`. Valores sintéticos.

### Antes (B29 `00b3b31`)

**Movimientos (100.00 cada uno; hora de Ciudad de México)**

- Pago del domingo 29 nov 23:30 → 204
- Pago del lunes 30 nov 00:30 → 204
- Pago del lunes 30 nov 23:50 → 204
- Pago del martes 1 dic 00:10 → 204
- Pago del sábado 31 oct 23:50, notificado en noviembre → 204
- Pago válido sin datePaid (fecha bancaria ausente) → 204
- Transferencias de la venta 6 → `[]`

**TC01: día, semana lunes-domingo y mes**

- Día 29 `{"date": "2026-11-29"}` → 200 `{"date": "2026-11-29", "received_amount_cents": 10000, "transfer_count": 1, "covered_sale_count": 1}`
- Día 30 `{"date": "2026-11-30"}` → 200 `{"date": "2026-11-30", "received_amount_cents": 20000, "transfer_count": 2, "covered_sale_count": 2}`
- Semana del domingo 29 `{"period": "week", "date": "2026-11-29"}` → 404 `{"detail": "Not Found"}`
- Semana del lunes 30 `{"period": "week", "date": "2026-11-30"}` → 404 `{"detail": "Not Found"}`
- Noviembre `{"period": "month", "date": "2026-11-15"}` → 404 `{"detail": "Not Found"}`
- Diciembre `{"period": "month", "date": "2026-12-01"}` → 404 `{"detail": "Not Found"}`

**TC03: pago de fin de octubre notificado en noviembre, y conciliado otra vez**

- Octubre `{"period": "month", "date": "2026-10-15"}` → 404 `{"detail": "Not Found"}`
- `reconcile` del intento de octubre → `applied: 0, duplicates: 1, in review: 0 | result: payment confirmed` (exit 0)
- Octubre tras conciliar `{"period": "month", "date": "2026-10-15"}` → 404 `{"detail": "Not Found"}`

**Entradas**

- Periodo inválido `{"period": "year", "date": "2026-11-30"}` → 404 `{"detail": "Not Found"}`

### Después (revisión final `34b2679`)

**Movimientos (100.00 cada uno; hora de Ciudad de México)**

- Pago del domingo 29 nov 23:30 → 204
- Pago del lunes 30 nov 00:30 → 204
- Pago del lunes 30 nov 23:50 → 204
- Pago del martes 1 dic 00:10 → 204
- Pago del sábado 31 oct 23:50, notificado en noviembre → 204
- Pago válido sin datePaid (fecha bancaria ausente) → 204
- Transferencias de la venta 6 → `[{"provider_transaction_id": "TX-VC30-NODATE", "occurred_at": null, "dated_by": "reception"}]`

**TC01: día, semana lunes-domingo y mes**

- Día 29 `{"date": "2026-11-29"}` → 200 `{"date": "2026-11-29", "received_amount_cents": 10000, "transfer_count": 1, "covered_sale_count": 1}`
- Día 30 `{"date": "2026-11-30"}` → 200 `{"date": "2026-11-30", "received_amount_cents": 20000, "transfer_count": 2, "covered_sale_count": 2}`
- Semana del domingo 29 `{"period": "week", "date": "2026-11-29"}` → 200 `{"period": "week", "start": "2026-11-23", "end": "2026-11-29", "received_amount_cents": 20000, "transfer_count": 2, "covered_sale_count": 2, "reception_dated_transfer_count": 1, "busy_days": [{"date": "2026-11-25", "received": 10000, "transfers": 1}, {"date": "2026-11-29", "received": 10000, "transfers": 1}], "days_listed": 7}`
- Semana del lunes 30 `{"period": "week", "date": "2026-11-30"}` → 200 `{"period": "week", "start": "2026-11-30", "end": "2026-12-06", "received_amount_cents": 30000, "transfer_count": 3, "covered_sale_count": 3, "reception_dated_transfer_count": 0, "busy_days": [{"date": "2026-11-30", "received": 20000, "transfers": 2}, {"date": "2026-12-01", "received": 10000, "transfers": 1}], "days_listed": 7}`
- Noviembre `{"period": "month", "date": "2026-11-15"}` → 200 `{"period": "month", "start": "2026-11-01", "end": "2026-11-30", "received_amount_cents": 40000, "transfer_count": 4, "covered_sale_count": 4, "reception_dated_transfer_count": 1, "busy_days": [{"date": "2026-11-25", "received": 10000, "transfers": 1}, {"date": "2026-11-29", "received": 10000, "transfers": 1}, {"date": "2026-11-30", "received": 20000, "transfers": 2}], "days_listed": 30}`
- Diciembre `{"period": "month", "date": "2026-12-01"}` → 200 `{"period": "month", "start": "2026-12-01", "end": "2026-12-31", "received_amount_cents": 10000, "transfer_count": 1, "covered_sale_count": 1, "reception_dated_transfer_count": 0, "busy_days": [{"date": "2026-12-01", "received": 10000, "transfers": 1}], "days_listed": 31}`

**TC03: pago de fin de octubre notificado en noviembre, y conciliado otra vez**

- Octubre `{"period": "month", "date": "2026-10-15"}` → 200 `{"period": "month", "start": "2026-10-01", "end": "2026-10-31", "received_amount_cents": 10000, "transfer_count": 1, "covered_sale_count": 1, "reception_dated_transfer_count": 0, "busy_days": [{"date": "2026-10-31", "received": 10000, "transfers": 1}], "days_listed": 31}`
- `reconcile` del intento de octubre → `applied: 0, duplicates: 1, in review: 0 | result: payment confirmed` (exit 0)
- Octubre tras conciliar `{"period": "month", "date": "2026-10-15"}` → 200 `{"period": "month", "start": "2026-10-01", "end": "2026-10-31", "received_amount_cents": 10000, "transfer_count": 1, "covered_sale_count": 1, "reception_dated_transfer_count": 0, "busy_days": [{"date": "2026-10-31", "received": 10000, "transfers": 1}], "days_listed": 31}`

**TC03 bis: la fecha bancaria llega después para la transferencia sin datePaid (venta 6)**

- Mes de la recepción (noviembre) antes `{"period": "month", "date": "2026-11-15"}` → 200 `{"period": "month", "start": "2026-11-01", "end": "2026-11-30", "received_amount_cents": 40000, "transfer_count": 4, "covered_sale_count": 4, "reception_dated_transfer_count": 1, "busy_days": [{"date": "2026-11-25", "received": 10000, "transfers": 1}, {"date": "2026-11-29", "received": 10000, "transfers": 1}, {"date": "2026-11-30", "received": 20000, "transfers": 2}], "days_listed": 30}`
- `reconcile` de la venta 6 con datePaid del 30 de octubre → `applied: 0, duplicates: 1, in review: 0 | result: payment confirmed` (exit 0)
- Transferencias de la venta 6 → `[{"provider_transaction_id": "TX-VC30-NODATE", "occurred_at": "2026-10-31T00:00:00Z", "dated_by": "bank"}]`
- Noviembre después `{"period": "month", "date": "2026-11-15"}` → 200 `{"period": "month", "start": "2026-11-01", "end": "2026-11-30", "received_amount_cents": 30000, "transfer_count": 3, "covered_sale_count": 3, "reception_dated_transfer_count": 0, "busy_days": [{"date": "2026-11-29", "received": 10000, "transfers": 1}, {"date": "2026-11-30", "received": 20000, "transfers": 2}], "days_listed": 30}`
- Octubre después `{"period": "month", "date": "2026-10-15"}` → 200 `{"period": "month", "start": "2026-10-01", "end": "2026-10-31", "received_amount_cents": 20000, "transfer_count": 2, "covered_sale_count": 2, "reception_dated_transfer_count": 0, "busy_days": [{"date": "2026-10-30", "received": 10000, "transfers": 1}, {"date": "2026-10-31", "received": 10000, "transfers": 1}], "days_listed": 31}`

**Entradas**

- Periodo inválido `{"period": "year", "date": "2026-11-30"}` → 422 `{"detail": [{"type": "enum", "loc": ["query", "period"], "msg": "Input should be 'day', 'week' or 'month'"}]}`

Validación:

- **TC01:**
  - El día 29 suma 10000.
  - El día 30 suma 20000: el pago de las 00:30 es del 30 y no del 29.
  - La semana del domingo 29 va del 23 al 29.
  - La semana del lunes 30 va del 30 al 6 de diciembre e incluye el pago del 1.
  - Noviembre tiene 30 días listados; diciembre, 31.
- **TC02:** la transferencia sin `datePaid` tiene `occurred_at: null` y `dated_by: reception`, cuenta el 25, que es su recepción, y aparece en `reception_dated_transfer_count`.
- **TC03:**
  - El pago del 31 de octubre notificado en noviembre cuenta en octubre, y conciliarlo otra vez es `duplicate`.
  - La fecha bancaria que llega después para la transferencia sin `datePaid` la mueve de noviembre a octubre (30 de octubre) una sola vez: noviembre pasa de 40000 a 30000 y octubre de 10000 a 20000, con el dinero total sin cambios.
- **Antes:** el endpoint de periodo respondía 404, y la evidencia sin `datePaid` no se registraba (la venta 6 quedaba sin transferencia).

Los datos se eliminaron al terminar. Estado VC01: **PASS**.

### Diferencias y decisión

| TC/AC | Antes (B29) | Después | Clasificación | Decisión |
| --- | --- | --- | --- | --- |
| TC01 | Solo el resumen diario | Día, semana y mes con desglose | Nuevo | Aceptada |
| TC02 | Evidencia sin `datePaid`: `incomplete_evidence`, sin registro | Registrada, fechada por recepción y explícita | Comportamiento | Aceptada (PRODUCT_BASE y docs/01) |
| TC03 | — | Periodo bancario una vez, corrección tardía única | Nuevo | Aceptada |

## Checks

`uv run python -m quality.check` sobre `34b2679`, con `.env` exportado: PASS en todos los pasos.

- format, lint y types (mypy strict).
- hygiene.
- migrations: upgrade/downgrade/upgrade de `0022` + `alembic check`.
- tests: 535 passed, Postgres real aislado.
- api: 16 contratos sin diferencias.
- evidence: B01–B29 APPROVED.

## Supresiones

Sin supresiones nuevas.

## Umbral

AC PASS / AC aplicables = 3/3 = **100%**.

## Review Standards/Spec

| Ronda | Revisión | Standards | Spec | Hallazgos |
| --- | --- | --- | --- | --- |
| 1 | `3fd634e` | APPROVE | REQUEST_CHANGES | Ver el detalle debajo de la tabla |
| 2 | `34b2679` + `7ff94e5` | APPROVE | APPROVE | Corrección por fecha bancaria tardía y README verificados. Nota registrada: una hora bancaria distinta que llega después de una ya registrada se ignora sin incidencia; queda para un ticket posterior |

Detalle de la ronda 1. Todo se aplicó en `34b2679`, con Red/Green donde correspondía.

- **Spec:** una fecha bancaria tardía no corregía el periodo de una transferencia fechada por recepción, y la definición de `incomplete_evidence` en el README estaba desactualizada.
- **Notas de Standards:**
  - una sola regla `dated_at` en SQL, reutilizada por la cobertura;
  - helper `totals`;
  - `BusinessPeriod.at`;
  - `calendar.monthrange`.
- **Registrados sin cambio:**
  - el par `occurred_at` + `bank_time_invalid` (un tipo `BankTime` sería más limpio);
  - `DailySummaryView`, que conserva el contrato de B29.

Hallazgos pendientes: 0.
