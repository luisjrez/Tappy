# Evidencia — B01 Arrancar API modular y health

Ticket: [#9](https://github.com/luisjrez/Tappy/issues/9) · Historia: [H1 #1](https://github.com/luisjrez/Tappy/issues/1) · Protocolo: [TICKET_QUALITY_PROTOCOL](../planning/TICKET_QUALITY_PROTOCOL.md) · Plantilla: [EVIDENCE_COMPARISON_TEMPLATE](../planning/EVIDENCE_COMPARISON_TEMPLATE.md)

## Revisiones y escenario

- Ticket, UC/AC/TC y comprobación: B01-UC01–UC03, B01-AC01–AC03, B01-TC01–TC03, B01-VC01.
- Modalidad: **resultado inicial** (primer servicio; no hay health ni arranque previos).
- Aplicabilidad por superficie: API sí (`GET /health`); comando sí (`python -m tappy`); panel **no aplica**: B01 no crea vistas de back office.
- Base: `e5bb134` (`main`). No hay base aprobada previa.
- Revisión evaluada: commit candidato `ca7d9bf` y commit de corrección de review (SHA final en el PR; la evidencia se repitió sobre el HEAD corregido).
- Entorno: macOS (Darwin 25.6), Python 3.14.8, uv 0.9.5, FastAPI 0.165.0, Starlette 1.10.0, Pydantic 2.14.4, pydantic-settings 2.16.3, Uvicorn 0.54.0, pytest 9.2.0, mypy 2.4.1, Ruff 0.17.6. Fecha: 2026-11-20. Ejecutor: sesión local de desarrollo del autor del PR.
- Actor: Desarrollador. Fixture: variables sintéticas (`synthetic-…`, `leaked-if-printed`); ningún secreto real.
- Pasos reproducibles: `cd apps/backend && rm -rf .venv && uv sync`, exportar variables de `.env.example` con valores sintéticos, `.venv/bin/python -m tappy`, `curl http://127.0.0.1:<port>/health`.

## Trazabilidad UC → AC → TC → test

| UC | AC | TC | Test real | Resultado |
| --- | --- | --- | --- | --- |
| B01-UC01 | B01-AC01 | B01-TC01 | `tests/test_health.py::test_health_reports_healthy_status`; `tests/test_startup.py::test_started_api_answers_health` (proceso real `python -m tappy`); instalación limpia manual en `.venv` (abajo) | PASS |
| B01-UC02 | B01-AC02 | B01-TC02 | `tests/test_startup.py::test_startup_fails_when_required_variable_is_missing` (secreto válido presente, falta `TAPPY_ENVIRONMENT`); `tests/test_startup.py::test_startup_failure_does_not_expose_secret_values[…]` (2 casos: ni el valor ni su longitud aparecen) | PASS |
| B01-UC03 | B01-AC03 | B01-TC03 | `tests/test_health.py::test_independent_app_instances_do_not_share_state` (settings y rutas propias por instancia) | PASS |

## TDD

| Comportamiento | Red observado | Green |
| --- | --- | --- |
| Health 200 | App factory sin rutas: `assert 404 == 200` | Router `platform/health.py` incluido por `create_app` |
| Fallo de configuración sin secretos | Entrada `uvicorn.run(create_app(Settings()))`: traceback de Pydantic con `input_value='leaked-if-printed'`; 3 casos fallan | `load_settings()` traduce `ValidationError` a `ConfigurationError` (`include_input=False`, `from None`); `__main__` sale con código 1 |
| Longitud del secreto no expuesta (hallazgo de review) | `assert '17' not in '…not 17'` en 2 casos | Mensajes de campos `SecretStr` redactados: «must have at least 32 characters» / «invalid secret value» |
| Arranque real en puerto configurado | El proceso escuchaba en 8000 fijo: `ConnectionRefusedError` en el puerto elegido | `TAPPY_HOST`/`TAPPY_PORT` en `Settings` y pasados a Uvicorn |
| Dos instancias sin estado compartido | No hubo Red inicial: el factory de TC01 ya lo cumplía. Mutación de control (factory que devuelve una app compartida): `assert {…'test'} == {…'staging'}` → el test detecta la regresión; mutación revertida | — |

Refactor con suite verde: `SettingsDependency` tipada en `platform/dependencies.py`; `variable_name`/`safe_message` en `config.py`; helpers de proceso compartidos en `tests/support.py`. Ensamblado (`main.py`), configuración (`platform/config.py`) y arranque (`__main__.py`) separados.

## Checks sobre el HEAD corregido

| Comando | Resultado | Código |
| --- | --- | --- |
| `uv run ruff format --check .` | `12 files already formatted` | 0 |
| `uv run ruff check .` | `All checks passed!` | 0 |
| `uv run mypy` | `Success: no issues found in 11 source files` (strict + plugin Pydantic) | 0 |
| `uv run pytest` | `6 passed` | 0 |

Exenciones de lint en configuración, acotadas: `tests/**` → `S101` (assert), `S105`/`S106` (secretos sintéticos); `tests/support.py` → `S603` (subprocess del propio `tappy`); `tests/test_startup.py` → `S310` (urlopen a 127.0.0.1). Sin `noqa`, `type: ignore` ni comentarios. Informe JUnit y comando único: diferidos a B03, que los define en su alcance.

## API — resultado inicial

`GET /health`, sin body ni cabeceras de petición. Proceso real tras `rm -rf .venv && uv sync`, `TAPPY_ENVIRONMENT=local`, `TAPPY_PORT=8765`.

| Elemento | Actual |
| --- | --- |
| Status HTTP | `200` |
| Cabeceras relevantes | `content-type: application/json` |
| Cuerpo JSON | `{"status":"ok","environment":"local"}` |
| Contrato | `HealthStatus {status: "ok", environment: str}` en OpenAPI |

`environment` es el nombre no secreto del entorno configurado; hace observable que cada instancia usa su propia configuración (AC03). No incluye credenciales ni datos del host.

## Comandos — resultado inicial

```text
$ unset TAPPY_SECRET_KEY; uv run python -m tappy
Invalid configuration:
- TAPPY_SECRET_KEY: Field required
exit=1

$ TAPPY_SECRET_KEY=leaked-if-printed uv run python -m tappy
Invalid configuration:
- TAPPY_ENVIRONMENT: Field required
- TAPPY_SECRET_KEY: must have at least 32 characters
exit=1
```

Sin traceback; el valor y su longitud no aparecen.

## Back office

Sin UI afectada.

## Diferencias y decisión

| TC / AC | Diferencia | Clasificación | Motivo | Evidencia | Resolución |
| --- | --- | --- | --- | --- | --- |
| B01-TC01–TC03 / AC01–AC03 | Resultado inicial; sin base anterior | No aplica diff | Servicio nuevo | Tests y salidas anteriores | Conforme |

- Estado VC01: **PASS** (resultado inicial validado contra contrato/AC/TC).
- Diferencias inesperadas pendientes: ninguna.
- Nueva base propuesta: este resultado inicial, solo tras aprobación humana del PR.

## Umbral

AC PASS / AC aplicables = 3/3 = **100%** (≥97%). Tests/checks 100% verdes; sin defectos conocidos de dinero, identidad, permisos ni secretos.

## Review Standards/Spec

| Eje | Hallazgo | Resolución |
| --- | --- | --- |
| Spec | Mensaje de error revelaba la longitud del secreto | Corregido con Red/Green (mensajes redactados) |
| Spec | Faltaba TC02 con secreto válido y otra variable ausente | Test añadido |
| Spec / Standards | Aserción de identidad `state is not state` tautológica | Sustituida por rutas/settings observables por instancia; mutación de control |
| Spec | Plantilla incompleta, sin SHA ni ejecutor | Plantilla completada; SHA candidato y final registrados |
| Spec | Instalación limpia en `.venv` no ejercitada | Ejecutada (`rm -rf .venv && uv sync`) y registrada |
| Spec | `environment` en health como posible ampliación | Se conserva: dato no secreto que demuestra AC03; documentado |
| Standards | Exenciones de lint para todo `tests/**` | Acotadas por archivo; `PLR2004` eliminado con `HTTPStatus` |
| Standards | Duplicación de secreto/comando en tests | Extraído a `tests/support.py` |
| Standards | Expresión densa en `describe_problems` | Extraído `variable_name` |
| Standards | `environment` como `str` libre | Se mantiene: el ticket no define el conjunto de entornos |

Re-revisión sobre el HEAD corregido: sin hallazgos pendientes.
