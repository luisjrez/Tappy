# Evidencia — B01 Arrancar API modular y health

Ticket: [#9](https://github.com/luisjrez/Tappy/issues/9) · Historia: [H1 #1](https://github.com/luisjrez/Tappy/issues/1) · Protocolo: [TICKET_QUALITY_PROTOCOL](../planning/TICKET_QUALITY_PROTOCOL.md)

## Identificación

- Base fija: `e5bb134` (`main`). Revisión evaluada: commit del PR de B01 (el SHA final queda en el PR).
- Fecha: 2026-11-20. Entorno: macOS (Darwin 25.6), Python 3.14.8, uv 0.9.5, FastAPI 0.165.0, Pydantic 2.14.4, pydantic-settings 2.16.3, Uvicorn 0.54.0, pytest 9.2.0, mypy 2.4.1, Ruff 0.17.6.
- Datos: variables sintéticas (`synthetic-…`); ningún secreto real.

## Trazabilidad UC → AC → TC → test

| UC | AC | TC | Test real | Resultado |
| --- | --- | --- | --- | --- |
| B01-UC01 | B01-AC01 | B01-TC01 | `tests/test_health.py::test_health_reports_healthy_status`, `tests/test_startup.py::test_started_api_answers_health` (proceso real `python -m tappy` desde `.venv`) | PASS |
| B01-UC02 | B01-AC02 | B01-TC02 | `tests/test_startup.py::test_startup_fails_when_required_variable_is_missing`, `tests/test_startup.py::test_startup_failure_does_not_expose_secret_values[…]` (2 casos) | PASS |
| B01-UC03 | B01-AC03 | B01-TC03 | `tests/test_health.py::test_independent_app_instances_do_not_share_state` | PASS |

## TDD

| Comportamiento | Red observado | Green |
| --- | --- | --- |
| Health 200 | Con app factory sin rutas: `assert 404 == 200` | Router `platform/health.py` incluido por `create_app` |
| Fallo de configuración sin secretos | Entrada naïf `uvicorn.run(create_app(Settings()))`: traceback de Pydantic con `input_value='leaked-if-printed'`; los 3 casos fallan | `load_settings()` traduce `ValidationError` a `ConfigurationError` con `include_input=False` y `from None`; `__main__` sale con código 1 y el listado de variables |
| Dos instancias sin estado compartido | No se observó Red: el factory de TC01 ya entrega settings por instancia (`app.state`). Se conserva como regresión | — |
| Arranque real en puerto configurado | Proceso escuchaba en el puerto fijo 8000: `ConnectionRefusedError` en el puerto elegido | `TAPPY_HOST`/`TAPPY_PORT` en `Settings` y pasados a Uvicorn |

Refactor con suite verde: `platform/dependencies.py` expone `SettingsDependency` tipada; `health` deja de leer `request.app.state` sin tipo. Ensamblado (`main.py`), configuración (`platform/config.py`) y arranque (`__main__.py`) quedan separados.

## Checks (revisión del commit candidato)

| Comando | Resultado | Código |
| --- | --- | --- |
| `uv run ruff format --check .` | `10 files already formatted` | 0 |
| `uv run ruff check .` | `All checks passed!` | 0 |
| `uv run mypy` | `Success: no issues found in 10 source files` (strict + plugin Pydantic) | 0 |
| `uv run pytest` | `6 passed` | 0 |

Exenciones de lint localizadas en configuración, solo para `tests/**`: `S101` (assert), `S105`/`S106` (secretos sintéticos de prueba), `S310`/`S603` (urlopen y subprocess contra el proceso local bajo prueba), `PLR2004` (status HTTP literales). Sin `noqa`, `type: ignore` ni comentarios en el código.

## B01-VC01 — Resultado inicial

Modalidad: **nuevo — resultado inicial**; no hay health anterior. Superficies: API y comando de arranque. Sin UI: no aplican capturas.

API — `GET /health` sin cabeceras ni body, proceso real con `TAPPY_ENVIRONMENT=local`, `TAPPY_PORT=8765`:

```text
HTTP/1.1 200 OK
server: uvicorn
content-length: 37
content-type: application/json

{"status":"ok","environment":"local"}
```

Contrato esperado: `200`, `{"status": "ok", "environment": <TAPPY_ENVIRONMENT>}`; esquema `HealthStatus` en OpenAPI. Conforme.

Comando — falta `TAPPY_SECRET_KEY`:

```text
$ uv run python -m tappy
Invalid configuration:
- TAPPY_SECRET_KEY: Field required
exit=1
```

Comando — secreto inválido (`leaked-if-printed`) y sin `TAPPY_ENVIRONMENT`:

```text
$ TAPPY_SECRET_KEY=leaked-if-printed uv run python -m tappy
Invalid configuration:
- TAPPY_ENVIRONMENT: Field required
- TAPPY_SECRET_KEY: Value should have at least 32 items after validation, not 17
exit=1
```

El valor no aparece en stdout/stderr ni hay traceback. Estado VC01: **PASS** (resultado inicial conforme). Diferencias inesperadas: ninguna.

## Umbral

AC PASS / AC aplicables = 3/3 = **100%** (≥97%). Tests/checks 100% verdes; sin defectos conocidos de dinero, identidad, permisos ni secretos.

## Review

Ver PR: hallazgos Standards/Spec y su resolución.
