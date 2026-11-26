# L02 — base Astro (en curso)

Base de revisión: d39aac3995130904e0a71247f61ef3741dc3eaa0.
Ticket: #94. Rama: t3/landing-l02; PR base previsto: t3/plan-landing-page-work.

El usuario autorizó continuar con PRs apilados sin integrar #108. L01 permanece abierto; esta excepción permite desarrollar dependencias, no simula aprobación humana ni autoriza merges.

Fronteras aprobadas: build estático y HTTP local, navegación sin JavaScript y 404.
Evidencia: resultado inicial. Implementación y verificación visual pendientes; no hay declaración de fidelidad a Pencil todavía.

Entorno: macOS arm64, Node 22.23.4 mediante npm exec, npm 10.9.2; Astro 7.4.13. Ejecutor: agente Codex. Fecha: 2026-11-25 local.

## Ejecución incremental

- L02-TC01 RED: HTTP 200 y HTML válido, fallo esperado de título (`Base` en lugar de Tappy).
- L02-TC01 GREEN: `npx --yes --package=node@22.23.4 -c 'npm test'`, 1 test aprobado, código 0.
- L02-TC02 RED: heading principal ausente; GREEN: contenido y navegación por ancla sin JavaScript, 2 tests aprobados. Chromium instalado: 159.0.8154.6, Playwright 1.65.1.
- L02-TC03 RED: heading genérico 404 en inglés; implementación de página española con regreso al inicio añadida. GREEN: status 404, mensaje y regreso al inicio aprobados.

Astro 7 detecta ejecución por agente y lanza preview en segundo plano. El servidor de pruebas usa `--ignore-lock` y puerto 4394 para que Playwright controle su ciclo de vida. Se detuvo el servidor inicial creado por Astro.

Checks: Astro check sin errores/advertencias; formato aprobado; build estático aprobado; 6 pruebas Playwright aprobadas (3 TC y 3 escenarios de capturas). AC funcionales: 3/3 (100%) en entorno local. VC01: capturas iniciales en 360×800, 768×1024 y 1440×900 para raíz y 404. HTML mínimo sin estilo: la fidelidad de las secciones se implementa en L04–L09, no se declara aquí. Reviews: pendientes.
