# Evidencia — B03 Ejecutar checks y pruebas en CI

Ticket: [#11](https://github.com/luisjrez/Tappy/issues/11) · Historia: [H1 #1](https://github.com/luisjrez/Tappy/issues/1) · Protocolo: [TICKET_QUALITY_PROTOCOL](../planning/TICKET_QUALITY_PROTOCOL.md) · Plantilla: [EVIDENCE_COMPARISON_TEMPLATE](../planning/EVIDENCE_COMPARISON_TEMPLATE.md) · Manifiesto: [B03-ci-checks.toml](B03-ci-checks.toml)

## Revisiones y escenario

- Ticket, UC/AC/TC y comprobación: B03-UC01–UC03, B03-AC01–AC03, B03-TC01–TC03, B03-VC01.
- Modalidad: **resultado inicial** (no existía comando de calidad ni CI). Aplicabilidad: comandos y CI sí; API sin cambios de contrato; panel no aplica (sin vistas).
- Base: rama B02 `b115bce` (PR #52). Revisiones: candidato `ead8cdd` → correcciones `2027d97` → código final `36e15c0`. Toda la evidencia de esta página corresponde a `36e15c0` salvo donde se indica otra revisión; los commits posteriores solo modifican documentación de evidencia y el manifiesto. Límite conocido: el gate verifica que la revisión exista en el historial (`merge-base --is-ancestor`), no que sea el último commit de código, porque un manifiesto no puede nombrar su propio commit.
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

Local sobre `36e15c0` (manifiesto de B03 aún con review `PENDING`, por eso `evidence` bloquea solo B03):

```text
$ uv run python -m quality.check
PASS format · PASS lint · PASS types · PASS hygiene · PASS migrations
64 passed
PASS tests · PASS api
## B01: APPROVED (revision 9f53aa9) — Completeness: 100.00%
## B02: APPROVED (revision ccf8eed) — Completeness: 100.00%
## B03: BLOCKED (revision 5a088e2) — Completeness: 100.00%
- Blocker: standards review is PENDING
- Blocker: spec review is PENDING
Summary: PASS format, PASS lint, PASS types, PASS hygiene, PASS migrations, PASS tests, PASS api, FAIL evidence
```

CI:

| Revisión | Ejecución | Resultado |
| --- | --- | --- |
| `ead8cdd` (candidato, gate anterior) | [44837302819](https://github.com/luisjrez/Tappy/actions/runs/44837302819) | success: 7/7 pasos, `50 passed` |
| `2027d97` (correcciones, review B03 `PENDING`) | [44838543496](https://github.com/luisjrez/Tappy/actions/runs/44838543496) | failure solo en `evidence`: `standards/spec review is PENDING` (comportamiento esperado del gate) |
| `622bcef` = `2027d97` + manifiesto B03 aprobado temporalmente (control de las sondas) | [44838548308](https://github.com/luisjrez/Tappy/actions/runs/44838548308) | success: `Summary: PASS format, PASS lint, PASS types, PASS hygiene, PASS migrations, PASS tests, PASS api, PASS evidence` |
| HEAD final del PR | ver checks del PR | debe quedar en success con el manifiesto aprobado tras la re-revisión |

## B03-TC02 — Sondas Red en CI, una infracción por vez

Ramas temporales sobre el control `622bcef` (eliminadas después; su contenido no forma parte del PR):

| Infracción | Commit | Ejecución | Resumen del job |
| --- | --- | --- | --- |
| Test fallido (`assert "tappy".upper() == "tappy"`) | `6d83ef2` | [44838553072](https://github.com/luisjrez/Tappy/actions/runs/44838553072) | failure · `PASS format, PASS lint, PASS types, PASS hygiene, PASS migrations, FAIL tests, PASS api, PASS evidence` |
| Error de tipos (`def probe_value() -> int: return "not an int"`) | `b73d6fb` | [44838557153](https://github.com/luisjrez/Tappy/actions/runs/44838557153) | failure · `FAIL types` (el meta-test del fixture, que copia `src`, también falla en `tests`) |
| Lint (`import os` sin uso) | `0b9fe94` | [44838561253](https://github.com/luisjrez/Tappy/actions/runs/44838561253) | failure · `FAIL lint` (el meta-test del fixture también falla en `tests`) |

En las sondas de tipos y lint, el paso `tests` también falla porque `test_clean_project_passes_every_step` copia el `src` real (con la infracción) a su proyecto fixture: es la misma infracción detectada dos veces, no un segundo cambio. La sonda anterior (`f16c4fa`, [44837307038](https://github.com/luisjrez/Tappy/actions/runs/44837307038)) rompía test y lint a la vez y queda sustituida por estas tres.

Primer intento de CI (`7683f5d`): fallo al resolver `astral-sh/setup-uv@v10` (no existe tag mayor); corregido fijando `v10.3.3`. No cuenta como evidencia.

## B03-VC01 — Resultado inicial de comandos

`api_snapshots` contra las bases aprobadas:

```text
$ uv run python -m quality.api_snapshots
health: no differences against 2027d97
ready-migrated: no differences against 2027d97
ready-unreachable: no differences against 2027d97
exit=0
```

Caso rojo controlado: copia de `contracts/api` con la base `ready-unreachable` alterada (`status 500`, campo `detail` extra). La diferencia se señala, el `.diff.txt` queda como artefacto y la base no cambia:

```text
shasum antes: 707fb11d2bd9
$ uv run python -m quality.api_snapshots --contracts=<copia con base alterada>
health: no differences against 2027d97
ready-migrated: no differences against 2027d97
ready-unreachable: 2 differences against 2027d97
value: status: 500 -> 503
removed: body.detail: 'database down' -> None
exit=1
shasum después: 707fb11d2bd9
```

`api_diff` directo con normalización declarada (`body.id`, `body.created_at`, `body.attempts[*].sale_id`):

```text
type: body.amount_cents: 15000 -> '15000'
added: body.currency: None -> 'MXN'
exit=1   (shasum de la base idéntico antes/después)
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
| `uv run python -m quality.check` sobre `36e15c0` | 8 pasos; `64 passed`; B01/B02 APPROVED; B03 bloqueado solo por review pendiente hasta la re-revisión | 1 → 0 al aprobar |

## Umbral

AC PASS / AC aplicables = 3/3 = **100%**. VC01 PASS. Hallazgos pendientes: ver review.

## Supresiones

- Línea: `# noqa: S105` en `Status.PASS = "PASS"` (falso positivo de contraseña), `# noqa: S314` al leer el JUnit generado localmente por pytest, `# noqa: S603` en los `subprocess.run` de `check` y `evidence` (comandos fijos del propio repo).
- Archivo, solo tests: `tests/quality/*` → `S603` (los meta-tests ejecutan los comandos de calidad como subprocesos), además de las ya registradas en B01/B02.

## Review Standards/Spec

| Ronda | Eje | Hallazgo | Resolución |
| --- | --- | --- | --- |
| 1 (`5a088e2`) | Standards/Spec | Manifiesto con `pending_findings = 0` antes del review: el gate aprobaba B03 | Review por eje (`APPROVED`/`PENDING`/`CHANGES_REQUESTED`); B03 queda bloqueado hasta aprobar |
| 1 | Spec | UC no registrados | `use_cases` obligatorio por AC; tabla UC → AC → TC |
| 1 | Spec | VC01 PASS sin evidencia | Modalidad + evidencia o justificación obligatorias |
| 1 | Spec | Artefactos API no preparados ni ligados a base aprobada | `quality.api_snapshots`, `contracts/api`, paso `api` en `check`/CI |
| 1 | Spec | Manifiestos sin revisión | `revision` verificada en el historial; CI `fetch-depth: 0` |
| 1 | Spec | Sonda Red rompía test y lint a la vez | Tres sondas separadas + control |
| 1 | Spec | `evidence` podía leer un JUnit viejo | `check` borra `reports/junit.xml` antes de `tests` |
| 1 | Standards | Ignores por archivo `S105`/`S314` | Directivas de línea con código |
| 1 | Standards | `# noqa` sin códigos permitido | Higiene exige códigos |
| 1 | Standards | `tools` dentro del wheel | `dev-mode-dirs`; el wheel solo contiene `tappy` (verificado con `uv build`) |
| 1 | Standards | Variable/guarda de servidor de tests duplicada | `quality.databases.isolated_test_server` |
| 1 | Standards | Vocabulario de estados triplicado; `kind` como `str`; salida mezclada español/inglés; `PASS/FAIL` duplicado | Enums `Status`/`ReviewVerdict`/`Change`; salida en inglés; `label()` |
| 1 | Spec | Manifiestos de B01/B02 fuera de alcance | Se conservan: el gate necesita los manifiestos de los tickets entregados |
| 1 | Standards | Semilla `target_metadata` en `env.py` | Se conserva: permite probar drift sin tocar los modelos reales |
| 2 (`2027d97`) | Spec | Evidencia de sondas y revisión desactualizadas (bloqueante) | Página reescrita con `36e15c0`, sondas y control |
| 2 | Spec | VC01 sin `api_snapshots` | Añadida salida verde y caso rojo con base intacta |
| 2 | Spec | Etiqueta de revisión de la base `health` | Bases etiquetadas con `2027d97`, el commit que las aprobó |
| 2 | Standards | `S603` mezclado entre archivo y línea | Línea en `tools`; archivo solo en `tests/quality/*` |
| 2 | Standards | Bases sin validar; `IsolationError` con traceback; reportes viejos | `Baseline` Pydantic; error claro; limpieza de `reports/api` (con Red/Green: 3 tests) |
| 2 | Spec | `merge-base --is-ancestor` no prueba que sea el último código | Límite documentado arriba |

Re-revisión final: pendiente.
