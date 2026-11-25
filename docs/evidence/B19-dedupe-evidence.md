# Evidencia — B19 Deduplicar eventos y transferencias

Ticket: [#27](https://github.com/luisjrez/Tappy/issues/27) · Historia: [H5 #5](https://github.com/luisjrez/Tappy/issues/5) · Protocolo: [TICKET_QUALITY_PROTOCOL](../planning/TICKET_QUALITY_PROTOCOL.md) · Manifiesto: [B19-dedupe-evidence.toml](B19-dedupe-evidence.toml)

> Verificado con eventos sintéticos con la forma oficial de pey, firmados localmente, y con el adaptador pey contra un pey falso local. **Sin webhooks ni pagos reales** (no demuestra integración bancaria real; B35).

## Revisiones y escenario

- Ticket, UC/AC/TC y comprobación: B19-UC01–UC03, B19-AC01–AC03, B19-TC01–TC03, B19-VC01. Incluye los arrastres de B17 y B18 en [#27](https://github.com/luisjrez/Tappy/issues/27) (mismo id con otro contenido se confirmaba y descartaba; `transactionId` repetido se marcaba `unmatched`).
- Modalidad: **antes/después** del comportamiento ante duplicados (antes: variante de contenido descartada sin rastro y segundo evento de una transferencia `unmatched`; después: variante conservada y señalada, segundo evento `duplicate`) y **resultado inicial** para el comando `event-conflicts`. Sin cambios de contrato de la API (las respuestas del webhook siguen siendo `204`; `SaleResponse` no cambia).
- Cambio esperado en un test anterior: el evento insertado directamente por SQL en el test de B18 incluye `environment`.
- Base: rama B18 (PR #74), stack #68. Revisiones: candidato `085acb6` → correcciones de review `8ff2289` (revisión final; VC01 repetida sobre ella).
- Entorno: macOS, Colima + Compose (Postgres 18), Python 3.14.8. Fecha: 2026-11-24 (UTC 2026-11-25). Ejecutor: sesión local de desarrollo del autor del PR.

## Diseño

- Unicidad por proveedor, **entorno** e id (Green): `webhook_events` y `transactions` ganan `environment` (`TAPPY_ENVIRONMENT`, ahora limitado a un identificador en minúsculas de hasta 32 caracteres para que no se divida la deduplicación por mayúsculas ni falle la inserción; las filas previas se rellenan con `unspecified`, de modo que un evento anterior a la migración que se reentregue después ya no se reconoce como el mismo —el estado `paid` del cobro sigue impidiendo un segundo efecto—) y sus restricciones únicas pasan a `(provider, environment, provider_event_id)` y `(provider, environment, provider_transaction_id)` (migración `0015`).
- Política de duplicación concentrada en persistencia/dominio (Refactor):
  - `store_event` devuelve `new`, `repeated` o `conflict`: mismo id y mismo digest → `repeated` (sin otro registro ni reproceso); mismo id con **otro digest** → el original no se toca y la variante se guarda en `webhook_event_conflicts` (único por evento y digest, así que reenvíos de la misma variante no se acumulan). Ambos se confirman con `204` para que el proveedor no reintente. Un evento nuevo, o uno repetido que sigue `received` (por ejemplo, tras una caída entre guardar y aplicar), se aplica en el momento; una variante en conflicto nunca.
  - `apply_evidence` devuelve `EvidenceOutcome` (`applied`, `duplicate`, `unmatched`): tras bloquear el intento, si la transferencia (proveedor, entorno, `transactionId`) ya existe para **ese** intento con el **mismo importe y la misma cuenta** → `duplicate` sin efecto; si difiere en algo o pertenece a otro intento → `unmatched`, para no ocultar la discrepancia (la incidencia es B20). El savepoint de B18 sigue como respaldo ante carreras.
- Concurrencia: el bloqueo del intento serializa evento y consulta para la misma transferencia; quien llega segundo ve la transferencia confirmada y queda `duplicate`. La consulta usa la misma operación `apply_evidence` (la conciliación por consulta llega en B22).
- El downgrade de `0015` se niega si hay variantes en conflicto o ids compartidos por varios entornos (no podría restaurar la unicidad anterior).
- Señalización: `python -m tappy.sales event-conflicts` lista cada variante (id, proveedor, entorno, digests y recepción). `process-events` informa también los duplicados. El estado de evento `duplicate` se añade al check de la base.

## Trazabilidad UC → AC → TC → test

| UC | AC | TC | Test real | Resultado |
| --- | --- | --- | --- | --- |
| B19-UC01 | B19-AC01 | B19-TC01 | `test_redelivering_the_same_event_keeps_one_transfer` (E1 dos veces: un evento, una transferencia, total 30000); `test_another_event_for_the_same_transfer_is_recognised_as_duplicate` (E2 para T1 → `duplicate`); `test_reprocessing_never_adds_a_second_effect`; `test_same_transaction_with_other_amount_is_not_hidden_as_duplicate`; `test_redelivering_an_event_still_waiting_applies_it` | PASS |
| B19-UC02 | B19-AC02 | B19-TC02 | `test_same_event_id_with_other_content_is_flagged_and_the_original_kept` (payload original intacto, variante guardada, total y transferencias sin cambio, listado por el comando); `test_repeated_conflicting_variants_are_kept_once`; `test_event_ids_are_unique_per_provider_and_environment`; `test_transfer_ids_are_unique_per_provider_and_environment`; `test_a_conflict_on_an_event_not_yet_applied_keeps_applying_the_original`; `test_environment_names_are_short_lowercase_identifiers` | PASS |
| B19-UC03 | B19-AC03 | B19-TC03 | `test_concurrent_event_and_query_evidence_for_one_transfer_count_once` (una transacción aplica la evidencia por consulta sin confirmar; el webhook E2 queda bloqueado —`pg_stat_activity`— y tras el commit es `duplicate`; repetir la consulta → `duplicate`; una transferencia, total 30000) | PASS |

## TDD

| Comportamiento | Red | Green |
| --- | --- | --- |
| Primera ejecución | Colección fallida: `ImportError` de `EvidenceOutcome`. Desviación del protocolo, declarada: los tests de los tres TC se escribieron juntos antes de implementar, en lugar de un TC cada vez; el Red de comportamiento de cada TC se obtuvo después con mutaciones dirigidas sobre el código ya escrito | — |
| TC01 duplicado reconocido | Mutación sin reconocer la transferencia ya registrada: `assert 'unmatched' == 'duplicate'` | `recorded_transfer` tras bloquear el intento |
| TC02 conflicto conservado | Mutación sin guardar la variante: `NoResultFound` (no existe la fila en `webhook_event_conflicts`) | `store_event` con `StoreOutcome.CONFLICT` |
| Duplicado con otros datos (review) | `assert 'duplicate' == 'unmatched'` (otro importe con el mismo `transactionId` se ocultaba como duplicado) | `same_transfer` compara intento, importe y cuenta |
| Reentrega de un evento atascado (review) | `assert 'received' == 'applied'` | Se aplica toda entrega que no sea conflicto |
| Nombre de entorno (review) | `Failed: DID NOT RAISE ValueError` para `Production`, 33 caracteres y `prod env` | Patrón `^[a-z0-9][a-z0-9-]{0,31}$` |
| TC03 concurrencia | Mutación sin bloquear el intento: `assert 'unmatched' == 'duplicate'` (el segundo no ve la transferencia y no la reconoce) | `FOR UPDATE` del intento antes de comprobar |

## B19-VC01 — Antes/después de duplicados y conflicto

Proceso real `python -m tappy` sobre `8ff2289` con `TAPPY_PAYMENT_PROVIDER=pey` (pey falso local para el QR) y secreto de webhooks generado; entorno `local`. Valores sintéticos.

| Paso | Status | Resultado |
| --- | --- | --- |
| E1 para T1 | 204 | `(sin cuerpo)` |
| Antes de los duplicados: `GET /sales/{A}` | 200 | `status=paid, confirmed_amount_cents=30000, transfers=[{"provider_transaction_id": "TX-VC01-T1", "amount_cents": 30000, "occurred_at": "2026-11-18T11:06:40Z", "received_at": "2026-11-25T01:29:40.559014Z", "beneficiary_name": "Tienda Demo A SA de CV", "masked_account": "**************6782"}]` |
| E1 reentregado (mismo id y contenido) | 204 | `(sin cuerpo)` |
| E2 para la misma transferencia T1 | 204 | `(sin cuerpo)` |
| E1 con otro contenido (importe 999.00, otra transacción) | 204 | `(sin cuerpo)` |
| Después: `GET /sales/{A}` | 200 | `status=paid, confirmed_amount_cents=30000, transfers=[{"provider_transaction_id": "TX-VC01-T1", "amount_cents": 30000, "occurred_at": "2026-11-18T11:06:40Z", "received_at": "2026-11-25T01:29:40.559014Z", "beneficiary_name": "Tienda Demo A SA de CV", "masked_account": "**************6782"}]` |

Señalización y reproceso:

```
$ python -m tappy.sales event-conflicts
event: msg_vc01_e1 (pey, local)
problem: conflicting content for an event id already stored
original digest: 4ba691054396ea4797fc838e8c8b0d714f5bf4677b137b12488c0ec1db4e3b5e
variant digest: 555abdc397644c59870c116123a7756314176ea9b48c50a7c14fd5b2928f87de
variant received at: 2026-11-25T01:29:40.588070+00:00
$ # E2 devuelto a received para reprocesarlo
$ python -m tappy.sales process-events
0 events applied, 0 unmatched, 1 duplicate, 0 failed
```

Estado final: `events [('msg_vc01_e1', 'local', 'applied'), ('msg_vc01_e2', 'local', 'duplicate')]`; `conflicts 1 transfers (1, 30000)`. **Antes** (B18): la variante de E1 se habría confirmado y descartado sin rastro, y E2 habría quedado `unmatched`.

### Diferencias

| Superficie | Antes (B18) | Después | Clasificación | Decisión |
| --- | --- | --- | --- | --- |
| Variante con el mismo id | Confirmada y descartada | Confirmada, original intacto, variante en `webhook_event_conflicts` y listada | Comportamiento | Aceptada (AC02) |
| Otro evento de una transferencia ya registrada | `unmatched` | `duplicate` si coinciden importe y cuenta; si no, `unmatched` | Comportamiento | Aceptada (AC01/AC03) |
| Salida de `process-events` | `1 event applied, 0 unmatched, 0 failed` | `1 event applied, 0 unmatched, 0 duplicates, 0 failed` | Cambio de formato del comando operativo | Aceptada: añade el conteo de duplicados; ningún consumidor la analiza |

Datos eliminados al terminar (esquema de desarrollo recreado). Estado VC01: **PASS**.

## Checks

`uv run python -m quality.check` sobre `8ff2289` (con `.env` exportado): PASS format, lint, types (mypy strict), hygiene, migrations (upgrade/downgrade/upgrade + `alembic check`), tests (386 passed, Postgres real aislado), api (16 contratos sin diferencias); `evidence` B01–B18 APPROVED.

## Supresiones

Sin supresiones nuevas.

## Umbral

AC PASS / AC aplicables = 3/3 = **100%**.

## Review Standards/Spec

| Ronda | Revisión | Standards | Spec | Hallazgos |
| --- | --- | --- | --- | --- |
| 1 | `085acb6` + `3ac434b` | CHANGES_REQUESTED | APPROVE | Standards: un segundo evento con el mismo `transactionId` pero otro importe/cuenta se ocultaba como `duplicate`; `TAPPY_ENVIRONMENT` sin límite (500 en inserción, deduplicación dividida por mayúsculas); downgrade sin guarda de ids compartidos; registro TDD que no declaraba que los tests se escribieron juntos; faltaba el antes de la salida de `process-events`. Spec (menores): tests de unicidad de transferencias por entorno y de conflicto sobre un evento sin aplicar; reentrega de un evento atascado |
| 2 | `8ff2289` + `79a8b2b` | APPROVE | APPROVE | Corregido con Red/Green; desviación TDD declarada; tabla de diferencias; VC01 repetida |

Hallazgos pendientes: 0.
