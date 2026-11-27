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

Regresión de configuración detectada al incluir metadatos git: faltaban tipos Node y Astro inspeccionaba el reporte generado. Corregido con @types/node fijado y exclusión de artefactos generados (no de código propio) en tsconfig. `npm run verify` vuelve a pasar completo, salida 0, ocho pruebas; log local /tmp/l03-verify.log.

## Evidencia remota verificada

[Run 45857206177](https://github.com/luisjrez/Tappy/actions/runs/45857206177), SHA f7958625b15853be91b52400e8c65f22b556493f: ocho casos reales aprobados y solo L03-TC03 falló intencionalmente. El artefacto [15137225075](https://github.com/luisjrez/Tappy/actions/runs/45857206177/artifacts/15137225075) se descargó y comprobó: JUnit identifica caso/fallo, trace.zip contiene 59 eventos y error de expectativa, y captura PNG muestra la landing sintética. Copia durable: ci-failure/. AC03 PASS. La prueba intencional se retira en esta revisión; falta ejecución verde del nuevo HEAD para AC01 y VC01 final.

La primera ejecución Linux detectó dependencias opcionales ausentes del lockfile; no se contó como prueba negativa funcional. Se regeneró el lockfile desde package.json en directorio limpio con npm 10.9.2 y se fijó esa versión en CI. La ejecución arriba ya instaló y verificó correctamente.
