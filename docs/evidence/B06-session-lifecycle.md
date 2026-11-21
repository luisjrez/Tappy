# Evidencia — B06 Expirar, renovar y revocar sesiones

Ticket: [#14](https://github.com/luisjrez/Tappy/issues/14) · Historia: [H2 #2](https://github.com/luisjrez/Tappy/issues/2) · Protocolo: [TICKET_QUALITY_PROTOCOL](../planning/TICKET_QUALITY_PROTOCOL.md) · Manifiesto: [B06-session-lifecycle.toml](B06-session-lifecycle.toml)

## Revisiones y escenario

- Ticket, UC/AC/TC y comprobación: B06-UC01–UC03, B06-AC01–AC03, B06-TC01–TC03, B06-VC01.
- Modalidad: **comparación** para `POST /auth/login` (contrato existente de B05 que se amplía) y **resultado inicial** para `POST /auth/refresh`, `POST /auth/logout` y el comando `deactivate`. Panel no aplica (B07).
- Base: rama B05 `e223b5e` (PR #56, stack nativo #54); evidencia aprobada de B05 como base de comparación. Revisiones: candidato `eff5ce6` → correcciones `1093101` → lock por familia `3a07302` → código final `4211fb9` (lock de identidad compatible). Checks y tests corresponden a `4211fb9`; el recorrido VC01 se capturó sobre `eff5ce6` y su comportamiento visible no cambió (las correcciones afectan a carreras concurrentes y a logout con access expirado, cubiertos por tests).
- Entorno: macOS, Colima + Compose, Python 3.14.8. Fecha: 2026-11-20. Ejecutor: sesión local de desarrollo del autor del PR.
- Actor: operador autenticado. Datos: identidades sintéticas; tokens redactados.

## Diseño

- Política acordada: access 15 min, renovación con rotación atómica, vida máxima absoluta de 30 días desde el login (`TAPPY_SESSION_MAX_LIFETIME_SECONDS`, mínimo 3600), concentrada en `SessionPolicy.from_settings`.
- Familia de sesión: cada login crea una familia (`family_id`, `family_expires_at`); cada renovación añade una fila nueva a la misma familia y marca la anterior con `rotated_at`. Migración `0004` (invalida las sesiones existentes al actualizar: eran de 15 minutos y no tenían refresh).
- `renew`: un único `UPDATE … WHERE refresh_digest = … AND revoked_at IS NULL AND rotated_at IS NULL AND family_expires_at > now AND identidad activa RETURNING …`; la fila bloqueada garantiza que dos renovaciones concurrentes no emitan dos sesiones. Si el refresh ya fue rotado hace más de 10 s (`SessionPolicy.reuse_grace`) es reutilización: `RefreshTokenReuseError`, y el router revoca la familia en **su propia transacción** antes de responder 401 (la transacción de la petición se revierte con la excepción). Dentro de la ventana es una renovación concurrente duplicada: solo falla, sin revocar al ganador.
- Serialización por familia: `renew` y `revoke_family` toman `pg_advisory_xact_lock` sobre la familia. Así un logout o una revocación concurrente con una renovación espera a que esta confirme y revoca también la sesión recién emitida (bajo READ COMMITTED, sin el lock el `UPDATE` de revocación no veía la fila nueva). La reutilización se detecta antes de tomar el lock, para que su revocación en transacción propia no espere un lock que retiene la propia petición.
- `deactivate_identity` bloquea la identidad con `FOR NO KEY UPDATE` (`with_for_update(key_share=True)`): cambia solo `status`, así que no necesita `FOR UPDATE`, y no choca con el `FOR KEY SHARE` que toma la clave foránea al insertar una sesión durante una renovación concurrente (con `FOR UPDATE` había deadlock).
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
| B06-UC03 | B06-AC03 | B06-TC03 | `test_logged_out_session_is_not_revived_by_renewal`; `test_deactivated_identity_loses_access_and_renewal` (access, refresh y nuevo login rechazados); `test_logout_with_expired_access_token_still_revokes_the_session`; `test_logout_racing_a_renewal_also_revokes_the_renewed_session` (carrera: renovación sin confirmar + logout concurrente); `test_locking_an_identity_for_deactivation_does_not_block_new_sessions`; `test_token_stops_working_when_identity_becomes_inactive` | PASS |

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
| Logout concurrente con renovación (re-revisión) | El access de la sesión renovada seguía respondiendo 200 tras el logout: `assert 200 == 401` | `lock_family` en `renew` y `revoke_family`; sin el lock en `revoke_family` el test vuelve a fallar |
| Desactivación concurrente con renovación (re-revisión 2) | Con el lock de desactivación retenido, insertar la sesión renovada esperaba: `LockNotAvailable … lock timeout`; reproducción del revisor: `{'deact': 'DeadlockDetected', 'renew': 'ok'}` | `FOR NO KEY UPDATE`; reproducción: `{'renew': 'ok', 'deact': 'ok'}` |

En las filas «Vida máxima», «Access anterior inválido tras rotar», «Reutilización revoca la sesión» y «Logout revoca» el Red se observó retirando temporalmente el comportamiento ya implementado (el test falla por la ausencia del comportamiento, no por instalación ni sintaxis) y restaurándolo después; el resto tuvo Red antes de implementar.

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

## Checks sobre `4211fb9`

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

Re-revisión 1 sobre `1093101`: Standards sin pendientes; Spec, hallazgo de baja severidad: logout/revocación concurrente con una renovación podía dejar viva la sesión nueva (READ COMMITTED). Corregido en `3a07302` con Red/Green (lock consultivo por familia). Durante la corrección, tomar el lock antes de detectar la reutilización provocaba que la revocación en transacción propia esperara el lock de la propia petición (la suite se colgó); se resolvió detectando la reutilización antes del lock.

Re-revisión 2 sobre `3a07302`: lock por familia correcto, sin auto-deadlock; Standards sin pendientes (nit: el test de carrera usa `sleep(0.5)` para ordenar hilos; si el orden falla pasa sin ejercitar la carrera, nunca falla en falso). Spec, baja severidad y previo: deadlock entre `deactivate` (`FOR UPDATE`) y la inserción de la sesión renovada (FK). Corregido en `4211fb9` con Red/Green.

Re-revisión 3 sobre `4211fb9`: sin hallazgos pendientes en ambos ejes (desactivaciones concurrentes siguen serializadas; sin vía de reactivación; test significativo). Nit de redacción de la tabla TDD corregido. Manifiesto aprobado.
