# Evidencia — B04 Provisionar el primer administrador

Ticket: [#12](https://github.com/luisjrez/Tappy/issues/12) · Historia: [H2 #2](https://github.com/luisjrez/Tappy/issues/2) · Protocolo: [TICKET_QUALITY_PROTOCOL](../planning/TICKET_QUALITY_PROTOCOL.md) · Manifiesto: [B04-bootstrap-admin.toml](B04-bootstrap-admin.toml)

## Revisiones y escenario

- Ticket, UC/AC/TC y comprobación: B04-UC01–UC03, B04-AC01–AC03, B04-TC01–TC03, B04-VC01.
- Modalidad: **resultado inicial** (comando nuevo). Aplicabilidad: comando sí; API sin cambios (las bases de `health`/`ready` siguen sin diferencias); panel no aplica.
- Base: rama B03 `f067526` (PR #53, stack nativo #54). Revisión evaluada: candidato `a5d7cb8`.
- Entorno: macOS (Darwin 25.6), Colima + Compose, Python 3.14.8, argon2-cffi 25.1.0, email-validator 2.4.0. Fecha: 2026-11-20. Ejecutor: sesión local de desarrollo del autor del PR.
- Actor: Responsable operativo. Datos: correos `@tappy.example` y frases de paso sintéticas.

## Decisiones aplicadas (acordadas antes de B04)

- Contraseña del primer administrador solo por stdin: oculta y confirmada con `getpass` en una terminal; una línea por pipe en scripts. Nunca por argumento ni variable de entorno.
- Política NIST: 12–128 caracteres, sin reglas de composición, rechazo de una lista corta local de contraseñas comunes (comparación sin mayúsculas). Hash Argon2id (`argon2-cffi`, parámetros por defecto).
- Sin registro público ni contraseña predeterminada en el repo.

## Diseño

- `tappy.identity.models.User`: `id` UUID, `email` normalizado en minúsculas y único, `password_hash`, `role` (`admin`/`operator`) y `status` (`active`/`inactive`) con restricciones CHECK, `created_at`. Migración `0002_identity_users`.
- `tappy.identity.passwords`: `check_policy`, `hash_password`, `verify_password`.
- `tappy.identity.provisioning`: `provision_admin` (rechaza correo existente con `IdentityAlreadyExistsError`, también ante carrera vía `IntegrityError`; nunca cambia contraseña ni rol de una identidad existente) y `find_identity`. Sin routers: el aprovisionamiento y el hashing viven fuera de la capa HTTP.
- `python -m tappy.identity bootstrap-admin --email …` y `show --email …`; errores con prefijo `Error:` y salida 1.
- `tappy.models`: registro explícito de modelos usado por Alembic y por el paso `migrations` (sin imports por efecto lateral).

## Trazabilidad UC → AC → TC → test

| UC | AC | TC | Test real | Resultado |
| --- | --- | --- | --- | --- |
| B04-UC01 | B04-AC01 | B04-TC01 | `test_bootstrap_admin_reports_active_admin_without_exposing_password` (proceso real: referencia/rol/estado en `bootstrap-admin` y `show`, contraseña ausente de stdout/stderr); `test_stored_password_is_an_argon2id_hash`; `test_hash_verifies_only_the_original_password` | PASS |
| B04-UC02 | B04-AC02 | B04-TC02 | `test_invalid_bootstrap_input_creates_nothing_and_hides_password` (correo vacío/inválido, contraseña vacía/corta/129 caracteres/común: sin filas, contraseña no impresa); `test_accepts_passwords_at_the_length_limits` (12 y 128); `test_rejects_short_long_and_common_passwords` | PASS |
| B04-UC03 | B04-AC03 | B04-TC03 | `test_repeating_bootstrap_keeps_single_identity_and_original_password` (mismo correo en mayúsculas y otra contraseña: una sola fila, hash intacto, contraseña original válida); `test_bootstrap_never_elevates_an_existing_operator` | PASS |

«Autenticarlo» en B04-UC01 se verifica por el hash Argon2id que acepta solo la contraseña original; el login HTTP llega en B05, como indica el ticket.

## TDD

| Comportamiento | Red observado | Green |
| --- | --- | --- |
| Aprovisionar y consultar admin activo | CLI stub con salida 0: `assert None is not None` (sin `reference:`) | Modelo, migración `0002`, hashing, `provision_admin`, CLI |
| Entrada inválida y repetición sin cambios | Sin Red propio: el Green anterior ya validaba entradas y existencia. Mutaciones de control: quitar `check_policy` → 4 fallos de TC02; sobrescribir hash/rol de la identidad existente → fallan los 2 tests de TC03. Mutaciones revertidas | — |
| Límites de la política | Sin Red propio (cubiertos por `check_policy`); se conservan como regresión de los límites 12/128 | — |

Refactor con suite verde: registro `tappy.models` en lugar del import por efecto lateral en `env.py`; `migrated_database_url` en `conftest`; helpers `app_environment`/`run_identity` en `tests/support.py`.

## B04-VC01 — Resultado inicial del comando

DB local de Compose migrada a `0002_identity_users`:

```text
$ printf "<secreto sintético>\n" | python -m tappy.identity bootstrap-admin --email vc01-admin@tappy.example
Administrator provisioned
reference: 0e917fea-ec6b-4aa3-b23f-1abf62a0d1b1
email: vc01-admin@tappy.example
role: admin
status: active
exit=0

$ python -m tappy.identity show --email vc01-admin@tappy.example
reference: 0e917fea-ec6b-4aa3-b23f-1abf62a0d1b1
email: vc01-admin@tappy.example
role: admin
status: active
exit=0

$ printf "<otro secreto>\n" | python -m tappy.identity bootstrap-admin --email VC01-ADMIN@tappy.example
Error: An identity with this email already exists
exit=1

$ printf "short\n" | python -m tappy.identity bootstrap-admin --email other@tappy.example
Error: Password must have at least 12 characters
exit=1

$ printf "<secreto>\n" | python -m tappy.identity bootstrap-admin --email not-an-email
Error: Invalid email: An email address must have an @-sign.
exit=1

$ psql: SELECT email, role, status, left(password_hash, 10) FROM users
vc01-admin@tappy.example|admin|active|$argon2id$
```

Una sola identidad; ninguna salida contiene la contraseña. La fila de prueba se eliminó al terminar. Estado VC01: **PASS** (resultado inicial).

## Checks sobre `a5d7cb8`

`uv run python -m quality.check`: format, lint, types, hygiene, migrations (con `0002` y `alembic check` sin drift), tests (`81 passed`), api (sin diferencias) en PASS; `evidence`: B01–B03 APPROVED, B04 bloqueado solo por review pendiente hasta cerrar el review.

## Umbral

AC PASS / AC aplicables = 3/3 = **100%**.

## Review Standards/Spec

Pendiente.
