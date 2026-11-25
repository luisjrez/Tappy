# Evidencia — B19 Deduplicar eventos y transferencias

Ticket: [#27](https://github.com/luisjrez/Tappy/issues/27) · Historia: [H5 #5](https://github.com/luisjrez/Tappy/issues/5) · Protocolo: [TICKET_QUALITY_PROTOCOL](../planning/TICKET_QUALITY_PROTOCOL.md) · Manifiesto: [B19-dedupe-evidence.toml](B19-dedupe-evidence.toml)

> Verificado con eventos sintéticos con la forma oficial de pey, firmados localmente, y con el adaptador pey contra un pey falso local. **Sin webhooks ni pagos reales** (no demuestra integración bancaria real; B35).

## Revisiones y escenario

- Ticket, UC/AC/TC y comprobación: B19-UC01–UC03, B19-AC01–AC03, B19-TC01–TC03, B19-VC01. Incluye los arrastres de B17 y B18 en [#27](https://github.com/luisjrez/Tappy/issues/27) (mismo id con otro contenido se confirmaba y descartaba; `transactionId` repetido se marcaba `unmatched`).
- Modalidad: **antes/después** del comportamiento ante duplicados (antes: variante de contenido descartada sin rastro y segundo evento de una transferencia `unmatched`; después: variante conservada y señalada, segundo evento `duplicate`) y **resultado inicial** para el comando `event-conflicts`. Sin cambios de contrato de la API (las respuestas del webhook siguen siendo `204`; `SaleResponse` no cambia).
- Cambio esperado en un test anterior: el evento insertado directamente por SQL en el test de B18 incluye `environment`.
- Base: rama B18 (PR #74), stack #68. Revisión evaluada: candidato `085acb6`.
- Entorno: macOS, Colima + Compose (Postgres 18), Python 3.14.8. Fecha: 2026-11-24 (UTC 2026-11-25). Ejecutor: sesión local de desarrollo del autor del PR.

## Diseño

- Unicidad por proveedor, **entorno** e id (Green): `webhook_events` y `transactions` ganan `environment` (`TAPPY_ENVIRONMENT`; las filas previas se rellenan con `unspecified`) y sus restricciones únicas pasan a `(provider, environment, provider_event_id)` y `(provider, environment, provider_transaction_id)` (migración `0015`).
- Política de duplicación concentrada en persistencia/dominio (Refactor):
  - `store_event` devuelve `new`, `repeated` o `conflict`: mismo id y mismo digest → `repeated` (sin otro registro ni reproceso); mismo id con **otro digest** → el original no se toca y la variante se guarda en `webhook_event_conflicts` (único por evento y digest, así que reenvíos de la misma variante no se acumulan). Ambos se confirman con `204` para que el proveedor no reintente; solo un evento nuevo se aplica.
  - `apply_evidence` devuelve `EvidenceOutcome` (`applied`, `duplicate`, `unmatched`): tras bloquear el intento, si la transferencia (proveedor, entorno, `transactionId`) ya existe para **ese** intento → `duplicate` sin efecto; si existe para otro intento → `unmatched` (incidencia en B20). El savepoint de B18 sigue como respaldo ante carreras.
- Concurrencia: el bloqueo del intento serializa evento y consulta para la misma transferencia; quien llega segundo ve la transferencia confirmada y queda `duplicate`. La consulta usa la misma operación `apply_evidence` (la conciliación por consulta llega en B22).
- Señalización: `python -m tappy.sales event-conflicts` lista cada variante (id, proveedor, entorno, digests y recepción). `process-events` informa también los duplicados. El estado de evento `duplicate` se añade al check de la base.

## Trazabilidad UC → AC → TC → test

| UC | AC | TC | Test real | Resultado |
| --- | --- | --- | --- | --- |
| B19-UC01 | B19-AC01 | B19-TC01 | `test_redelivering_the_same_event_keeps_one_transfer` (E1 dos veces: un evento, una transferencia, total 30000); `test_another_event_for_the_same_transfer_is_recognised_as_duplicate` (E2 para T1 → `duplicate`); `test_reprocessing_never_adds_a_second_effect` | PASS |
| B19-UC02 | B19-AC02 | B19-TC02 | `test_same_event_id_with_other_content_is_flagged_and_the_original_kept` (payload original intacto, variante guardada, total y transferencias sin cambio, listado por el comando); `test_repeated_conflicting_variants_are_kept_once`; `test_event_ids_are_unique_per_provider_and_environment` | PASS |
| B19-UC03 | B19-AC03 | B19-TC03 | `test_concurrent_event_and_query_evidence_for_one_transfer_count_once` (una transacción aplica la evidencia por consulta sin confirmar; el webhook E2 queda bloqueado —`pg_stat_activity`— y tras el commit es `duplicate`; repetir la consulta → `duplicate`; una transferencia, total 30000) | PASS |

## TDD

| Comportamiento | Red | Green |
| --- | --- | --- |
| Primera ejecución | Colección fallida: `ImportError` de `EvidenceOutcome` (no es Red de comportamiento; Red por caso abajo) | — |
| TC01 duplicado reconocido | Mutación sin reconocer la transferencia ya registrada: `assert 'unmatched' == 'duplicate'` | `recorded_transfer` tras bloquear el intento |
| TC02 conflicto conservado | Mutación sin guardar la variante: `NoResultFound` (no existe la fila en `webhook_event_conflicts`) | `store_event` con `StoreOutcome.CONFLICT` |
| TC03 concurrencia | Mutación sin bloquear el intento: `assert 'unmatched' == 'duplicate'` (el segundo no ve la transferencia y no la reconoce) | `FOR UPDATE` del intento antes de comprobar |

## B19-VC01 — Antes/después de duplicados y conflicto

Proceso real `python -m tappy` sobre `085acb6` con `TAPPY_PAYMENT_PROVIDER=pey` (pey falso local para el QR) y secreto de webhooks generado; entorno `local`. Valores sintéticos.

| Paso | Status | Resultado |
| --- | --- | --- |
| E1 para T1 | 204 | `(sin cuerpo)` |
| Antes de los duplicados: `GET /sales/{A}` | 200 | `status=paid, confirmed_amount_cents=30000, transfers=[{"provider_transaction_id": "TX-VC01-T1", "amount_cents": 30000, "occurred_at": "2026-11-18T11:06:40Z", "received_at": "2026-11-25T01:22:00.665229Z", "beneficiary_name": "Tienda Demo A SA de CV", "masked_account": "**************6782"}]` |
| E1 reentregado (mismo id y contenido) | 204 | `(sin cuerpo)` |
| E2 para la misma transferencia T1 | 204 | `(sin cuerpo)` |
| E1 con otro contenido (importe 999.00, otra transacción) | 204 | `(sin cuerpo)` |
| Después: `GET /sales/{A}` | 200 | `status=paid, confirmed_amount_cents=30000, transfers=[{"provider_transaction_id": "TX-VC01-T1", "amount_cents": 30000, "occurred_at": "2026-11-18T11:06:40Z", "received_at": "2026-11-25T01:22:00.665229Z", "beneficiary_name": "Tienda Demo A SA de CV", "masked_account": "**************6782"}]` |

Señalización y reproceso:

```
$ python -m tappy.sales event-conflicts
event: msg_vc01_e1 (pey, local)
problem: conflicting content for an event id already stored
original digest: 2438ac2582a3d73ba1a000ddcb0c32522c5f650b85c2cdc800ae11b012c67980
variant digest: 39ea5e16550a375e56ef7a950eaeb0ad4afe3b8f7a504eb08baad73a68c50fe0
variant received at: 2026-11-25T01:22:00.689272+00:00
$ # E2 devuelto a received para reprocesarlo
$ python -m tappy.sales process-events
0 events applied, 0 unmatched, 1 duplicate, 0 failed
```

Estado final: `events [('msg_vc01_e1', 'local', 'applied'), ('msg_vc01_e2', 'local', 'duplicate')]`; `conflicts 1 transfers (1, 30000)`. **Antes** (B18): la variante de E1 se habría confirmado y descartado sin rastro, y E2 habría quedado `unmatched`. Datos eliminados al terminar (esquema de desarrollo recreado). Estado VC01: **PASS**.

## Checks

`uv run python -m quality.check` sobre `085acb6` (con `.env` exportado): PASS format, lint, types (mypy strict), hygiene, migrations (upgrade/downgrade/upgrade + `alembic check`), tests (379 passed, Postgres real aislado), api (16 contratos sin diferencias); `evidence` B01–B18 APPROVED.

## Supresiones

Sin supresiones nuevas.

## Umbral

AC PASS / AC aplicables = 3/3 = **100%**.

## Review Standards/Spec

Pendiente.
