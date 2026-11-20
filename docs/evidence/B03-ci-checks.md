# Evidencia — B03 Ejecutar checks y pruebas en CI

Ticket: [#11](https://github.com/luisjrez/Tappy/issues/11) · Historia: [H1 #1](https://github.com/luisjrez/Tappy/issues/1) · Protocolo: [TICKET_QUALITY_PROTOCOL](../planning/TICKET_QUALITY_PROTOCOL.md) · Plantilla: [EVIDENCE_COMPARISON_TEMPLATE](../planning/EVIDENCE_COMPARISON_TEMPLATE.md) · Manifiesto: [B03-ci-checks.toml](B03-ci-checks.toml)

## Revisiones y escenario

- Ticket, UC/AC/TC y comprobación: B03-UC01–UC03, B03-AC01–AC03, B03-TC01–TC03, B03-VC01.
- Modalidad: **resultado inicial** (no existía comando de calidad ni CI). Aplicabilidad: comandos y CI sí; API sin cambios de contrato; panel no aplica (sin vistas).
- Base: rama B02 `b115bce` (PR #52). Revisión evaluada: `ead8cdd` (SHA final en el PR).
- Entorno local: macOS (Darwin 25.6), Colima + Compose 5.0.2, Python 3.14.8, uv 0.9.5. CI: `ubuntu-24.04`, `actions/checkout@v7`, `astral-sh/setup-uv@v10.3.3`, `actions/upload-artifact@v7`. Fecha: 2026-11-20. Ejecutor: sesión local de desarrollo del autor del PR y GitHub Actions.
- Datos: variables sintéticas `ci-synthetic-…` en el workflow; ninguna credencial ni banco real.

## Diseño

- `tools/quality` (paquete de desarrollo; el wheel solo incluye `src/tappy`, `tools` entra al entorno editable por `dev-mode-dirs`):
  - `check`: comando único con pasos `format`, `lint` (`--no-fix`), `types`, `hygiene`, `migrations`, `tests` (borra y regenera `reports/junit.xml`), `api` y `evidence`. Ejecuta todos aunque uno falle y sale con 1 si alguno falla.
  - `hygiene`: comentarios detectados con `tokenize` (no grep); solo se permiten directivas con códigos: `noqa: <códigos>`, `type: ignore[<códigos>]`, `pragma: no cover`. `# noqa` o `# type: ignore` sin códigos se señalan.
  - `migrations`: base desechable en el servidor de tests aislado (misma guarda que pytest) → `upgrade head` → `downgrade base` → `upgrade head` → `alembic check`.
  - `evidence`: manifiesto TOML por ticket con `revision` exacta, criterios con `use_cases` obligatorios (UC → AC → TC → tests), VC01 con modalidad (`initial`/`comparison`/`not_applicable`) y evidencia o justificación, y review por eje (`standards`/`spec`: `APPROVED`/`PENDING`/`CHANGES_REQUESTED`) más hallazgos pendientes. Completitud `100 × AC PASS / AC aplicables` sin redondeo; bloquea si <97%, AC obligatorio sin PASS, VC01 sin PASS/evidencia, algún eje no aprobado, hallazgos pendientes o revisión inexistente en el historial (`git merge-base --is-ancestor`; CI con `fetch-depth: 0`). Tests ausentes = NOT_RUN; `skipped` = FAIL.
  - `api_diff`: diff de snapshots con normalización declarada que conserva relaciones, orden de listas significativo, cambios tipados (`type`/`removed`/`added`/`value`); nunca escribe la base.
  - `api_snapshots`: casos declarados en `contracts/api/cases.toml`; captura la respuesta actual (DB migrada desechable o inalcanzable), escribe `reports/api/<caso>.current.json` y `<caso>.diff.txt` y compara con `contracts/api/baselines/<caso>.json`, que guarda la revisión aprobada. Sin base aprobada o con diferencias sale con 1; nunca crea ni sobrescribe bases. Aprobar una base es un cambio explícito revisado en el PR.
- Bases iniciales aprobadas desde la evidencia ya revisada: `health` (B01, `9f53aa9`), `ready-migrated` y `ready-unreachable` (B02, `ccf8eed`).
- `.github/workflows/backend.yml`: en cada push, `uv sync --locked`, Compose y `python -m quality.check`; sube `reports/` (JUnit y artefactos de API) como artefacto.
- Manifiestos de B01 y B02 añadidos: el gate de evidencia los vuelve a exigir en cada ejecución.

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

Correcciones del review (Red → Green):

| Comportamiento | Red observado | Green |
| --- | --- | --- |
| Esquema reforzado del manifiesto (UC, revisión, VC01, review por eje) | 28 de 29 tests fallan con el modelo anterior (campos rechazados) | Modelo nuevo y `blockers()` ampliado |
| `# noqa` / `# type: ignore` sin códigos | `assert ['# type: ignore'] == ['# noqa', '# type: ignore']` | Regex exige códigos |
| Artefactos de API con base aprobada | Stub `api_snapshots → exit 0`: 3 fallos | `api_snapshots` con `current`/`diff` y sin escritura de bases |
| Tipo de status en snapshots | Primera comparación real: `type: status: 503 -> <HTTPStatus.SERVICE_UNAVAILABLE: 503>` | `int(response.status_code)` |

Sin test propio: limpieza de `reports/junit.xml` antes de `tests` (pytest sobrescribe el archivo en todos los casos reproducibles; el cambio evita leer un JUnit viejo si pytest no llega a escribirlo).

Refactor con suite verde: `disposable_database` e `isolated_test_server` compartidos entre `conftest` y `quality.migrations`; `junit_key`/`outcome_of`; `label` en `check`; enums `Status`, `ReviewVerdict`, `Change`.

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
