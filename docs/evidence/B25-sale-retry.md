# Evidencia — B25 Reintentar la misma venta con control

Ticket: [#33](https://github.com/luisjrez/Tappy/issues/33) · Historia: [H5 #5](https://github.com/luisjrez/Tappy/issues/5) · Protocolo: [TICKET_QUALITY_PROTOCOL](../planning/TICKET_QUALITY_PROTOCOL.md) · Manifiesto: [B25-sale-retry.toml](B25-sale-retry.toml)

> Verificado con un pey falso local. **No hubo QR, pagos ni consultas reales.** Un reintento nunca crea otra venta ni promete que el QR anterior dejó de poder pagarse.

## Revisiones y escenario

- **Trazabilidad:** B25-UC01–UC03, B25-AC01–AC03, B25-TC01–TC03 y B25-VC01.
- **Modalidad: antes/después.**
  - **Antes (B24):** un intento `expired` permitía otro de inmediato, sin comprobar el vencido, sin vínculo con el intento anterior y sin advertencia.
  - **Después:**
    - El reintento exige que el anterior esté `failed`, o `expired` y comprobado.
    - El intento nuevo queda vinculado al anterior y advierte de un posible pago tardío.
    - `AttemptResponse` gana `verified_at`, `previous_attempt_id` y `late_payment_possible`.
- **Cambios esperados en tests anteriores:**
  - Cuerpos exactos de B13 y B14: incluyen los campos nuevos.
  - `test_finished_attempts_allow_a_new_reservation[expired]` (B13): marca comprobado el intento vencido.
  - Lote de vencimiento de B24: ahora también comprueba el intento vencido y necesita una página de respuesta.
- **Base y revisiones:**
  - Base: rama B24 `6e87182` ([PR #80](https://github.com/luisjrez/Tappy/pull/80)), stack #68.
  - Candidato: `78541a2` + `348ec4b`. El segundo se descubrió en la VC01: un vencido ya comprobado seguía sugiriendo `verify_before_retry`.
  - Correcciones de la review: `99e6787`, revisión final. La VC01 se repitió sobre ella.
- **Entorno:** macOS, Colima + Compose (Postgres 18), Python 3.14.8. Fecha: 2026-11-25 (UTC). Ejecutor: sesión local de desarrollo del autor del PR.

## Diseño

### Reintento = la misma reserva

`POST /sales/{id}/attempts` reutiliza la reserva, la clave idempotente y el lock de la venta del primer intento («Reusar reserva e idempotencia del primer intento»). `attempt_to_retry` decide bajo el lock de la venta:

| Situación | Respuesta |
| --- | --- |
| Hay un intento `creating`, `pending` o `reconciling` | `409` «active payment attempt»: hay que recuperarlo o comprobarlo antes |
| El último intento está `expired` sin `verified_at` | `409` «verify it before creating another» |
| El último intento está `failed`, o `expired` y comprobado | Se crea el nuevo, con `previous_attempt_id` apuntando a ese intento |

- Migración `0020`: añade `previous_attempt_id` con FK y `UNIQUE`. Cada intento admite un solo sucesor, así que dos reintentos no pueden colgar del mismo anterior.
- El índice parcial de intento activo único sigue vigente.
- La venta, su importe y su referencia no cambian.

### Comprobación del vencido

- Al vencer un intento se encola un trabajo `expired` con `enqueue_job`, compartido con la conciliación de creaciones inciertas.
- `run-jobs` (o `reconcile`) consulta a pey:
  - **Sin pago:** el intento recibe `verified_at` y el trabajo queda `done` (`verified unpaid`).
  - **Con pago:** confirma la venta. Es un pago tardío, `expired → paid`.
  - **Respuesta incierta:** se reprograma y el reintento sigue bloqueado.
- Solo cuenta una consulta hecha **cuando el intento ya estaba vencido**: `QueryTarget.expired` se captura al leer el intento antes de llamar a pey. `verified_at` conserva la primera marca.
- Riesgo registrado: la comprobación corre en cuanto vence el intento, así que un pago hecho en los últimos segundos podría no aparecer todavía. La advertencia de pago tardío cubre ese caso, y B26 registra el pago si llega.

### Advertencia de pago tardío

- `late_payment_possible` es `true` si **cualquier** intento anterior de la cadena emitió un QR, porque ese QR puede recibir un pago tardío (PRODUCT_BASE).
- Aparece en la respuesta del reintento y en `GET /sales/{id}`.
- Un intento `expired` comprobado sugiere `new_attempt`; uno sin comprobar, `verify_before_retry`.

### Arrastre de B24

| Punto | Estado |
| --- | --- |
| 1. Exigir la comprobación del vencido | Cumplido (`UnverifiedAttemptError`) |
| 2. `reconciling` sigue activo | Cumplido: bloquea con «active payment attempt» |
| 3. Repetición idempotente con la vista guardada | No aplica: cada reintento usa una clave nueva y repetirla devuelve el mismo intento |
| 4. Vencimiento con el reloj del servidor | Cumplido: el trabajo de comprobación usa el reloj inyectado |

## Trazabilidad UC → AC → TC → test

Todos los tests están en `tests/sales/test_attempt_retries.py`.

| UC | AC | TC | Test real | Resultado |
| --- | --- | --- | --- | --- |
| B25-UC01 | B25-AC01 | B25-TC01 | `test_a_verified_expired_attempt_allows_a_linked_retry_on_the_same_sale` (misma venta, importe y referencia; vínculo; QR nuevo; advertencia; vencido con `new_attempt`; 1 venta); `test_repeating_a_retry_returns_the_same_attempt`; `test_a_failed_attempt_allows_a_retry_without_a_late_payment_warning`; `test_the_late_payment_warning_covers_every_earlier_qr`; `test_a_late_payment_found_by_the_verification_needs_no_retry` | PASS |
| B25-UC02 | B25-AC02 | B25-TC02 | `test_an_active_or_uncertain_attempt_blocks_a_retry[creating\|pending\|reconciling]`; `test_an_expired_attempt_needs_verification_before_a_retry`; `test_an_uncertain_verification_keeps_the_retry_blocked`; `test_a_query_made_before_the_expiration_never_verifies_it` | PASS |
| B25-UC03 | B25-AC03 | B25-TC03 | `test_concurrent_retries_leave_a_single_new_attempt` (carrera determinista con `wait_until_blocked_on_a_lock`: un 201, un 409, un solo intento nuevo vinculado y 1 venta) | PASS |

## TDD

**Red de comportamiento:** los tests se escribieron antes del código y se corrieron contra la rama sin implementación. Fallan 6 de 10. Los 4 que pasaban caracterizan reglas que ya existían: un intento activo bloquea otro y la repetición idempotente devuelve el mismo intento.

```
E       KeyError: 'previous_attempt_id'
E       assert <HTTPStatus.CREATED: 201> == <HTTPStatus.CONFLICT: 409>
E       assert <HTTPStatus.CREATED: 201> == <HTTPStatus.CONFLICT: 409>
_____ test_a_failed_attempt_allows_a_retry_without_a_late_payment_warning ______
    def test_a_failed_attempt_allows_a_retry_without_a_late_payment_warning(
            "UPDATE payment_attempts SET status = 'failed', provider_request_id = NULL, "
E       KeyError: 'previous_attempt_id'
E       assert (1, 0) == (1, 1)
E       AttributeError: 'AttemptView' object has no attribute 'previous_attempt_id'
FAILED tests/sales/test_attempt_retries.py::test_a_verified_expired_attempt_allows_a_linked_retry_on_the_same_sale
FAILED tests/sales/test_attempt_retries.py::test_an_expired_attempt_needs_verification_before_a_retry
FAILED tests/sales/test_attempt_retries.py::test_an_uncertain_verification_keeps_the_retry_blocked
FAILED tests/sales/test_attempt_retries.py::test_a_failed_attempt_allows_a_retry_without_a_late_payment_warning
FAILED tests/sales/test_attempt_retries.py::test_a_late_payment_found_by_the_verification_needs_no_retry
FAILED tests/sales/test_attempt_retries.py::test_concurrent_retries_leave_a_single_new_attempt
6 failed, 4 passed in 4.85s
```

| Comportamiento | Red | Green |
| --- | --- | --- |
| Reintento vinculado y comprobación | Ver arriba | `attempt_to_retry`, `previous_attempt_id`, trabajo `expired`, `mark_verified`, resultado `verified` |
| Sugerencia tras comprobar | `assert 'verify_before_retry' == 'new_attempt'` (hallado en la VC01) | `next_action` con `new_attempt` para un vencido comprobado |
| Advertencia en toda la cadena (review) | `assert False is True` en `…covers_every_earlier_qr` | Se recorre la cadena de intentos anteriores |
| Comprobación solo tras el vencimiento (review) | Falla `…query_made_before_the_expiration…`: la marca se ponía con una consulta previa al vencimiento | `QueryTarget.expired` |
| Mutaciones | Sin exigir la comprobación: fallan 2. Sin encolar la comprobación: fallan 4. Sin el vínculo: fallan 3 | — |

## Aplicabilidad por superficie

| Superficie | Aplica | Justificación |
| --- | --- | --- |
| API | Sí | Reglas del reintento, campos nuevos y `409` |
| Comandos | Sí | `run-jobs` y `reconcile` informan `verified unpaid` |
| Panel | No aplica | Sin vistas en este alcance |

## B25-VC01 — Antes/después del reintento

Proceso real `python -m tappy` con `TAPPY_PAYMENT_PROVIDER=pey` y `TAPPY_QR_EXPIRATION_SECONDS=360`. El pey falso local atiende la creación y la consulta. Para no esperar la ventana real, `expires_at` se adelanta por SQL. La comprobación la hace el lote real `run-jobs`. Valores sintéticos.

### Antes (B24 `6e87182`)

**Venta 1: reintento tras un intento vencido (TC01, TC02)**

- Primer intento QR → 201 `{"status": "pending", "provider_request_id": "QRVC25A001", "next_action": "show_qr"}`
- (se adelanta `expires_at` a «ahora − 1 s» por SQL para no esperar la ventana de 360 s)
- Seguimiento vencido → 200 `{"sale_id": "d9acca29…", "reference": "B6DZBY6TN7", "amount_cents": 30000, "status": "open", "attempts": [{"status": "expired", "provider_request_id": "QRVC25A001", "next_action": "verify_before_retry"}]}`
- Reintento sin comprobar el vencido → 201 `{"status": "pending", "provider_request_id": "QRVC25A002", "next_action": "show_qr"}`
- Lote programado: comprobación del vencido (pey responde sin transacciones) (`run-jobs`, exit 0): `pending attempts expired: 0 | jobs claimed: 0 | confirmed: 0, in review: 0, rescheduled: 0, exhausted: 0, lease lost: 0, failed: 0`
- Seguimiento tras la comprobación → 200 `{"sale_id": "d9acca29…", "reference": "B6DZBY6TN7", "amount_cents": 30000, "status": "open", "attempts": [{"status": "expired", "provider_request_id": "QRVC25A001", "next_action": "verify_before_retry"}, {"status": "pending", "provider_request_id": "QRVC25A002", "next_action": "show_qr"}]}`
- Reintento tras la comprobación → 409 `{"detail": "The sale already has an active payment attempt"}`
- Venta tras el reintento → 200 `{"sale_id": "d9acca29…", "reference": "B6DZBY6TN7", "amount_cents": 30000, "status": "open", "attempts": [{"status": "expired", "provider_request_id": "QRVC25A001", "next_action": "verify_before_retry"}, {"status": "pending", "provider_request_id": "QRVC25A002", "next_action": "show_qr"}]}`
- Otro reintento con un intento activo → 409 `{"detail": "The sale already has an active payment attempt"}`

**Venta 2: dos reintentos simultáneos (TC03)**

- Primer intento QR → 201 `{"status": "pending", "provider_request_id": "QRVC25B001", "next_action": "show_qr"}`
- Lote programado: comprobación del vencido (`run-jobs`, exit 0): `pending attempts expired: 0 | jobs claimed: 0 | confirmed: 0, in review: 0, rescheduled: 0, exhausted: 0, lease lost: 0, failed: 0`
- Dos reintentos simultáneos → `[201, 409]`
- Venta 2 tras los reintentos → 200 `{"sale_id": "084dae62…", "reference": "6ZXQ5ATEYC", "amount_cents": 30000, "status": "open", "attempts": [{"status": "expired", "provider_request_id": "QRVC25B001", "next_action": "verify_before_retry"}, {"status": "pending", "provider_request_id": "QRVC25B002", "next_action": "show_qr"}]}`

Ventas en la base: 2

Consultas a pey: (ninguna)

### Después (revisión final `99e6787`)

**Venta 1: reintento tras un intento vencido (TC01, TC02)**

- Primer intento QR → 201 `{"status": "pending", "provider_request_id": "QRVC25A001", "previous_attempt_id": null, "late_payment_possible": false, "verified_at": null, "next_action": "show_qr"}`
- (se adelanta `expires_at` a «ahora − 1 s» por SQL para no esperar la ventana de 360 s)
- Seguimiento vencido → 200 `{"sale_id": "914df44b…", "reference": "FBWXVEF0JX", "amount_cents": 30000, "status": "open", "attempts": [{"status": "expired", "provider_request_id": "QRVC25A001", "previous_attempt_id": null, "late_payment_possible": false, "verified_at": null, "next_action": "verify_before_retry"}]}`
- Reintento sin comprobar el vencido → 409 `{"detail": "The previous attempt expired; verify it before creating another"}`
- Lote programado: comprobación del vencido (pey responde sin transacciones) (`run-jobs`, exit 0): `pending attempts expired: 0 | jobs claimed: 1 | confirmed: 0, verified unpaid: 1, in review: 0, rescheduled: 0, exhausted: 0, lease lost: 0, failed: 0`
- Seguimiento tras la comprobación → 200 `{"sale_id": "914df44b…", "reference": "FBWXVEF0JX", "amount_cents": 30000, "status": "open", "attempts": [{"status": "expired", "provider_request_id": "QRVC25A001", "previous_attempt_id": null, "late_payment_possible": false, "verified_at": "2026-11-25T13:06:15.471488Z", "next_action": "new_attempt"}]}`
- Reintento tras la comprobación → 201 `{"status": "pending", "provider_request_id": "QRVC25A003", "previous_attempt_id": "315b3bbf…", "late_payment_possible": true, "verified_at": null, "next_action": "show_qr"}`
- Venta tras el reintento → 200 `{"sale_id": "914df44b…", "reference": "FBWXVEF0JX", "amount_cents": 30000, "status": "open", "attempts": [{"status": "expired", "provider_request_id": "QRVC25A001", "previous_attempt_id": null, "late_payment_possible": false, "verified_at": "2026-11-25T13:06:15.471488Z", "next_action": "new_attempt"}, {"status": "pending", "provider_request_id": "QRVC25A003", "previous_attempt_id": "315b3bbf…", "late_payment_possible": true, "verified_at": null, "next_action": "show_qr"}]}`
- Otro reintento con un intento activo → 409 `{"detail": "The sale already has an active payment attempt"}`

**Venta 2: dos reintentos simultáneos (TC03)**

- Primer intento QR → 201 `{"status": "pending", "provider_request_id": "QRVC25B001", "previous_attempt_id": null, "late_payment_possible": false, "verified_at": null, "next_action": "show_qr"}`
- Lote programado: comprobación del vencido (`run-jobs`, exit 0): `pending attempts expired: 0 | jobs claimed: 1 | confirmed: 0, verified unpaid: 1, in review: 0, rescheduled: 0, exhausted: 0, lease lost: 0, failed: 0`
- Dos reintentos simultáneos → `[201, 409]`
- Venta 2 tras los reintentos → 200 `{"sale_id": "c37e0153…", "reference": "CPCHH7ZDGE", "amount_cents": 30000, "status": "open", "attempts": [{"status": "expired", "provider_request_id": "QRVC25B001", "previous_attempt_id": null, "late_payment_possible": false, "verified_at": "2026-11-25T13:06:16.140078Z", "next_action": "new_attempt"}, {"status": "pending", "provider_request_id": "QRVC25B002", "previous_attempt_id": "cb96e5e4…", "late_payment_possible": true, "verified_at": null, "next_action": "show_qr"}]}`

Ventas en la base: 2

Consultas a pey:
{"get": "/transaction/codi/qr/QRVC25A001", "nextToken": "first", "status": 200}
{"get": "/transaction/codi/qr/QRVC25B001", "nextToken": "first", "status": 200}

Validación:

- **TC01:** tras la comprobación (`verified unpaid: 1`), el reintento crea un intento nuevo en la misma venta. Su QR es `QRVC25A003` porque el script fija el id del pey falso en cada paso; el reintento rechazado con `409` (paso `A002`) no llamó a pey, como muestra el registro de consultas. Importe 30000 y referencia sin cambios, QR nuevo, `previous_attempt_id` al vencido y `late_payment_possible: true`.
- **TC02:**
  - Sin comprobar el vencido: `409`.
  - Con un intento activo: `409`.
- **TC03:** dos reintentos simultáneos dan `[201, 409]` y un solo intento nuevo. Las 2 ventas de la base son las dos del escenario: ninguna adicional.
- **Antes:** el reintento sobre un vencido sin comprobar se aceptaba (201), sin vínculo ni advertencia, y no había comprobación.

Los datos se eliminaron al terminar. Estado VC01: **PASS**.

### Diferencias y decisión

| TC/AC | Antes (B24) | Después | Clasificación | Decisión |
| --- | --- | --- | --- | --- |
| TC01 | Reintento inmediato, sin vínculo ni advertencia | Reintento tras comprobar, vinculado y con advertencia | Comportamiento | Aceptada |
| TC02 | Vencido sin comprobar: 201 | `409` hasta comprobarlo | Comportamiento | Aceptada |
| TC03 | Un solo intento nuevo | Igual, y además con vínculo único | Sin cambio en el resultado | Aceptada |
| `AttemptResponse` | — | `verified_at`, `previous_attempt_id`, `late_payment_possible` | Aditiva | Aceptada |

## Checks

`uv run python -m quality.check` sobre `99e6787`, con `.env` exportado: PASS en todos los pasos.

- format, lint y types (mypy strict).
- hygiene.
- migrations: upgrade/downgrade/upgrade de `0020` + `alembic check`.
- tests: 478 passed, Postgres real aislado.
- api: 16 contratos sin diferencias.
- evidence: B01–B24 APPROVED.

## Supresiones

Sin supresiones nuevas.

## Umbral

AC PASS / AC aplicables = 3/3 = **100%**.

## Review Standards/Spec

| Ronda | Revisión | Standards | Spec | Hallazgos |
| --- | --- | --- | --- | --- |
| 1 | `78541a2` + `348ec4b` | APPROVE | REQUEST_CHANGES | Ver detalle debajo de la tabla |
| 2 | `99e6787` + `473dc18` | APPROVE | APPROVE | Ambos hallazgos corregidos y probados. Notas de evidencia aplicadas: «ninguna» en las consultas vacías y una explicación de los ids de QR del escenario |

Detalle de la ronda 1. Spec pidió dos cambios, ambos corregidos en `99e6787` con Red/Green:

- La advertencia solo miraba el intento anterior inmediato.
- Una consulta previa al vencimiento podía marcar el intento como comprobado.

Notas de Standards aplicadas:

- Renombrado a `attempt_to_retry`.
- `enqueue_job` compartido.
- Un solo informe por conciliación.
- `verified_at` conserva la primera marca.
- El test de B13 solo marca comprobados los vencidos.

Riesgo registrado: el margen de los últimos segundos antes del vencimiento.

Hallazgos pendientes: 0.
