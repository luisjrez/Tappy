# Evidencia — B03 Ejecutar checks y pruebas en CI

Ticket: [#11](https://github.com/luisjrez/Tappy/issues/11) · Historia: [H1 #1](https://github.com/luisjrez/Tappy/issues/1) · Protocolo: [TICKET_QUALITY_PROTOCOL](../planning/TICKET_QUALITY_PROTOCOL.md) · Plantilla: [EVIDENCE_COMPARISON_TEMPLATE](../planning/EVIDENCE_COMPARISON_TEMPLATE.md) · Manifiesto: [B03-ci-checks.toml](B03-ci-checks.toml)

## Revisiones y escenario

- Ticket, UC/AC/TC y comprobación: B03-UC01–UC03, B03-AC01–AC03, B03-TC01–TC03, B03-VC01.
- Modalidad: **resultado inicial** (no existía comando de calidad ni CI). Aplicabilidad: comandos y CI sí; API sin cambios de contrato; panel no aplica (sin vistas).
- Base: rama B02 `b115bce` (PR #52). Revisión evaluada: `ead8cdd` (SHA final en el PR).
- Entorno local: macOS (Darwin 25.6), Colima + Compose 5.0.2, Python 3.14.8, uv 0.9.5. CI: `ubuntu-24.04`, `actions/checkout@v7`, `astral-sh/setup-uv@v10.3.3`, `actions/upload-artifact@v7`. Fecha: 2026-11-20. Ejecutor: sesión local de desarrollo del autor del PR y GitHub Actions.
- Datos: variables sintéticas `ci-synthetic-…` en el workflow; ninguna credencial ni banco real.

## Diseño

- `tools/quality` (paquete de desarrollo, no se expone por la API):
  - `check`: comando único con pasos `format`, `lint` (`--no-fix`), `types`, `hygiene`, `migrations`, `tests` (JUnit en `reports/junit.xml`) y `evidence`. Ejecuta todos aunque uno falle y sale con 1 si alguno falla.
  - `hygiene`: comentarios detectados con `tokenize` (no grep); solo se permiten directivas `noqa`, `type: ignore[...]` y `pragma: no cover`.
  - `migrations`: base desechable → `upgrade head` → `downgrade base` → `upgrade head` → `alembic check` (drift modelos/migraciones).
  - `evidence`: manifiestos TOML por ticket (`docs/evidence/*.toml`) con UC/AC/TC → tests; calcula `100 × AC PASS / AC aplicables` sin redondeo y bloquea si <97%, si un AC obligatorio no pasa, si VC01 no es PASS/N/A justificado o si hay hallazgos de review pendientes. Tests ausentes en el JUnit = NOT_RUN; `skipped` = FAIL; casos manuales/externos exigen resultado y evidencia; un AC N/A exige justificación.
  - `api_diff`: compara snapshots de API con normalización declarada (placeholders estables por documento, que conservan relaciones), orden de listas significativo, tipos/presencia/valor; sale con 1 ante cualquier diferencia y nunca escribe la base.
- `.github/workflows/backend.yml`: en cada push instala con `uv sync --locked`, levanta Compose y ejecuta `python -m quality.check`; sube `reports/` como artefacto.
- Manifiestos de B01 y B02 añadidos: sus AC quedan ligados a tests que el CI vuelve a exigir.

## Trazabilidad UC → AC → TC → test

| UC | AC | TC | Prueba real | Resultado |
| --- | --- | --- | --- | --- |
| B03-UC01 | B03-AC01 | B03-TC01 | `tests/quality/test_check.py::test_clean_project_passes_every_step` (proyecto fixture con la configuración real); `tests/quality/test_migrations.py::test_current_migrations_apply_roll_back_and_match_models`; batería real local y en CI (abajo) | PASS |
| B03-UC02 | B03-AC02 | B03-TC02 | `test_each_infraction_fails_the_battery[format, lint, types, hygiene, tests]`; `test_models_without_migration_are_reported`; tests de bloqueo del runner de evidencia y de `api_diff`; sonda Red en CI (abajo) | PASS |
| B03-UC03 | B03-AC03 | B03-TC03 | `tests/quality/test_hygiene.py` (comentario señalado; `#` dentro de cadenas y f-strings no; directivas permitidas; CLI con salida 1/0) | PASS |

## TDD

| Comportamiento | Red observado | Green |
| --- | --- | --- |
| Comentario vs `#` en cadena | Stub `find_comments → []`: `assert [] == [Finding(… line=6 …)]` | `tokenize` + filtro `COMMENT` |
| Directivas permitidas y CLI | Directivas señaladas (3 hallazgos); CLI inexistente salía 0 | Regex de directivas; `main` con exclusión de `.venv` y salida 1 |
| Batería: proyecto limpio y una infracción por vez | Stub `check.main → 0`: 6 fallos (sin `PASS/FAIL <paso>`) | Runner de pasos; el fixture además detectó formato real pendiente en `check.py`, `S603` sin acotar, `tappy` resuelto al paquete instalado (→ `pythonpath`) y un fixture sin `src` real |
| Drift de migraciones | Stub `verify_migrations → []`: `assert 0 == 1` | Upgrade/downgrade/upgrade + `alembic check`; `target_metadata` inyectable por `config.attributes` |
| Completitud aprobada | Stub `evaluate → no aprobado` | Modelo Pydantic del manifiesto, lectura JUnit, estados por caso/AC |
| Condiciones obligatorias | 6 fallos: AC obligatorio bajo margen, VC01 NOT_RUN/FAIL/BLOCKED, review pendiente, sin criterios | `blockers()`; `vc01_satisfied` |
| Casos externos, N/A y CLI | 6 fallos | `result`/`evidence`, `applicable`/`justification` validado, `main` sobre directorio |
| Diff de API | Stub `compare → []`: 4 fallos | `Normalizer` + `differences`; CLI sin escritura |

Tests que pasaron sin Red propio (implementados por un Green anterior y conservados como regresión): `test_command_succeeds_without_comments`, `test_completeness_is_not_rounded_up`, `test_agreed_optional_criterion_may_fail_within_margin`, `test_vc01_not_applicable_requires_justification[…]`, `test_command_succeeds_when_every_ticket_is_approved`, `test_declared_volatile_values_are_normalized_preserving_relations`, los casos `skipped`/`missing`/vacío de `test_one_unmet_criterion_of_three_blocks_approval`.

Refactor con suite verde: `disposable_database` compartido entre `conftest` y `quality.migrations`; nombres `junit_key`/`outcome_of`; `mandatory_label`.

## B03-TC01 — Batería local y CI

Local, sobre el árbol de `ead8cdd`:

```text
$ uv run python -m quality.check
PASS format (exit 0)
PASS lint (exit 0)
PASS types (exit 0)
PASS hygiene (exit 0)
PASS migrations (exit 0)
PASS tests (exit 0)
## B01: APROBADO … Completitud: 100.00%
## B02: APROBADO … Completitud: 100.00%
## B03: APROBADO … Completitud: 100.00%
PASS evidence (exit 0)
Summary: PASS format, PASS lint, PASS types, PASS hygiene, PASS migrations, PASS tests, PASS evidence
```

CI sobre `ead8cdd`: [run 44837302819](https://github.com/luisjrez/Tappy/actions/runs/44837302819) — **success**; 7 pasos PASS, `50 passed`, B01/B02 APROBADO (el manifiesto de B03 se añade en el commit siguiente, que repite la batería en CI).

## B03-TC02 — Sonda Red en CI

Rama temporal con `tests/test_ci_red_probe.py` (`assert 1 + 1 == 3`) sobre `ead8cdd` (commit sonda `f16c4fa`): [run 44837307038](https://github.com/luisjrez/Tappy/actions/runs/44837307038) — **failure**: `FAILED tests/test_ci_red_probe.py::test_deliberately_failing_probe - assert (1 + 1) == 3` → `FAIL tests (exit 1)`; además `FAIL lint (exit 1)` por el literal del propio test; el job termina en rojo. La rama se eliminó después; el test temporal no forma parte del PR.

Primer intento de CI (`7683f5d`): el job falló al resolver `astral-sh/setup-uv@v10` (no existe tag mayor). Corregido fijando `v10.3.3`; ese fallo no se cuenta como evidencia de la sonda.

## B03-VC01 — Resultado inicial de comandos

Diff de API con normalización declarada (`body.id`, `body.created_at`, `body.attempts[*].sale_id`); la base no cambia (mismo `shasum` antes y después):

```text
$ python -m quality.api_diff baseline.json current.json --normalize body.id --normalize body.created_at --normalize "body.attempts[*].sale_id"
type: body.amount_cents: 15000 -> '15000'
added: body.currency: None -> 'MXN'
exit=1
shasum baseline.json antes/después: 6e1680174feda42e57909047cdcffeca156a1dac
```

Higiene por separado sobre un archivo con comentario y `#` en cadena/f-string:

```text
$ python -m quality.hygiene sample.py
sample.py:5: # explains the obvious
exit=1
```

Estado VC01: **PASS** (resultado inicial). Diferencias inesperadas: ninguna. Panel: sin UI afectada.

## Checks

| Comando | Resultado | Código |
| --- | --- | --- |
| `uv run python -m quality.check` | 7/7 pasos PASS; `50 passed`; B01–B03 APROBADO | 0 |

## Umbral

AC PASS / AC aplicables = 3/3 = **100%**. VC01 PASS. Hallazgos pendientes: ver review.

## Review Standards/Spec

Pendiente.
