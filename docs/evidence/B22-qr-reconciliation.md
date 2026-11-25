# Evidencia — B22 Conciliar QR cuando falta notificación

Ticket: [#30](https://github.com/luisjrez/Tappy/issues/30) · Historia: [H5 #5](https://github.com/luisjrez/Tappy/issues/5) · Protocolo: [TICKET_QUALITY_PROTOCOL](../planning/TICKET_QUALITY_PROTOCOL.md) · Manifiesto: [B22-qr-reconciliation.toml](B22-qr-reconciliation.toml)

> Verificado con el contrato oficial de pey (`GET /transaction/codi/qr/{id}`, OpenAPI `2026-10-20`) y con un pey falso local. **No hubo consultas, pagos ni webhooks reales**, y una simulación no demuestra la integración bancaria real. La conciliación solo aplica evidencia que devuelve el proveedor: ningún operador marca un cobro como recibido.

## Revisiones y escenario

- **Trazabilidad:** B22-UC01–UC03, B22-AC01–AC03, B22-TC01–TC03 y B22-VC01.
- **Modalidad: resultado inicial.** El comando `reconcile` y la consulta al proveedor son nuevos. La API no cambia de contrato (`api`: 16 contratos sin diferencias); el detalle del cobro solo refleja el resultado.
- **Contrato:** `tests/fixtures/pey/codi-qr-transactions.json`, extraído de `https://docs.pey.mx/openapi.json` (versión `2026-10-20`, sha256 `568e0255…5c5a`, el mismo documento que B15). Incluye parámetros (`id`, `nextToken`), el esquema de cada transacción (`id`, `status` `PENDING`/`PAID`, `amount`, `datePaid`…) y todas las respuestas (200, 400×3, 404, 429, 500).
- **Base y revisiones:**
  - Base: rama B21 `c052d2c` ([PR #77](https://github.com/luisjrez/Tappy/pull/77)), stack #68.
  - Candidato: `0d47d1b`.
  - Notas de la review: `3c72677`, revisión final. La VC01 se repitió sobre ella.
- **Entorno:** macOS, Colima + Compose (Postgres 18), Python 3.14.8. Fecha: 2026-11-25 (UTC). Ejecutor: sesión local de desarrollo del autor del PR.

## Diseño

### Consulta acotada (`tappy.payments.pey.PeyQrProvider.qr_payments`)

- `GET /transaction/codi/qr/{id}` con el id de QR codificado en la ruta, el mismo cliente, autenticación y timeout que la creación, y `nextToken` como parámetro.
- Sigue `nextToken` hasta **10 páginas** (`MAX_QUERY_PAGES`, 200 transacciones). Si hay más, el resultado es incierto (`too_many_pages`).
- Devuelve solo las transacciones `PAID` como `QrPayment` (id, centavos, fecha de pago). La normalización de importe y fecha reutiliza `cents` y `paid_at` de los webhooks; si no es exacta, el pago queda incompleto (`None`) y B20 lo manda a revisión.
- Política de errores: 404 → `not_found`, 429 → `rate_limited`, 400 → `rejected`, otro estado → `server_error`, cuerpo inválido o transacción sin `id` → `invalid_response`, timeout/conexión → `timeout`/`connection` (mapa explícito desde la política de la creación). Todo eso es `PaymentsQueryError`: **nunca es un rechazo**.
- El simulador nunca informa pagos (`[]`).

### Conciliación por intento (`tappy.sales.reconciliation.reconcile_attempt`)

1. Lee el intento en una transacción corta y la cierra antes de llamar al proveedor (no hay transacción abierta durante la red).
2. Solo se consulta un intento con id de QR propio y del mismo proveedor; si no, `not_queryable`.
3. Cada pago se convierte en `PaymentEvidence` con el QR y el id del intento, el `transactionId` de pey, el entorno (`TAPPY_ENVIRONMENT`) y **la cuenta para la que se emitió el QR**: la respuesta de pey no trae `bankAccountId`, solo devuelve transacciones de QR creados con nuestra API key, y el QR se creó con la instantánea del receptor del intento (B15).
4. Se aplica con la operación única `apply_evidence(db, evidence, None, now)` de B18–B21: mismo lock consultivo, intento y cobro, mismas validaciones (importe exacto, cuenta, transacción) y misma deduplicación por `(proveedor, entorno, transactionId)`.
5. Si el intento queda `paid`, se cierran sus trabajos de conciliación pendientes (`done`). Sin evidencia o con error, el intento conserva su estado (`pending`/`reconciling`), sin `failure_code` ni `expired`.

Resultado: `confirmed`, `review`, `no_evidence`, `uncertain` o `not_queryable`.

### Comando operativo

`python -m tappy.sales reconcile <attempt-id>` imprime intento, referencia, QR, pagos encontrados, aplicados/duplicados/en revisión, estado del intento y del cobro, y el resultado en texto. Decisión: termina con código 0 siempre que la consulta se intentó (también si fue incierta), porque la ausencia o el error no son fallos del cobro; la línea `result:` lo distingue. Un intento inexistente termina con 1 (`Attempt not found`) y un id mal formado con 2 (argparse).

### Arrastres

| Origen | Requisito | Estado |
| --- | --- | --- |
| B18–B20 | Usar `apply_evidence(..., event_id=None, ...)`; no generar evidencia de consulta sin `transactionId` (la unicidad con `NULLS NOT DISTINCT` las fundiría) | Cumplido: `id` es obligatorio en cada transacción; sin él, la respuesta es inválida |
| B21 #1 | Registrar un `codiQrId` descubierto por `record_issued_qr` | No aplica: la consulta es por un id que el intento ya tiene; los intentos sin id son `not_queryable` |
| B21 #2 | Resolver por consulta el caso `duplicate_provider_id` | Cumplido para el QR adoptado (es el `provider_request_id` del intento); el QR distinto solo quedó en el log y no se puede consultar |
| B21 #3 | Usar `move()` | Cumplido: el único cambio de estado es `cover_sale` → `move` |

### Riesgo externo no probado

TC03 supone que el `id` de la transacción en la consulta es el mismo `transactionId` del webhook, y que `amount` significa lo mismo en ambos (la consulta lo documenta como importe total, con un desglose que puede incluir comisión al pagador). Si en tráfico real difieren, nada se cuenta dos veces, pero el pago irá a revisión (`conflicting_transfer` o `amount_mismatch`). Queda pendiente de la integración real (B35).

## Trazabilidad UC → AC → TC → test

| UC | AC | TC | Test real | Resultado |
| --- | --- | --- | --- | --- |
| B22-UC01 | B22-AC01 | B22-TC01 | `tests/sales/test_qr_reconciliation.py::test_evidence_on_a_later_page_confirms_the_sale_once` (página 1 con `PENDING` y `nextToken`, página 2 con el pago: cobro `paid`, 1 transferencia con la cuenta enmascarada; repetir no suma); `…::test_a_confirmed_reconciliation_closes_its_pending_job[timeout\|duplicate_provider_id]`; `…::test_a_different_amount_found_by_query_goes_to_review`; `…::test_the_command_reconciles_one_attempt`; `tests/payments/test_pey_query.py::test_follows_next_tokens_and_returns_only_paid_transactions`; `…::test_the_official_example_page_is_understood` | PASS |
| B22-UC02 | B22-AC02 | B22-TC02 | `test_qr_reconciliation.py::test_no_evidence_keeps_the_payment_unconfirmed[empty\|only-pending]`; `…::test_an_uncertain_answer_keeps_a_reconciling_attempt_waiting[server-error\|rate-limited\|not-found\|timeout]`; `…::test_an_attempt_without_a_qr_id_cannot_be_queried`; `test_pey_query.py::test_an_empty_answer_is_no_evidence_rather_than_a_rejection`; `…::test_provider_problems_leave_the_payment_uncertain`; `…::test_network_failures_leave_the_payment_uncertain`; `…::test_the_query_is_bounded_in_pages`; `…::test_unusable_amounts_or_dates_are_kept_as_incomplete_payments` | PASS |
| B22-UC03 | B22-AC03 | B22-TC03 | `test_qr_reconciliation.py::test_a_webhook_then_a_query_for_the_same_transfer_count_once`; `…::test_a_query_then_a_webhook_for_the_same_transfer_count_once` (el webhook queda `duplicate`) | PASS |

## TDD

| Comportamiento | Red | Green |
| --- | --- | --- |
| Consulta y conciliación | Los tests se escribieron antes del código y fallaban en la colección: `ImportError: cannot import name 'MAX_QUERY_PAGES' from 'tappy.payments.pey'` y `ModuleNotFoundError: No module named 'tappy.sales.reconciliation'`. Primer Green: 25 de 26 pasan; el que falló (`assert (review, 0) == (review, 1)`) tenía mal la expectativa: una transferencia de otro importe es `review`, no `applied` (B20), y se corrigió el test | `qr_payments`, `reconcile_attempt`, `reconcile` |
| Paginación | Mutación que ignora `nextToken`: fallan 3 (`follows_next_tokens`, `bounded_in_pages`, `later_page_confirms`) | Bucle acotado con `nextToken` |
| Ausencia no es rechazo | Mutación que marca `failed` sin evidencia: fallan 3 (`no_evidence[empty\|only-pending]`, `command_reconciles`) | Estado intacto sin evidencia |
| Mismo pago por webhook y consulta | Mutación con otro entorno en la evidencia de consulta: falla `webhook_then_query` | Entorno de `TAPPY_ENVIRONMENT` en ambos caminos |

## Aplicabilidad por superficie

| Superficie | Aplica | Justificación |
| --- | --- | --- |
| Comandos | Sí | `reconcile <attempt-id>` nuevo |
| API | Sí, sin cambio de contrato | `GET /sales/{id}` refleja la confirmación |
| Panel | No aplica | Sin vistas en este alcance |

## B22-VC01 — Resultado inicial de la conciliación

Proceso real `python -m tappy` con `TAPPY_PAYMENT_PROVIDER=pey` y un secreto de webhooks generado al vuelo. El pey falso local atiende `POST /codi/qr` y `GET /transaction/codi/qr/{id}` con páginas configuradas por QR. Valores sintéticos (cobros de 300.00). Revisión `3c72677` (idéntico sobre `0d47d1b`).

| A antes (QR pendiente, sin webhook) | 200 | `{"status": "open", "confirmed_amount_cents": 0, "attempt": "pending", "transfers": [], "exceptions": []}` |

**A: evidencia propia en la segunda página**

```
$ python -m tappy.sales reconcile 3b8bd1ec-cfc7-4751-89c8-dc264dca3071
attempt: 3b8bd1ec-cfc7-4751-89c8-dc264dca3071
sale reference: D2TJ7VWPD9
qr: QRVC22AAAA
payments found: 1
applied: 1, duplicates: 0, in review: 0
attempt status: paid
sale status: paid
result: payment confirmed
(exit 0)
```

| A después | 200 | `{"status": "paid", "confirmed_amount_cents": 30000, "attempt": "paid", "transfers": ["TX-VC22-A"], "exceptions": []}` |

**A: repetir la conciliación**

```
$ python -m tappy.sales reconcile 3b8bd1ec-cfc7-4751-89c8-dc264dca3071
attempt: 3b8bd1ec-cfc7-4751-89c8-dc264dca3071
sale reference: D2TJ7VWPD9
qr: QRVC22AAAA
payments found: 1
applied: 0, duplicates: 1, in review: 0
attempt status: paid
sale status: paid
result: payment confirmed
(exit 0)
```

| A tras repetir | 200 | `{"status": "paid", "confirmed_amount_cents": 30000, "attempt": "paid", "transfers": ["TX-VC22-A"], "exceptions": []}` |

**B: consulta sin transacciones**

```
$ python -m tappy.sales reconcile 14779796-326c-47b8-a52d-83d7a45a8c05
attempt: 14779796-326c-47b8-a52d-83d7a45a8c05
sale reference: BRHXB0JCWN
qr: QRVC22BBBB
payments found: 0
applied: 0, duplicates: 0, in review: 0
attempt status: pending
sale status: open
result: no payment evidence found; the payment stays unconfirmed
(exit 0)
```

| B después | 200 | `{"status": "open", "confirmed_amount_cents": 0, "attempt": "pending", "transfers": [], "exceptions": []}` |

**C: error temporal del proveedor**

```
$ python -m tappy.sales reconcile 5190610c-709d-4d13-b033-900388d06350
attempt: 5190610c-709d-4d13-b033-900388d06350
sale reference: GYQ906A1BC
qr: QRVC22CCCC
payments found: 0
applied: 0, duplicates: 0, in review: 0
attempt status: pending
sale status: open
result: provider query failed (server_error); the payment stays unconfirmed
(exit 0)
```

| C después | 200 | `{"status": "open", "confirmed_amount_cents": 0, "attempt": "pending", "transfers": [], "exceptions": []}` |

Webhook `codi.qr.payment_received` TX-VC22-D → 204

| D tras el webhook | 200 | `{"status": "paid", "confirmed_amount_cents": 30000, "attempt": "paid", "transfers": ["TX-VC22-D"], "exceptions": []}` |

**D: la consulta devuelve la misma transferencia**

```
$ python -m tappy.sales reconcile 112fe50e-4a73-4887-aeaa-5b568ff76b7b
attempt: 112fe50e-4a73-4887-aeaa-5b568ff76b7b
sale reference: CAVWF3P8XS
qr: QRVC22DDDD
payments found: 1
applied: 0, duplicates: 1, in review: 0
attempt status: paid
sale status: paid
result: payment confirmed
(exit 0)
```

| D después | 200 | `{"status": "paid", "confirmed_amount_cents": 30000, "attempt": "paid", "transfers": ["TX-VC22-D"], "exceptions": []}` |

transfers [('TX-VC22-A', 30000), ('TX-VC22-D', 30000)]
events [('msg_vc22_d', 'applied')]
exceptions 0
pey requests:
{"get": "/transaction/codi/qr/QRVC22AAAA", "nextToken": "first", "status": 200}
{"get": "/transaction/codi/qr/QRVC22AAAA", "nextToken": "page-2", "status": 200}
{"get": "/transaction/codi/qr/QRVC22AAAA", "nextToken": "first", "status": 200}
{"get": "/transaction/codi/qr/QRVC22AAAA", "nextToken": "page-2", "status": 200}
{"get": "/transaction/codi/qr/QRVC22BBBB", "nextToken": "first", "status": 200}
{"get": "/transaction/codi/qr/QRVC22CCCC", "nextToken": "first", "status": 500}
{"get": "/transaction/codi/qr/QRVC22DDDD", "nextToken": "first", "status": 200}

Los datos se eliminaron al terminar. Validación contra el contrato y los AC:

- A (TC01): sin webhook, la evidencia está en la segunda página (2 peticiones con `nextToken`): se confirma una vez y repetir solo cuenta un duplicado.
- B y C (TC02): sin transacciones o con un 500, el intento sigue `pending` y el cobro `open`, sin incidencias.
- D (TC03): el webhook confirma y la consulta devuelve la misma transferencia: duplicado, una sola transferencia y el evento sigue `applied`.

Estado VC01: **PASS**.

## Checks

`uv run python -m quality.check` sobre `3c72677`, con `.env` exportado: PASS en todos los pasos.

- format, lint y types (mypy strict).
- hygiene.
- migrations (sin migraciones nuevas) + `alembic check`.
- tests: 439 passed, Postgres real aislado.
- api: 16 contratos sin diferencias.
- evidence: B01–B21 APPROVED.

## Supresiones

Sin supresiones nuevas.

## Umbral

AC PASS / AC aplicables = 3/3 = **100%**.

## Review Standards/Spec

| Ronda | Revisión | Standards | Spec | Hallazgos |
| --- | --- | --- | --- | --- |
| 1 | `0d47d1b` | APPROVE | APPROVE | Sin violaciones ni defectos financieros. Notas aplicadas en `3c72677`: mapa explícito de problemas de red, `qr_payments` sin capa intermedia, una sola lectura del intento por informe y cierre de trabajos en SQL, nombres uniformes de argumentos no usados, `except ValueError`, test del trabajo `duplicate_provider_id`. Decisión registrada: código de salida 0 en resultados inciertos (ver Diseño). Riesgo externo registrado: equivalencia de `id`/`amount` entre consulta y webhook |

Hallazgos pendientes: 0.
