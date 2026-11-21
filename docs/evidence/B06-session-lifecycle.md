# Evidencia — B06 Expirar, renovar y revocar sesiones

Ticket: [#14](https://github.com/luisjrez/Tappy/issues/14) · Historia: [H2 #2](https://github.com/luisjrez/Tappy/issues/2) · Protocolo: [TICKET_QUALITY_PROTOCOL](../planning/TICKET_QUALITY_PROTOCOL.md) · Manifiesto: [B06-session-lifecycle.toml](B06-session-lifecycle.toml)

## Revisiones y escenario

- Ticket, UC/AC/TC y comprobación: B06-UC01–UC03, B06-AC01–AC03, B06-TC01–TC03, B06-VC01.
- Modalidad: **comparación** para `POST /auth/login` (contrato existente de B05 que se amplía) y **resultado inicial** para `POST /auth/refresh`, `POST /auth/logout` y el comando `deactivate`. Panel no aplica (B07).
- Base: rama B05 `e223b5e` (PR #56, stack nativo #54); evidencia aprobada de B05 como base de comparación. Revisiones: candidato `eff5ce6` → código final `1093101` (correcciones de review). Checks y tests corresponden a `1093101`; el recorrido VC01 se capturó sobre `eff5ce6` y su comportamiento visible no cambió (las correcciones afectan a carreras concurrentes y a logout con access expirado, cubiertos por tests).
- Entorno: macOS, Colima + Compose, Python 3.14.8. Fecha: 2026-11-20. Ejecutor: sesión local de desarrollo del autor del PR.
- Actor: operador autenticado. Datos: identidades sintéticas; tokens redactados.

## Diseño

- Política acordada: access 15 min, renovación con rotación atómica, vida máxima absoluta de 30 días desde el login (`TAPPY_SESSION_MAX_LIFETIME_SECONDS`, mínimo 3600), concentrada en `SessionPolicy.from_settings`.
- Familia de sesión: cada login crea una familia (`family_id`, `family_expires_at`); cada renovación añade una fila nueva a la misma familia y marca la anterior con `rotated_at`. Migración `0004` (invalida las sesiones existentes al actualizar: eran de 15 minutos y no tenían refresh).
- `renew`: un único `UPDATE … WHERE refresh_digest = … AND revoked_at IS NULL AND rotated_at IS NULL AND family_expires_at > now AND identidad activa RETURNING …`; la fila bloqueada garantiza que dos renovaciones concurrentes no emitan dos sesiones. Si el refresh ya fue rotado hace más de 10 s (`SessionPolicy.reuse_grace`) es reutilización: `RefreshTokenReuseError`, y el router revoca la familia en **su propia transacción** antes de responder 401 (la transacción de la petición se revierte con la excepción). Dentro de la ventana es una renovación concurrente duplicada: solo falla, sin revocar al ganador.
- Decisiones de alcance: la detección de reutilización aplica «no revive una sesión revocada» a un refresh robado/reenviado (práctica de OAuth 2.0 Security BCP); el comando `deactivate` es la interfaz operativa mínima para B06-UC03 hasta la gestión desde API/panel de B08; la migración `0004` borra las sesiones existentes (access de 15 min sin refresh) al actualizar.
- `is_usable`: un access token deja de autorizar si está revocado, rotado, expirado o su identidad está inactiva.
- `POST /auth/logout` revoca la familia completa (204); acepta un access token expirado pero nunca uno rotado o revocado, para que cerrar sesión tarde no deje vivo el refresh. `python -m tappy.identity deactivate --email …` marca la identidad inactiva y revoca todas sus sesiones (la gestión desde API/panel llega en B08).
- Reloj sustituible (`MovableClock` en tests) para límites de expiración.
- Contratos nuevos con base aprobada en `eff5ce6`: `refresh-rejected` y `logout-unauthenticated` (401).

## Trazabilidad UC → AC → TC → test

| UC | AC | TC | Test real | Resultado |
| --- | --- | --- | --- | --- |
| B06-UC01 | B06-AC01 | B06-TC01 | `test_renewal_issues_working_tokens_and_retires_the_previous_pair`; `test_expired_access_token_can_be_renewed_within_the_session_lifetime` | PASS |
| B06-UC02 | B06-AC02 | B06-TC02 | `test_session_cannot_be_renewed_past_its_absolute_lifetime` (29 renovaciones diarias; día 30 → refresh y `/auth/me` 401); `test_reused_refresh_token_fails_and_revokes_the_whole_session`; `test_logged_out_session_is_not_revived_by_renewal`; `test_concurrent_renewals_keep_exactly_one_working_session` (exactamente un éxito y el par ganador funciona); `test_expired_token_is_rejected`; `test_revoked_session_is_rejected` | PASS |
| B06-UC03 | B06-AC03 | B06-TC03 | `test_logged_out_session_is_not_revived_by_renewal`; `test_deactivated_identity_loses_access_and_renewal` (access, refresh y nuevo login rechazados); `test_logout_with_expired_access_token_still_revokes_the_session`; `test_token_stops_working_when_identity_becomes_inactive` | PASS |

## TDD

| Comportamiento | Red observado | Green |
| --- | --- | --- |
| Renovación que retira el par anterior | `KeyError: 'refresh_token'` | Familia de sesión, `renew` con `UPDATE … RETURNING`, `rotated_at` en `is_usable`, `POST /auth/refresh` |
| Contrato de login ampliado | El test de B05 que fija los campos falla: `Extra items in the left set: 'refresh_token', 'refresh_expires_at'` | Test de B05 actualizado al contrato nuevo (cambio aditivo, ver VC01) |
| Desactivación | `invalid choice: 'deactivate'` | `deactivate_identity` + comando |
| Vida máxima | Retirando la condición `family_expires_at > now` de la renovación: falla `…absolute_lifetime` | Condición restaurada |
| Access anterior inválido tras rotar | Retirando `rotated_at IS NULL` de la validación del access: falla `…retires_the_previous_pair` | Condición restaurada |
| Reutilización revoca la sesión | Sin revocar ante reutilización: falla `…reused…`; revocando dentro de la transacción de la petición (que se revierte con el 401): falla `…reused…` | Revocación en transacción propia |
| Logout revoca | Logout sin revocar: falla `…logged_out…` | `revoke_family` |
| Renovación concurrente conserva un ganador (review) | Test endurecido: `assert len(successes) == 1` fallaba porque el perdedor revocaba al ganador | Ventana de gracia `reuse_grace`; con gracia 0 el test vuelve a fallar |
| Logout con access expirado (review) | `logout.status_code == 401` en lugar de 204 | `find_access(..., allow_expired=True)` |

En las cuatro primeras filas el Red se observó retirando temporalmente el comportamiento ya implementado (el test falla por la ausencia del comportamiento, no por instalación ni sintaxis) y restaurándolo después; las dos últimas tuvieron Red antes de implementar.

Refactor con suite verde: `SessionPolicy` y `SessionFamily`; `find_access` compartido por `resolve_identity` y `log_out`; `revoke_sessions` común a familia e identidad; `issue_session`; errores homogéneos por excepción (`InvalidRefreshTokenError`, `RefreshTokenReuseError`).

## B06-VC01 — API inicial y comparación de login

`POST /auth/login`, mismo actor y escenario que la evidencia aprobada de B05:

| Campo | B05 (base aprobada) | B06 (actual) | Clasificación |
| --- | --- | --- | --- |
| `access_token` | presente (opaco) | presente (opaco) | sin cambio |
| `token_type` | `"bearer"` | `"bearer"` | sin cambio |
| `expires_at` | login + 15 min | login + 15 min | sin cambio |
| `refresh_token` | ausente | presente (opaco) | aditiva compatible |
| `refresh_expires_at` | ausente | login + 30 días | aditiva compatible |

Efecto en consumidores: ninguno incompatible; los clientes que ignoran campos extra siguen funcionando. Los 401 genéricos de login no cambian (`login-rejected` sin diferencias).

Recorrido real (proceso `python -m tappy`, DB local en `0004`; tokens redactados):

| Paso | Resultado |
| --- | --- |
| `POST /auth/login` | 200 · `{"access_token":"<redactado>","token_type":"bearer","expires_at":"2026-11-21T00:38:23.497683Z","refresh_token":"<redactado>","refresh_expires_at":"2026-12-21T00:23:23.497683Z"}` |
| `POST /auth/refresh` con refresh vigente | 200 · nuevo par; `refresh_expires_at` igual al del login |
| `GET /auth/me` con access nuevo / anterior | 200 / 401 |
| `POST /auth/refresh` reutilizando el refresh anterior | 401 `{"detail":"Invalid refresh token"}`; después el access nuevo → 401 |
| `POST /auth/logout` → `GET /auth/me` → `POST /auth/refresh` | 204 → 401 → 401 |
| `python -m tappy.identity deactivate --email vc01-admin@tappy.example` → `GET /auth/me` | `status: inactive` → 401 |

El log del servidor no contiene tokens (0 coincidencias). Datos de prueba eliminados al terminar. Estado VC01: **PASS** (diferencias de login esperadas y aditivas; recorrido inicial conforme).

## Checks sobre `1093101`

`uv run python -m quality.check`: format, lint, types, hygiene, migrations (`0004` sin drift), tests, api (7 contratos sin diferencias) en PASS; `evidence` bloquea B06 solo hasta aprobar el review.

## Supresiones

Sin supresiones nuevas.

## Umbral

AC PASS / AC aplicables = 3/3 = **100%**.

## Review Standards/Spec

Ronda 1 sobre `eff5ce6`; correcciones en `1093101`.

| Eje | Hallazgo | Resolución |
| --- | --- | --- |
| Spec | Logout con access expirado dejaba vivo el refresh | `allow_expired` en logout (Red/Green) |
| Spec | Renovación concurrente: el perdedor revocaba al ganador; test aceptaba 0 éxitos | Ventana de gracia; test exige un éxito y par ganador funcional (Red/Green) |
| Spec | TC02 sin consultar identidad tras la vida máxima | `/auth/me` → 401 añadido |
| Spec | Reutilización, `deactivate` y migración destructiva fuera de lo pedido | Decisiones de alcance registradas en Diseño |
| Standards | TDD sin Red propio en cuatro comportamientos (bloqueante) | Red observado retirando el comportamiento; registrado en la tabla TDD |
| Standards | Commit de la revocación en 401 dependía de devolver `JSONResponse` | Revocación en transacción propia + excepciones homogéneas; mutación demuestra que el test lo detecta |
| Standards | `revoke_family`/`revoke_identity_sessions` duplicados | `revoke_sessions(scope)` |
| Standards | `issue` poco descriptivo; test sin el helper `refresh` | `issue_session`; helper usado |
| Standards | Migración `0004` destructiva | Aceptada antes de producción; registrada |
| Standards | `SessionPolicy.from_settings` acopla a `Settings` | Se conserva: coherente con la organización modular |

Re-revisión: pendiente.
