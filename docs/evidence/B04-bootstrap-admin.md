# Evidencia — B04 Provisionar el primer administrador

Ticket: [#12](https://github.com/luisjrez/Tappy/issues/12) · Historia: [H2 #2](https://github.com/luisjrez/Tappy/issues/2) · Protocolo: [TICKET_QUALITY_PROTOCOL](../planning/TICKET_QUALITY_PROTOCOL.md) · Manifiesto: [B04-bootstrap-admin.toml](B04-bootstrap-admin.toml)

## Revisiones y escenario

- Ticket, UC/AC/TC y comprobación: B04-UC01–UC03, B04-AC01–AC03, B04-TC01–TC03, B04-VC01.
- Modalidad: **resultado inicial** (comando nuevo). Aplicabilidad: comando sí; API sin cambios (las bases de `health`/`ready` siguen sin diferencias); panel no aplica.
- Base: rama B03 `f067526` (PR #53, stack nativo #54). Revisiones: candidato `a5d7cb8` → correcciones `da6e33f` → código final `961ff31` (índice del modelo). Checks y tests corresponden a `961ff31`; el VC01 se capturó sobre `da6e33f` con la migración, que no cambió.
- Entorno: macOS (Darwin 25.6), Colima + Compose, Python 3.14.8, argon2-cffi 25.1.0, email-validator 2.4.0. Fecha: 2026-11-20. Ejecutor: sesión local de desarrollo del autor del PR.
- Actor: Responsable operativo. Datos: correos `@tappy.example` y frases de paso sintéticas.

## Decisiones aplicadas (acordadas antes de B04)

- Contraseña del primer administrador solo por stdin: oculta y confirmada con `getpass` en una terminal; una línea por pipe en scripts. Nunca por argumento ni variable de entorno.
- Política NIST: normalización Unicode NFKC, 12–128 caracteres, sin reglas de composición, rechazo de una lista corta local de contraseñas comunes (comparación sin mayúsculas). Hash Argon2id (`argon2-cffi`, parámetros por defecto).
- Sesión (para B05/B06): access token opaco de 15 min, renovación con rotación atómica, vida máxima de 30 días; documentada en el README del backend antes de activar, como pide el ticket.
- Sin registro público ni contraseña predeterminada en el repo.

## Diseño

- Vocabulario: `CONTEXT.md` incorpora **Administrador** e **Identidad**; el modelo es `Identity` (tabla `identities`), no «usuario».
- `tappy.identity.models.Identity`: `id` UUID, `email` normalizado, índice único `lower(email)` (la DB rechaza correos que difieren solo en mayúsculas), `password_hash`, `role` (`admin`/`operator`) y `status` (`active`/`inactive`) con restricciones CHECK, `created_at`. Migración `0002_identity_identities`. `operator` e `inactive` se incluyen porque B05 («admin u operador activo», «usuario inactivo») y B08 los usan; evita reescribir la restricción en el siguiente ticket.
- `tappy.identity.errors`: jerarquía única `IdentityError` (`PasswordPolicyError`, `InvalidEmailError`, `IdentityAlreadyExistsError`, `IdentityNotFoundError`).
- `tappy.identity.passwords`: `check_policy`, `hash_password`, `verify_password`, todos sobre la forma NFKC.
- `tappy.identity.provisioning`: `provision_admin` (rechaza correo existente; ante carrera solo un `UniqueViolation` se traduce a «already exists», otras violaciones se propagan; nunca cambia contraseña ni rol existentes) y `find_identity`. Sin routers.
- CLI `python -m tappy.identity bootstrap-admin|show --email …`: valida el correo antes de pedir la contraseña; lee una línea sin `\r\n`; un handler por comando (`set_defaults`).
- `tappy.models`: registro explícito (`__all__`) usado por Alembic y por el paso `migrations`. `enum_column` vive en `platform/persistence`.

## Trazabilidad UC → AC → TC → test

| UC | AC | TC | Test real | Resultado |
| --- | --- | --- | --- | --- |
| B04-UC01 | B04-AC01 | B04-TC01 | `test_bootstrap_admin_reports_active_admin_without_exposing_password` (proceso real: referencia/rol/estado en `bootstrap-admin` y `show`, contraseña ausente de stdout/stderr); `test_stored_password_is_an_argon2id_hash`; `test_hash_verifies_only_the_original_password`; `test_compatible_unicode_forms_are_the_same_password`; `test_windows_line_ending_is_not_part_of_the_password` | PASS |
| B04-UC02 | B04-AC02 | B04-TC02 | `test_invalid_bootstrap_input_creates_nothing_and_hides_password` (correo vacío/inválido, contraseña vacía/corta/129 caracteres/común: sin filas, contraseña no impresa); `test_accepts_passwords_at_the_length_limits` (12 y 128); `test_rejects_short_long_and_common_passwords`; `test_common_password_check_applies_after_unicode_normalization` | PASS |
| B04-UC03 | B04-AC03 | B04-TC03 | `test_repeating_bootstrap_keeps_single_identity_and_original_password` (mismo correo en mayúsculas y otra contraseña: una sola fila, hash intacto, contraseña original válida); `test_bootstrap_never_elevates_an_existing_operator`; `test_database_rejects_emails_differing_only_by_case`; `test_model_schema_enforces_case_insensitive_unique_email` (esquema creado desde el modelo) | PASS |

«Autenticarlo» en B04-UC01 se verifica por el hash Argon2id que acepta solo la contraseña original; el login HTTP llega en B05, como indica el ticket.

## TDD

| Comportamiento | Red observado | Green |
| --- | --- | --- |
| Aprovisionar y consultar admin activo | CLI stub con salida 0: `assert None is not None` (sin `reference:`) | Modelo, migración `0002`, hashing, `provision_admin`, CLI |
| Entrada inválida y repetición sin cambios | Sin Red propio: el Green anterior ya validaba entradas y existencia. Mutaciones de control: quitar `check_policy` → 4 fallos de TC02; sobrescribir hash/rol de la identidad existente → fallan los 2 tests de TC03. Mutaciones revertidas | — |
| Límites de la política | Sin Red propio (cubiertos por `check_policy`); se conservan como regresión de los límites 12/128 | — |

| Correcciones de review: tabla `identities`, NFKC, `\r\n`, unicidad sin mayúsculas en la DB | `13 failed, 8 passed` (tabla renombrada en los tests; NFKC, `\r\n` e índice `lower(email)` ausentes) | Renombre, `normalized()`, `rstrip("\r\n")`, índice funcional |
| Índice único del modelo (re-revisión) | Esquema desde el modelo: `UniqueViolation` al insertar un segundo correo distinto (`lower('email')` constante) | `Index(…, func.lower(Identity.email))` fuera de la clase |

Refactor con suite verde: registro `tappy.models` en lugar del import por efecto lateral en `env.py`; `migrated_database_url` en `conftest`; helpers `app_environment`/`run_identity` en `tests/support.py`.

## B04-VC01 — Resultado inicial del comando

DB local de Compose migrada a `0002_identity_identities`, sobre `da6e33f`:

```text
$ printf "<secreto sintético>\r\n" | python -m tappy.identity bootstrap-admin --email vc01-admin@tappy.example
Administrator provisioned
reference: 672260b7-2867-43e8-abcb-1582cfd9654b
email: vc01-admin@tappy.example
role: admin
status: active
exit=0

$ python -m tappy.identity show --email VC01-Admin@tappy.example
reference: 672260b7-2867-43e8-abcb-1582cfd9654b
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

$ python -m tappy.identity bootstrap-admin --email not-an-email < /dev/null   (falla antes de pedir contraseña)
Error: Invalid email: An email address must have an @-sign.
exit=1

$ psql: SELECT email, role, status, left(password_hash, 10) FROM identities
vc01-admin@tappy.example|admin|active|$argon2id$
```

Una sola identidad; ninguna salida contiene la contraseña. La fila de prueba se eliminó al terminar. Estado VC01: **PASS** (resultado inicial).

## Checks sobre `961ff31`

`uv run python -m quality.check`: format, lint, types, hygiene, migrations (con `0002` y `alembic check` sin drift), tests (`86 passed`), api (sin diferencias) en PASS; `evidence`: B01–B03 APPROVED, B04 bloqueado solo por review pendiente hasta cerrar el review.

## Umbral

AC PASS / AC aplicables = 3/3 = **100%**.

## Review Standards/Spec

Ronda 1 sobre `a5d7cb8`, sin bloqueantes; correcciones en `da6e33f`.

| Eje | Hallazgo | Resolución |
| --- | --- | --- |
| Spec | Preparación operativa: faltaba documentar duración/rotación de sesión | README «Session policy» con los valores acordados (B05/B06 los implementan) |
| Spec | «Autenticarlo» solo a nivel de hash | Aceptado: el ticket difiere el login a B05; documentado en Trazabilidad |
| Spec | `operator`/`inactive` aún sin flujo | Se conservan con justificación en Diseño (B05/B08) |
| Spec | `\r\n` por pipe; sin normalización Unicode | `rstrip("\r\n")`; NFKC en política, hash y verificación (Red/Green) |
| Spec | Cualquier `IntegrityError` se reportaba como «already exists» | Solo `UniqueViolation`; el resto se propaga |
| Spec | Unicidad de correo sensible a mayúsculas en la DB | Índice único `lower(email)` (Red/Green) |
| Spec | Contraseña pedida antes de validar el correo | Correo validado primero |
| Standards | Vocabulario `User`/«usuario» fuera del glosario | `CONTEXT.md`: Administrador e Identidad; modelo `Identity`, tabla `identities` |
| Standards | `MODELS` sin uso para mantener un import | `__all__` en `tappy.models` |
| Standards | Switch repetido de comandos en la CLI | `COMMANDS` + `set_defaults(handler=…)` |
| Standards | Mensaje de «already exists» duplicado; dos jerarquías de errores | `tappy.identity.errors` con base `IdentityError` |
| Standards | `enum_column` en el módulo de identidad | Movido a `platform/persistence` |
| Standards | Tuplas posicionales y `dispose` sin `finally` en tests | `StoredIdentity` (NamedTuple) y `try/finally` |
| Standards | `app_environment` no reutilizado | Reutilizado en `test_startup.py` |
| Standards | `except A, B:` con apariencia de Python 2 | Se conserva: sintaxis válida en Python 3.14 (PEP 758) y es la forma que deja Ruff format |

Re-revisión 1 sobre `bba374f`: bloqueante — el índice del modelo compilaba `lower('email')` (constante) y `alembic check` no compara índices de expresión; corregido en `961ff31` con Red/Green. No bloqueante: fila de `except A, B:` corregida a «se conserva».

Re-revisión 2 sobre `961ff31`: sin hallazgos pendientes en ambos ejes (índice compila a `lower(email)`, único índice, modelo y migración coinciden). Manifiesto aprobado.
