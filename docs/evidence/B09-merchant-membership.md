# Evidencia — B09 Configurar comercio y membresía

Ticket: [#17](https://github.com/luisjrez/Tappy/issues/17) · Historia: [H3 #3](https://github.com/luisjrez/Tappy/issues/3) · Protocolo: [TICKET_QUALITY_PROTOCOL](../planning/TICKET_QUALITY_PROTOCOL.md) · Manifiesto: [B09-merchant-membership.toml](B09-merchant-membership.toml)

## Revisiones y escenario

- Ticket, UC/AC/TC y comprobación: B09-UC01–UC03, B09-AC01–AC03, B09-TC01–TC03, B09-VC01.
- Modalidad: **resultado inicial** (API `/merchants` y vista «Merchants» nuevas). Contratos existentes sin diferencias; nuevo `merchants-unauthenticated` (401) aprobado en `7758b73`. El menú del panel suma «Merchants» (cambio esperado de navegación).
- Base: rama B08 `8610294` (PR #59) en el stack principal #54. Revisión evaluada: candidato `7758b73`.
- Entorno: macOS, Colima + Compose, Python 3.14.8; Chrome (DevTools MCP), 1280×800 (capturas de página completa). Fecha: 2026-11-20. Ejecutor: sesión local de desarrollo del autor del PR.
- Datos: comercios «Tienda Demo A/B» y operadores sintéticos.

## Diseño

- `tappy.merchants`: `Merchant` y `Membership` (único por comercio+identidad), migración `0005_merchants_memberships` (sobre `0004`; el stack lateral de B41/B42 también parte de `0004` y deberá reencadenar su `0005` al integrarse).
- Autorización centralizada por pertenencia (`scoped`/`accessible_merchant`): administradores ven todo; operadores solo comercios con membresía. Fuera de alcance → `404` («Merchant not found»), sin revelar existencia. Los IDs en ruta o query no amplían el alcance.
- API: `GET /merchants`, `GET /merchants/{id}` (identidad activa, acotado); `POST /merchants`, `PATCH /merchants/{id}`, `POST /merchants/{id}/members` solo admin (`403` operador, `401` anónimo). Asignación idempotente: repetir → `200` con la membresía original intacta (comprobación previa + restricción única con savepoint para carreras). Solo operadores activos son asignables (`422`).
- Panel: vista propia «Merchants» (sin CRUD genérico) para crear comercios y asignar operadores activos; CSRF y POST→redirect→GET con mensajes flash.

## Trazabilidad UC → AC → TC → test

| UC | AC | TC | Test real | Resultado |
| --- | --- | --- | --- | --- |
| B09-UC01 | B09-AC01 | B09-TC01 | `test_operator_sees_only_the_merchant_it_belongs_to` (con dos comercios, la operadora A solo ve A con su membresía una vez); `test_own_merchant_is_readable_and_anonymous_gets_nothing`; `test_admin_creates_merchant_and_assigns_operator_from_panel` | PASS |
| B09-UC02 | B09-AC02 | B09-TC02 | `test_operator_cannot_read_or_modify_a_foreign_merchant` (GET B → 404, PATCH B → 403, unirse a B → 403, `?merchant_id=B` no amplía; B sin cambios); `test_merchant_form_requires_csrf_and_an_admin` | PASS |
| B09-UC03 | B09-AC03 | B09-TC03 | `test_repeated_assignment_keeps_one_original_membership` (201 → 200, una fila, `created_at` original); `test_only_active_operators_can_be_assigned` | PASS |

## TDD

| Comportamiento | Red | Green |
| --- | --- | --- |
| Alta, asignación y listado acotado | `assert 404 == 201` | Modelos, migración, servicio, router |
| Vista del panel | Formulario inexistente: falla el alta desde el panel | `MerchantsView` + plantilla |
| Aislamiento y permisos | Sin Red propio (aportados por el Green). Mutaciones: operador ve todos → fallan TC01 y TC02; `PATCH` sin `ADMIN_ONLY` → falla TC02 | `visible_to`, `ADMIN_ONLY` |
| Idempotencia | Quitar la comprobación previa no rompe: la restricción única con savepoint garantiza igualmente una sola fila (defensa en profundidad) | — |

Refactor con suite verde: el panel usa `list_all_merchants` en lugar de un actor sintético; mapeo de errores compartido en el router.

## B09-VC01 — Resultado inicial de API y panel

API (proceso real, DB en `0005_merchants_memberships`):

| Petición | Status | Resultado |
| --- | --- | --- |
| `POST /merchants/{A}/members` (admin, operador A) | 201 | `{"name":"Tienda Demo A","members":[{"email":"vc01-operador-a@tappy.example",…}]}` |
| Mismo POST repetido | 200 | Sin duplicado |
| `GET /merchants` (operador A) | 200 | Solo «Tienda Demo A» |
| `GET /merchants/{B}` (operador A) | 404 | `{"detail":"Merchant not found"}` |
| `PATCH /merchants/{B}` (operador A) | 403 | `{"detail":"Administrator role required"}` |
| `GET /merchants` (admin) | 200 | `[("Tienda Demo A", 1), ("Tienda Demo B", 0)]` |

Panel (`/admin/merchants`):

| Vista | Captura | Comprobación |
| --- | --- | --- |
| Asignar operador B a la Tienda B | ![Asignado](B09/01-operador-asignado.png) | «Operator assigned»; cada comercio muestra solo sus operadores |
| Repetir la asignación del operador A | ![Repetido](B09/02-asignacion-repetida.png) | «That operator is already a member»; sin duplicados |

Datos de prueba eliminados al terminar. Estado VC01: **PASS** (resultado inicial).

## Checks

Pendiente de registrar sobre la revisión final.

## Supresiones

Sin supresiones nuevas.

## Umbral

AC PASS / AC aplicables = 3/3 = **100%**.

## Review Standards/Spec

Pendiente.
