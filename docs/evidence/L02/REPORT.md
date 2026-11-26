# L02 — base Astro (en curso)

Base de revisión: d39aac3995130904e0a71247f61ef3741dc3eaa0.
Ticket: #94. Rama: t3/landing-l02; PR base previsto: t3/plan-landing-page-work.

El usuario autorizó continuar con PRs apilados sin integrar #108. L01 permanece abierto; esta excepción permite desarrollar dependencias, no simula aprobación humana ni autoriza merges.

Fronteras aprobadas: build estático y HTTP local, navegación sin JavaScript y 404.
Evidencia: resultado inicial. Implementación mínima y capturas iniciales verificadas; no hay declaración de fidelidad a Pencil todavía.

Entorno: macOS 26.6.2 (25G83) arm64, Node 22.23.4 mediante npm exec, npm 10.9.2; Astro 7.4.13. Ejecutor: agente Codex. Fecha: 2026-11-25 local.

## Ejecución incremental

- L02-TC01 RED: HTTP 200 y HTML válido, fallo esperado de título (`Base` en lugar de Tappy).
- L02-TC01 GREEN: `npx --yes --package=node@22.23.4 -c 'npm test'`, 1 test aprobado, código 0.
- L02-TC02 RED: heading principal ausente; GREEN: contenido y navegación por ancla sin JavaScript, 2 tests aprobados. Chromium instalado: 159.0.8154.6, Playwright 1.65.1.
- L02-TC03 RED: heading genérico 404 en inglés; implementación de página española con regreso al inicio añadida. GREEN: status 404, mensaje y regreso al inicio aprobados.

Astro 7 detecta ejecución por agente y lanza preview en segundo plano. El servidor de pruebas usa `--ignore-lock` y puerto 4394 para que Playwright controle su ciclo de vida. Se detuvo el servidor inicial creado por Astro.

Checks: Astro check sin errores/advertencias; formato aprobado; build estático aprobado; 6 pruebas Playwright aprobadas (3 TC y 3 escenarios de capturas). AC funcionales: 3/3 (100%) en entorno local. VC01: capturas iniciales en 360×800, 768×1024 y 1440×900 para raíz y 404. HTML mínimo sin estilo: la fidelidad de las secciones se implementa en L04–L09, no se declara aquí. Reviews: pendientes.

## Revisión y trazabilidad

Código evaluado: `1977dcda7064123bfee280a6b89fedaafb904316`. Comandos desde `apps/landing`, con Node 22.23.4: `npm ci`, `npm run check`, `npm run format:check`, `npm test`, `npm run build`. Todos terminaron con código 0. `npm test` construye de nuevo antes de servir HTTP local. Los datos son textos públicos de producto; no hay cuentas ni operaciones reales.

| UC / AC / TC | Evidencia | Resultado |
| --- | --- | --- |
| L02-UC01 / AC01 / TC01 | Instalación lockfile, build y test HTTP de raíz/título | PASS |
| L02-UC02 / AC02 / TC02 | Chromium sin JavaScript, heading visible y navegación por ancla | PASS |
| L02-UC03 / AC03 / TC03 | HTTP 404, heading español y regreso a raíz | PASS |

Referencia: [frame Pen f0UZM](../../planning/LANDING_DESIGN_REFERENCES.md#pagina). El alcance mínimo de L02 conserva contenido semántico; tipografía, color y composición quedan en L04–L09. Las seis capturas adyacentes registran ambas rutas y tres viewports, Chromium 159.0.8154.6, escala 1, sin JavaScript. No hay baseline implementado anterior aprobado. VC01 PASS para esta base funcional, no para la landing final.

## Corrección de revisión — 26 de noviembre

Standards y Spec señalaron sobrescritura del baseline y falta de 320 px/200%. Las capturas nuevas van a `test-results` (ignorado); las originales quedan intactas. Promoción explícita de esta ejecución: [revision-02](revision-02/). El reporte se completa con trazabilidad y revisión.

Nuevo RED: a 320 px y ampliación CSS `zoom: 2`, una palabra larga desbordaba. Se añadió `overflow-wrap: anywhere` compartido. GREEN: 8 tests aprobados; tipos sin errores/advertencias; build incluido en la prueba. La ampliación se prueba por CSS zoom, no mediante el menú de zoom del navegador; ambas rutas conservan contenido, enlaces operables y no presentan desplazamiento horizontal. Entorno de esta repetición: Node 22.23.4, npm 11.6.2 (versión del host actual), mismo Chromium y macOS. Código evaluado: árbol de corrección sobre 1977dcd, identificado por el commit que incorpora este reporte. No se cambió el lockfile.

Capturas revisadas: [inicio 360](revision-02/inicio-360.png), [inicio 768](revision-02/inicio-768.png), [inicio 1440](revision-02/inicio-1440.png), [404 360](revision-02/404-360.png), [320 con ampliación 200%](revision-02/inicio-320-2.png). No hay contenido recortado; el salto de palabras a ancho extremo es intencional.
