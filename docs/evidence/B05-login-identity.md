# Evidencia — B05 Iniciar sesión y consultar identidad

Ticket: [#13](https://github.com/luisjrez/Tappy/issues/13) · Historia: [H2 #2](https://github.com/luisjrez/Tappy/issues/2) · Protocolo: [TICKET_QUALITY_PROTOCOL](../planning/TICKET_QUALITY_PROTOCOL.md) · Manifiesto: [B05-login-identity.toml](B05-login-identity.toml)

## Revisiones y escenario

- Ticket, UC/AC/TC y comprobación: B05-UC01–UC03, B05-AC01–AC03, B05-TC01–TC03, B05-VC01.
- Modalidad: **resultado inicial** (endpoints nuevos `POST /auth/login` y `GET /auth/me`). Bases existentes (`health`, `ready-*`) sin diferencias. Panel no aplica (B07).
- Base: rama B04 (PR #55, stack nativo #54). Revisión evaluada: candidato `7476af9`.
- Entorno: macOS, Colima + Compose, Python 3.14.8. Fecha: 2026-11-20. Ejecutor: sesión local de desarrollo del autor del PR.
- Actor: operador o administrador activo. Datos: identidades y frases de paso sintéticas.

## Diseño

- Política acordada: token opaco (`secrets.token_urlsafe(32)`), vida de 15 min configurable con `TAPPY_ACCESS_TOKEN_TTL_SECONDS` (mínimo 60). La renovación con rotación y la vida máxima de 30 días llegan en B06.
- `access_sessions` (migración `0003`): `identity_id`, `token_digest` SHA-256 único (el token bruto nunca se guarda), `created_at`, `expires_at`, `revoked_at` (revocación en B06).
- `tappy.identity.sessions`: `log_in` (error genérico `Invalid email or password` para correo inexistente o inválido, contraseña incorrecta o identidad inactiva; verifica contra un hash de igualación cuando el correo no existe para un tiempo de respuesta comparable) y `resolve_identity` (token desconocido, revocado, expirado o identidad inactiva → no autorizado).
- `tappy.identity.dependencies.CurrentIdentity`: dependencia única de identidad por `Authorization: Bearer`, independiente del panel. 401 con `WWW-Authenticate: Bearer`.
- DTOs Pydantic `SessionResponse` (`access_token`, `token_type`, `expires_at`) e `IdentityResponse` (`reference`, `email`, `role`, `status`); nunca exponen hash ni digest.
- `Clock` sustituible (`create_app(settings, clock=…)`), usado por los tests de expiración.
- Contratos de API nuevos con base aprobada en `7476af9`: `login-rejected` (401) y `me-unauthenticated` (401).

## Trazabilidad UC → AC → TC → test

| UC | AC | TC | Test real | Resultado |
| --- | --- | --- | --- | --- |
| B05-UC01 | B05-AC01 | B05-TC01 | `test_active_operator_logs_in_and_reads_own_identity` (200 con identidad correcta; DTO sin contraseña ni token); `test_only_a_digest_of_the_token_is_stored` | PASS |
| B05-UC02 | B05-AC02 | B05-TC02 | `test_rejected_logins_share_one_generic_error_and_create_no_session` (contraseña incorrecta, identidad inactiva, correo inexistente, correo inválido: mismo 401 y mensaje; cero sesiones) | PASS |
| B05-UC03 | B05-AC03 | B05-TC03 | `test_requests_without_valid_token_are_rejected` (sin token, alterado, esquema `Basic`); `test_each_token_only_reveals_its_own_identity` (token ajeno con `?email=`/`?reference=` de otra identidad: solo devuelve la propia); `test_expired_token_is_rejected` (14:59 → 200, 15:00 → 401) | PASS |

## TDD

| Comportamiento | Red observado | Green |
| --- | --- | --- |
| Login y `/auth/me` | Sin ruta: `KeyError: 'access_token'` | Modelo `AccessSession`, migración `0003`, `log_in`/`resolve_identity`, router `/auth` |
| Rechazos genéricos, token inválido/ajeno/expirado | Sin Red propio (el Green de TC01 incluyó la resolución completa). Mutaciones de control: permitir login de inactivo → falla TC02[inactive]; quitar la expiración → falla `test_expired_token_is_rejected`; mensaje distinto para correo inexistente → fallan TC02[inexistente] y TC02[inválido]. Mutaciones revertidas | — |

Refactor con suite verde: `CurrentIdentity` movida a `identity/dependencies.py` (sin acoplar al router ni al panel); helpers `create_identity` y `MovableClock` en `tests/support.py`.

## B05-VC01 — Resultado inicial de API

Proceso real `python -m tappy` contra la DB local migrada a `0003`, administrador sintético provisionado con `bootstrap-admin`:

| Petición | Status | Cuerpo |
| --- | --- | --- |
| `POST /auth/login` válido | 200 | `{"access_token": "<redactado: 43 caracteres>", "token_type": "bearer", "expires_at": "2026-11-21T00:24:56.280311Z"}` |
| `GET /auth/me` con `Bearer <token>` | 200 | `{"reference":"4f0d81d7-822f-41eb-a34c-da3ac43dfa2b","email":"vc01-admin@tappy.example","role":"admin","status":"active"}` |
| `POST /auth/login` contraseña incorrecta | 401 | `{"detail":"Invalid email or password"}` |
| `POST /auth/login` correo inexistente | 401 | `{"detail":"Invalid email or password"}` |
| `GET /auth/me` sin token | 401 · `www-authenticate: Bearer` | `{"detail":"Not authenticated"}` |
| `GET /auth/me` token alterado | 401 | `{"detail":"Not authenticated"}` |

El log del servidor no contiene el token ni la contraseña (0 coincidencias). Datos de prueba eliminados al terminar. `api_snapshots`: `login-rejected` y `me-unauthenticated` sin diferencias contra su base. Estado VC01: **PASS**.

## Checks

Pendiente de registrar sobre la revisión final.

## Umbral

AC PASS / AC aplicables = 3/3 = **100%**.

## Review Standards/Spec

Pendiente.
