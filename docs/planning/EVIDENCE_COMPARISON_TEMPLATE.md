# Evidencia inicial o comparativa — <ticket>

Estado inicial: NOT_RUN. Plantilla para completar con ejecuciones reales; no es evidencia ni aprobación por sí misma. Seguir el [protocolo común](TICKET_QUALITY_PROTOCOL.md).

## Revisiones y escenario

- Ticket, UC/AC/TC y comprobación `<ticket>-VC01`:
- Modalidad: resultado inicial / cambio existente / No aplica justificado:
- Aplicabilidad por superficie: API / panel / comando; justificar las que no apliquen:
- Base aprobada (solo cambio existente): SHA y enlace; para nuevo indicar «No hay base previa»:
- Revisión actual: SHA o diff identificado antes del commit candidato:
- Entorno, configuración relevante y fecha:
- Actor/rol, fixture sintético, precondiciones y pasos reproducibles:
- Para UI: navegador, viewport, tema, escala de texto y estado de pantalla:
- Artefactos sanitizados accesibles al revisor:

## API — petición y respuesta

Duplicar esta sección por operación y TC afectado. Si no aplica, justificar la superficie alternativa usada.

- Método/ruta/query y body sanitizado:
- Cabeceras permitidas y normalización declarada:

| Elemento | Anterior aprobado | Actual |
| --- | --- | --- |
| Status HTTP | Por completar | Por completar |
| Cabeceras relevantes permitidas | Por completar | Por completar |
| Cuerpo JSON | Enlazar JSON formateado copiable | Enlazar JSON formateado copiable |
| Contrato OpenAPI | Referencia de base | Referencia actual y diff si cambió |

Para un endpoint nuevo completar solo petición, status, JSON y contrato esperado/actual; omitir columna anterior y diff. Para cambio existente completar ambas columnas y adjuntar diff legible. La evidencia inicial aprobada será la base de cambios futuros.

## Back office — resultado inicial o antes/después

Duplicar por vista y estado afectado. Si no aplica, indicar «Sin UI afectada».

| Vista / rol / TC / estado | Captura anterior | Captura actual | Comprobación de contenido e interacción |
| --- | --- | --- | --- |
| Por completar | Enlace o ausencia justificada | Enlace | Importes, estados, acciones, permisos, legibilidad; teclado/foco por separado cuando aplique |

Para una vista nueva adjuntar solo capturas iniciales y su validación contra AC/TC. Para una modificación mostrar las dos capturas lado a lado al revisar. Registrar además petición/resultado y lectura posterior para acciones que modifican datos.

## Comandos, infraestructura o trabajos

- Comando o interfaz observable:
- Antes (solo cambio existente): salida sanitizada y código de salida:
- Resultado inicial o actual: salida sanitizada y código de salida:
- Diferencia y efecto consultable:

## Diferencias y decisión

| TC / AC | Diferencia concreta antes → después | Esperada / regresión | Motivo y efecto en consumidores | Test/evidencia | Resolución |
| --- | --- | --- | --- | --- | --- |
| Por completar | Por completar | Por clasificar | Por completar | Por completar | Pendiente |

- Estado VC01: NOT_RUN / PASS / FAIL / BLOCKED; No aplica con justificación revisada cuando corresponda.
- Revisión de base y actual comparadas:
- Diferencias inesperadas pendientes:
- Revisión Standards/Spec y decisión:
- Nueva base propuesta: no reemplazar la anterior antes de aprobar.

La evidencia se exige según aplicabilidad: inicial para nuevo y comparativa para modificación; no suma puntos artificiales a la completitud. Un JSON distinto no se acepta solo regenerando snapshots, y una captura similar no sustituye las pruebas de comportamiento.
