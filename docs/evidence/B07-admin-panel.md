# Evidencia — B07 Entrar y salir de Starlette Admin

Ticket: [#15](https://github.com/luisjrez/Tappy/issues/15) · Historia: [H2 #2](https://github.com/luisjrez/Tappy/issues/2) · Protocolo: [TICKET_QUALITY_PROTOCOL](../planning/TICKET_QUALITY_PROTOCOL.md) · Manifiesto: [B07-admin-panel.toml](B07-admin-panel.toml)

## Revisiones y escenario

- Ticket, UC/AC/TC y comprobación: B07-UC01–UC03, B07-AC01–AC03, B07-TC01–TC03, B07-VC01.
- Modalidad: **resultado inicial** (panel nuevo en `/admin`). La API existente no cambia de contrato: los 7 contratos de `api_snapshots` siguen sin diferencias.
- Base: rama B06 `4211fb9` (PR #57, stack nativo #54). Revisiones: candidato `da2dd79` → correcciones `4071ff8` → código final `31149bd` (rol no permitido sin renovación). Checks y tests corresponden a `31149bd`; las capturas y respuestas VC01 se tomaron sobre `da2dd79` y su comportamiento visible no cambió (las correcciones afectan a renovación, reutilización y rol en sesiones ya abiertas, cubiertos por tests).
- Entorno: macOS, Colima + Compose, Python 3.14.8, Starlette 1.10.0, starlette-admin 1.0.3. Navegador para capturas: Chrome (DevTools MCP), contexto aislado, viewport 1280×800, tema claro por defecto, escala 100 %. Fecha: 2026-11-20. Ejecutor: sesión local de desarrollo del autor del PR.
- Actores: administrador activo, operadora activa, anónimo. Datos: identidades sintéticas `vc01-…@tappy.example`.

## Diseño

- `tappy.backoffice.admin.mount_admin`: `BaseAdmin` de starlette-admin en `/admin` con `AdminAuthProvider` y `SessionMiddleware` (cookie `tappy_admin_session`, `HttpOnly`, `SameSite=Strict`, `Secure` según `TAPPY_ADMIN_SECURE_COOKIES`, por defecto `true`; `max_age` igual a la vida máxima de sesión).
- `AdminAuthProvider` (autenticación compartida con la API, sin reglas propias): `login` llama a `log_in(..., required_role=Role.ADMIN)` (operador o inactivo → mismo «Invalid email or password»); guarda access y refresh en la cookie firmada; `authenticate` usa el caso de uso de identidad `resume_session(..., Role.ADMIN)`, que valida el access, lo renueva con `renew_session` si expiró (la reutilización de un refresh ya rotado revoca la familia en transacción propia, igual que `POST /auth/refresh`) y exige el rol en cada petición; `logout` revoca la familia con `log_out`. Ante reutilización, rol o identidad no válidos se limpia la cookie; ante un refresh duplicado dentro de la ventana de gracia (peticiones concurrentes) solo se rechaza esa petición, sin cerrar la sesión vigente. Las operaciones de DB corren en el threadpool.
- CSRF: middleware de doble envío firmado de starlette-admin (cookie `starlette_admin_csrftoken` + campo `csrftoken`), activo para todo método no seguro bajo `/admin`, incluidos el login y el logout (`POST`).
- El logger de starlette-admin queda en `ERROR` para no registrar correos de intentos de login (registra `username` en INFO/WARNING); un test lo comprueba con `caplog`.
- Decisiones: la cookie CSRF de starlette-admin marca `Secure` según el esquema de la petición y usa `SameSite=Lax`; no es una credencial (token de doble envío, legible por JS por diseño). Detrás de un proxy TLS se ejecuta Uvicorn con cabeceras reenviadas (documentado en el README). `TAPPY_SECRET_KEY` firma tanto la cookie de sesión del panel como el CSRF; starlette-admin y `SessionMiddleware` usan salts/serializadores distintos.
- Presentación propia del panel (plantillas de starlette-admin); sin vistas de datos todavía (B08 añade operadores).

## Trazabilidad UC → AC → TC → test

| UC | AC | TC | Test real | Resultado |
| --- | --- | --- | --- | --- |
| B07-UC01 | B07-AC01 | B07-TC01 | `test_admin_enters_panel_and_logout_revokes_access` (login 303 → panel 200 con el correo → logout 303 → sin acceso; cero sesiones activas en DB); `test_panel_renews_expired_access_transparently`; `test_concurrent_panel_request_with_stale_cookie_keeps_current_session` | PASS |
| B07-UC02 | B07-AC02 | B07-TC02 | `test_anonymous_visitor_is_sent_to_login`; `test_operator_cannot_enter_panel`; `test_api_bearer_token_does_not_open_panel`; `test_revoked_panel_session_loses_access`; `test_demoted_or_deactivated_admin_loses_panel`; `test_demoted_admin_session_is_revoked_without_renewal`; `test_replayed_panel_cookie_revokes_the_whole_session`; `test_anonymous_logout_changes_nothing`; `test_failed_panel_login_keeps_emails_out_of_logs` | PASS |
| B07-UC03 | B07-AC03 | B07-TC03 | `test_logout_without_valid_csrf_is_rejected_without_changes` (sin token, forjado, alterado → 403, panel sigue accesible, sesión sin revocar); `test_login_without_csrf_is_rejected` (403, cero sesiones); `test_panel_cookie_flags_follow_environment` (`HttpOnly`, `SameSite=Strict`, `Secure` solo si está configurado) | PASS |

## TDD

| Comportamiento | Red | Green |
| --- | --- | --- |
| Admin entra y el logout revoca | Sin panel: `assert None is not None` (no hay token CSRF en `/admin/login`) | `mount_admin`, `AdminAuthProvider` |
| Operador rechazado | Retirando `Role.ADMIN` del login del panel: falla `test_operator_cannot_enter_panel` | `required_role` en `log_in` |
| Logout revoca la sesión | Logout sin revocar: falla `test_admin_enters_panel_and_logout_revokes_access` | `log_out` |
| Sesión revocada pierde acceso | Tratando como válida una sesión inválida: falla `test_revoked_panel_session_loses_access` | `find_access`/`renew` |
| CSRF en mutaciones | Permitiendo `POST` como método seguro en el middleware: fallan los 3 casos de logout y el de login sin CSRF | CSRF de starlette-admin activo |
| Cookie según entorno | `https_only=False` fijo: falla el caso `Secure=True`; `SameSite=lax`: fallan ambos casos | `https_only` desde la configuración, `SameSite=Strict` |
| Cookie vieja reutilizada revoca la sesión (review) | `assert active_sessions(...) == 0` fallaba: la familia seguía activa | `renew_session` (identidad) revoca en transacción propia; API y panel lo comparten |
| Rol exigido al reanudar, renovación en el panel, carrera con cookie vieja, logs sin correos (review) | Sin Red propio; mutaciones detectadas: sin rol al reanudar → falla `…demoted…[role]`; sin renovación → fallan 3 tests; limpiar cookie ante refresh duplicado → falla `…stale_cookie…`; logger en DEBUG → falla `…keeps_emails_out_of_logs` | `resume_session`, `current_summary` |

Los tests de TC02/TC03 pasaron a la primera porque el comportamiento lo aporta el Green de TC01 y el CSRF de starlette-admin; el Red se observó retirando temporalmente cada comportamiento y restaurándolo (todos revertidos). Una primera mutación de CSRF fue inválida (faltaba el import) y se repitió correctamente.

Refactor con suite verde: `LoginCredentials` también en `find_active_identity`; `SessionTokens` congelado sustituye a la clase mutable del panel; el panel no tiene reglas de identidad propias; tests con helpers de CSRF parametrizados, estados exactos (303) y `active_sessions`.

## B07-VC01 — Resultado inicial del panel

Capturas del recorrido (servidor real `python -m tappy`, `TAPPY_ADMIN_SECURE_COOKIES=false` por HTTP local):

| Vista / rol / TC | Captura | Comprobación |
| --- | --- | --- |
| `/admin/` anónimo → login (TC02) | ![Anónimo redirigido al login](B07/01-anonimo-redirige-a-login.png) | Redirección a `/admin/login?next=…`; formulario sin datos administrativos |
| Login de operadora (TC02) | ![Operadora rechazada](B07/02-operadora-rechazada.png) | Alerta «Invalid email or password»; contraseña oculta |
| Admin dentro del panel (TC01) | ![Admin en el panel](B07/03-admin-en-panel.png) | Identidad real `vc01-admin@tappy.example` en el menú; «No data views are available» (sin vistas aún) |
| `/admin/` tras pulsar Logout (TC01) | ![Sin acceso tras logout](B07/04-tras-logout-sin-acceso.png) | De vuelta al login; en DB `activas=0` de 1 sesión |

Respuestas HTTP con una sesión de admin válida (cookies y tokens redactados):

```text
GET  /admin/                               → 200
POST /admin/logout (sin csrftoken)         → 403 "CSRF token missing"
POST /admin/logout (csrftoken alterado)    → 403 "CSRF token invalid"
GET  /admin/ tras los intentos rechazados  → 200 (la sesión sigue activa: sin cambios)
Set-Cookie: tappy_admin_session=<redactado>; path=/; Max-Age=2592000; httponly; samesite=strict
```

En local la cookie no lleva `Secure` porque `TAPPY_ADMIN_SECURE_COOKIES=false`; con el valor por defecto (`true`) sí (test parametrizado). El log del servidor no contiene correos ni contraseñas (0 coincidencias). Teclado/foco: el formulario de login se completó y envió por su árbol de accesibilidad (campos «Username», «Password», botón «Sign in»); no se cambiaron interacciones propias. Datos de prueba eliminados al terminar. Estado VC01: **PASS** (resultado inicial).

## Checks sobre `31149bd`

`uv run python -m quality.check`: format, lint, types, hygiene, migrations, tests, api (7 contratos sin diferencias) en PASS; `evidence` bloquea B07 solo hasta aprobar el review.

## Supresiones

Sin supresiones nuevas.

## Umbral

AC PASS / AC aplicables = 3/3 = **100%**.

## Review Standards/Spec

Ronda 1 sobre `da2dd79`; correcciones en `4071ff8`.

| Eje | Hallazgo | Resolución |
| --- | --- | --- |
| Standards | Reutilización de refresh desde la cookie del panel no revocaba la familia (permisos, bloqueante) | `renew_session` en identidad con revocación en transacción propia; API y panel lo usan (Red/Green) |
| Standards | Regla de rol al reanudar fuera de identidad (Feature Envy) | `resume_session(..., required_role)` en identidad |
| Standards | `find_active_identity` con correo/contraseña sueltos | Recibe `LoginCredentials` |
| Standards | `PanelCredentials` mutable | `SessionTokens` congelado |
| Standards | Flujo redundante en `logout` | `contextlib.suppress` |
| Standards | `setLevel` global sin test de logs | Test con `caplog` + mutación |
| Standards | Ternario anidado, `!= 200` y consulta duplicada en tests | Funciones parametrizadas, 303 exacto, `active_sessions` |
| Standards | `SessionPolicy.from_settings` en router y panel; secreto único | Se conservan: un solo constructor de política; salts distintos (documentado) |
| Spec | Renovación del panel sin test | `test_panel_renews_expired_access_transparently` + mutación |
| Spec | Rol revisado en sesión existente y admin desactivado sin test | `test_demoted_or_deactivated_admin_loses_panel` + mutación |
| Spec | Rutas internas sin anónimo | `test_anonymous_logout_changes_nothing` (y la cookie vieja reutilizada) |
| Spec | Renovación concurrente podía cerrar la sesión del admin | Refresh duplicado dentro de la gracia solo rechaza la petición; test + mutación |
| Spec | Cookie CSRF no sigue `TAPPY_ADMIN_SECURE_COOKIES` | Decisión documentada: no es credencial; `Secure` según esquema con cabeceras reenviadas del proxy |

Re-revisión sobre `4071ff8`: sin bloqueantes; fix de reutilización resuelto (sin lock entre transacciones; `/auth/refresh` igual o más estricto). Nit: un admin degradado con access válido disparaba una renovación antes del rechazo y la familia seguía activa. Corregido en `31149bd` con Red/Green (`RoleNotAllowedError`: el panel revoca la sesión sin renovar; `assert 2 == 0` → verde). Ambos ejes aprobados; manifiesto aprobado.
