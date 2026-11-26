# L03 — checks y artefactos (en curso)

Ticket #95. Base: 74a7245. Rama t3/landing-l03, apilada sobre #114 por autorización del usuario. Sin merge autorizado.

Fecha 2026-11-26; ejecutor Codex; macOS 26.6.2 arm64; Node 22.23.4, npm 11.6.2; Chromium 159.0.8154.6. Versiones de dependencias fijadas en lockfile.

| UC / AC / TC | Ejecución | Estado |
| --- | --- | --- |
| L03-UC01 / AC01 / TC01 | `npm run verify`: formato, lint, tipos, build y 8 pruebas. CI pendiente | NOT_RUN (parte externa pendiente) |
| L03-UC02 / AC02 / TC02 | Fixture temporal `const amount: number = "defecto intencional L03-TC02"` en página Astro: check termina 1 con TS2322, archivo/línea identificados. Fixture retirado y suite verde | PASS |
| L03-UC03 / AC03 / TC03 | Prueba temporal busca enlace inexistente; termina 1 y genera screenshot, contexto y trace.zip. Captura/contexto conservados en local-failure. Verificación de artefacto remoto pendiente | NOT_RUN (parte externa pendiente) |

Resultado inicial: antes del cambio `npm run verify` no existía (salida 1); después ejecuta cadena completa sin servicios bancarios ni secretos. El fallo intencional de navegación fue retirado. No hay skip/xfail. Reporte HTML incluye SHA y artefacto CI se nombra por SHA.

VC01 pendiente de CI. No hay cambios en UI: no aplica nueva comparación de diseño; captura del fallo documenta la frontera de diagnóstico. Reviews y completitud final pendientes. No se declara aprobado un requisito de CI por una ejecución local.
