# Landing Tappy — borrador de historias y subtareas

Fecha: 25 de noviembre de 2026. Estado: **Plan, referencias y Cloudflare Pages Free aprobados por el usuario para publicar tickets; implementación NOT_RUN**. Todos los AC, TC y VC están NOT_RUN.

## Alcance y fuentes

Solo landing pública responsive y sus páginas informativas. No incluye app móvil, web transaccional del pagador, autenticación, alta de comercios, back office, integración bancaria ni construcción de una demo interactiva. Mostrar una captura de la app no implica implementarla. La adaptación de la landing a teléfono sí forma parte de web.

Fuentes: [PRODUCT_BASE.md](../../PRODUCT_BASE.md), [CONTEXT.md](../../CONTEXT.md), [estructura del backlog backend](BACKEND_TICKETS_DRAFT.md) y [protocolo de calidad](TICKET_QUALITY_PROTOCOL.md). No se recibió un ticket web concreto; la consulta de issues abiertas no identificó uno de landing. Antes de implementar cada ticket publicado se leerán su cuerpo, comentarios, padre y bloqueos.

**Diseño inspeccionado por MCP:** `Landing A · Mostrador`, frame `f0UZM`, 1440 × 5924. Se leyeron sus secciones y textos en el documento abierto de `/Users/luisjuarez/dev/Tappy/tappy-design.pen` y se confirmó el mismo frame y sus siete hijos en la copia del worktree. Ver [índice de diseño y diferencias](LANDING_DESIGN_REFERENCES.md). Solo se inspeccionó la landing; no se modificó Pen. La lectura valida referencias del borrador, no significa que L01 ni la implementación estén aprobados.

## Propuesta técnica

Astro + TypeScript estricto, salida estática, HTML semántico y CSS responsive en `apps/landing/` (ruta propuesta). JavaScript solo para interacciones que lo necesiten; FAQ nativa con details/summary y enlaces de sección. Sin servidor web de aplicación, base de datos, CMS ni framework cliente adicional por defecto. Reutilizar assets/tokens existentes tras inventariarlos; no duplicar el sistema de marca ni copiar pantallas móviles como componentes funcionales.

Astro prerenderiza páginas por defecto: [documentación oficial consultada](https://docs.astro.build/en/guides/on-demand-rendering/). Esto sustenta la propuesta estática, no una medición de rendimiento. Versiones, gestor de paquetes y hosting se fijarán al implementar L02 respetando el monorepo.

CTA propuesto: «Ver demo» solo con destino público disponible y rotulado. Mientras no exista, «Cómo funciona» enlaza a la explicación dentro de la página. No construir una demo como trabajo oculto de landing. Lista de espera, formularios y analítica quedan fuera de esta entrega; requieren alcance y tratamiento de datos propios.


**Storybook incluido por petición del usuario.** L13 prepara una prueba de integración con componentes reales de Astro y un catálogo mínimo; L14 completa estados, interacciones y regresión visual. Se seleccionará y fijará una combinación de versiones probada: la documentación de Storybook distingue integraciones oficiales y comunitarias, incluida Astro. No se presupone que cualquier versión de Astro/Storybook sea compatible. Se evaluará primero el adaptador Astro vigente; si no funciona, documentar una alternativa de render del HTML real de Astro sin mantener copias de markup exclusivas para las stories. La compatibilidad es un AC de L13, no una promesa del borrador. Storybook se construye como artefacto separado de la landing pública; no añade por sí mismo JavaScript al sitio ni exige contratar un servicio visual.

Fuentes consultadas: [integraciones Storybook](https://storybook.js.org/docs/contribute/framework), [adaptador Astro](https://github.com/storybook-astro/storybook-astro/blob/develop/README.md). Versiones y mecanismo exacto pendientes de la prueba L13.

## Correspondencia con la narrativa documentada

Este mapa cubre PRODUCT_BASE §5.1 y el frame inspeccionado; los IDs y diferencias se detallan en el [índice de Pen](LANDING_DESIGN_REFERENCES.md). FAQ y enlaces legales son ampliaciones necesarias respecto al diseño actual, sujetas a aprobación del borrador.

| Parte de landing | Entrega | Ticket |
| --- | --- | --- |
| Cabecera y propuesta principal | Marca, beneficio, navegación y CTA visible | L04, L08 |
| Problema cotidiano | Capturas del pagador, consulta al banco y cierre manual | L05 |
| Cómo funciona | Importe, solicitud y recepción validada, con límites por canal | L05 |
| Beneficios | Historial, comprobantes y resumen según disponibilidad comprobada | L06 |
| Experiencia del pagador | Revisión y autorización bancaria compatible sin registro Tappy | L07 |
| Ayuda y límites | FAQ, responsabilidades y compatibilidad | L07 |
| Acción final | Demo disponible o explicación interna | L08 |
| Pie informativo | Términos, privacidad y contacto atendido | L09 |

Referencias visuales adicionales: [sistema web](../../design-system/README.md), [tokens CSS](../../design-system/tappy-theme.css) y [marca](../../TAPPY_BRAND_IDENTITY_SPEC.md). La guía existente propone superficies cálidas, verde bosque, retícula de 4 px, contenedor máximo 80 rem, controles de 48 px y titular HTML de 40–80 px. Son referencias a reconciliar con Pen en L01, no medidas extraídas del archivo actual. La guía tiene instrucciones para Tailwind/shadcn; no obligan a añadir React ni shadcn a Astro: conservar los valores y roles pertinentes con CSS del sitio. L01 debe resolver explícitamente variantes de fuente y tema claro/oscuro; L10 verificará todos los temas que se comprometan, sin dar por aprobado uno por omisión.

## Historias padre

| ID | Historia de usuario | Subtareas obligatorias | Aceptación de la historia |
| --- | --- | --- | --- |
| LW1 | Como contribuidor, quiero una referencia web y una base reproducible para entregar cambios verificables. | L01–L03, L13 | Referencia trazable, build estático y controles que detectan fallos. |
| LW2 | Como responsable de un comercio, quiero entender qué resuelve Tappy y cómo funciona para valorar si me sirve. | L04–L06 | Narrativa completa, honesta y legible en escritorio y teléfono. |
| LW3 | Como visitante, quiero resolver dudas y acceder a una acción disponible para continuar con confianza. | L07–L09 | FAQ, CTA y enlaces informativos útiles, sin promesas falsas ni destinos vacíos. |
| LW4 | Como visitante, quiero acceder a una página rápida y accesible; como responsable de publicación, quiero una entrega comprobable. | L10–L12, L14 | Accesibilidad, metadatos y publicación verificadas sobre la revisión final. |

Una historia se acepta solo cuando todas sus subtareas obligatorias pasan. Los IDs LW/L son locales; no son números de GitHub. Publicación de las 4 historias y 14 subtickets autorizada explícitamente por el usuario.

## Contrato común de implementación

Cada fila de escenario define un UC, un AC obligatorio y un TC con el mismo sufijo. El UC es la acción del actor bajo la preparación indicada; el AC es el resultado esperado completo; el TC ejecuta esa acción por la frontera observable. Todos están NOT_RUN, incluidos los manuales. Cada ticket hereda el alcance/exclusiones anterior y requiere sus bloqueos resueltos.

Aplicar el protocolo común: Red por comportamiento ausente → mínimo Green → refactor con checks verdes → evidencia → commit candidato → review Standards/Spec → correcciones, nueva verificación y review → PR humano. En contenido/diseño, revisión contra checklist y evidencia documental; TDD de software no aplica hasta existir comportamiento ejecutable. No inventar tests que comparen constantes consigo mismas.

Checks web propuestos: formato/lint de archivos web, Astro check/TypeScript, build estático, pruebas de comportamiento con Playwright, enlaces internos y revisión accesible automática más teclado/lector manual. L02/L03 fijan comandos y versiones reproducibles. Ruff, mypy, pytest y Postgres no aplican a cambios exclusivamente web/documentales; si se toca backend se exige su batería real aislada. No añadir backend para satisfacer un checklist.

VC01 obligatorio por ticket: resultado inicial para funcionalidad nueva; antes/después contra la última base aprobada para modificaciones; No aplica solo justificado. Conservar SHA, entorno, pasos, viewport y evidencia sanitizada con la [plantilla](EVIDENCE_COMPARISON_TEMPLATE.md). Capturas no sustituyen pruebas de interacción. Para UI usar 360×800, 768×1024 y 1440×900; comprobar además reflow a 320 CSS px y zoom 200%. Assets y datos siempre ficticios, sin información bancaria/personal real.

Salida: ≥97% de AC aplicables sin redondeo, todos los obligatorios y checks aprobados, VC01 conforme y cero hallazgos abiertos. Aquí cada ticket tiene tres AC obligatorios: exige 3/3. NOT_RUN/BLOCKED no suma. No declarar avance funcional por completar este documento.


### Evidencia visual revisable por ticket

Cada ticket lleva **Referencia de diseño** con enlace a la sección del índice, archivo Pen y node ID. No se inventan URLs de selección de Pen: las herramientas disponibles exponen archivo e ID, pero no un permalink confirmado. El índice ofrece enlaces navegables y el ID exacto para localizar el nodo por MCP. Al publicar issues, convertir estos enlaces a URLs de GitHub fijadas a una revisión.

- **Primera implementación:** diseño de referencia + captura del resultado inicial + lista de desviaciones aprobadas. Pen es la referencia de diseño, no un «antes» de código que nunca existió.
- **Cambio posterior:** captura antes de la última versión aprobada + después del candidato + diff visual, en el mismo viewport, navegador, tema, fuente cargada, datos sintéticos y estado. Guardar ambos SHA y versión del Pen; no sobrescribir el baseline.
- **Revisión:** tabla por diferencia con sección/node ID, story o ruta, UC/AC/TC, esperado, observado, motivo, clasificación (ajuste esperado o regresión), decisión y evidencia. Un cambio de copy aprobado puede diferir de Pen; un contenido recortado o CTA perdido bloquea.
- **Storybook:** cada story incorpora referencia Pen, ticket y estado. Capturar normal, foco/hover donde aplique, texto largo, ancho estrecho, FAQ abierta/cerrada y movimiento reducido. Los componentes se añaden a Storybook en su ticket L04–L09; L14 verifica cobertura y compone las secciones, no posterga toda la documentación.
- **Entrega al revisor:** reporte Markdown y capturas antes/después/diff (o referencia/resultado inicial) como artefactos de CI o del PR accesibles, con enlaces a la story y página completa. No depender de archivos temporales ni de un porcentaje de píxeles como prueba de corrección. Capturar también página integrada: Storybook no sustituye E2E ni teclado/lector.

L03 conserva artefactos; L13 habilita el catálogo; L14 implementa y demuestra la detección de regresiones; cada VC01 hereda estas reglas. La referencia original se conserva en `docs/design/landing/2026-11-25/` con manifest de hashes; copiar su enlace y node ID al reporte de cada ejecución. Una modificación intencional del baseline necesita revisión explícita. Regenerar capturas no convierte una regresión en aprobada.

## Subtareas

### L01 — Consolidar referencia y copy web

**Referencia de diseño:** [secciones e IDs Pen](LANDING_DESIGN_REFERENCES.md#inventario).

**Capturas de referencia:** [f0UZM](../design/landing/2026-11-25/f0UZM.png).

**Bloqueado por:** —. **Actor:** Producto/diseño. **Frontera:** Inventario documentado.

**Objetivo/alcance y pasos:** Inventariar solo frames de landing; resolver marca/tokens/assets; registrar copy aprobado y destinos.

**UC → AC → TC (obligatorios; NOT_RUN)**

| IDs | Preparación | Acción / caso de uso | Resultado esperado / criterio de aceptación | Ejecución |
| --- | --- | --- | --- | --- |
| L01-UC01 → L01-AC01 → L01-TC01 | Pen disponible y base de producto | Identificar secciones y assets de landing | Inventario con IDs de frames, tamaños, fuente/licencia de assets y diferencias respecto a producto; ninguna pantalla móvil incluida como alcance | Manual |
| L01-UC02 → L01-AC02 → L01-TC02 | Copy del diseño con alta gratis, NFC o compatibilidad universal | Revisar cada afirmación | Matriz conservar/corregir/retirar con fundamento; ninguna promesa sin respaldo aprobada | Manual |
| L01-UC03 → L01-AC03 → L01-TC03 | Demo, contacto o textos legales sin destino confirmado | Definir estado de cada enlace | Decisiones pendientes con responsable por asignar y condición de desbloqueo; CTA alterno Cómo funciona documentado | Manual |

**Red/Green/Refactor:** aplicar el ciclo común a cada TC automatizado por separado; verificar los TC manuales con pasos y resultado observado. En L01, TDD de software No aplica: entrega documental revisada contra fuentes.

**L01-VC01 — NOT_RUN:** evidencia inicial de la frontera indicada para los tres TC; capturas de estados visibles cuando aplique y salida de comandos para build/CI. Modificaciones posteriores requieren antes/después. Identificar revisión y referencias UC/AC/TC; cumplir la salida común antes de cerrar.

### L02 — Servir la primera página estática

**Referencia de diseño:** [secciones e IDs Pen](LANDING_DESIGN_REFERENCES.md#pagina).

**Capturas de referencia:** [f0UZM](../design/landing/2026-11-25/f0UZM.png).

**Bloqueado por:** L01. **Actor:** Contribuidor. **Frontera:** Build y HTTP local.

**Objetivo/alcance y pasos:** Crear app Astro mínima; fijar versiones/lockfile y scripts; documentar instalación.

**UC → AC → TC (obligatorios; NOT_RUN)**

| IDs | Preparación | Acción / caso de uso | Resultado esperado / criterio de aceptación | Ejecución |
| --- | --- | --- | --- | --- |
| L02-UC01 → L02-AC01 → L02-TC01 | Checkout limpio y entorno documentado | Instalar y generar sitio | Build reproducible sin secretos ni servicios bancarios; raíz devuelve HTML con título Tappy | Automatizada |
| L02-UC02 → L02-AC02 → L02-TC02 | JavaScript desactivado | Abrir raíz | Texto principal y enlace Cómo funciona accesibles en HTML | Automatizada |
| L02-UC03 → L02-AC03 → L02-TC03 | Ruta inexistente | Solicitar página | Página 404 útil con regreso al inicio y status 404 en hosting compatible | Automatizada |

**Red/Green/Refactor:** aplicar el ciclo común a cada TC automatizado por separado; verificar los TC manuales con pasos y resultado observado.

**L02-VC01 — NOT_RUN:** evidencia inicial de la frontera indicada para los tres TC; capturas de estados visibles cuando aplique y salida de comandos para build/CI. Modificaciones posteriores requieren antes/después. Identificar revisión y referencias UC/AC/TC; cumplir la salida común antes de cerrar.

### L03 — Verificar cambios web en CI

**Referencia de diseño:** [secciones e IDs Pen](LANDING_DESIGN_REFERENCES.md#pagina).

**Capturas de referencia:** [f0UZM](../design/landing/2026-11-25/f0UZM.png).

**Bloqueado por:** L02. **Actor:** Contribuidor. **Frontera:** Comando de verificación y CI.

**Objetivo/alcance y pasos:** Configurar checks web y pruebas de navegador; guardar artefactos sanitizados.

**UC → AC → TC (obligatorios; NOT_RUN)**

| IDs | Preparación | Acción / caso de uso | Resultado esperado / criterio de aceptación | Ejecución |
| --- | --- | --- | --- | --- |
| L03-UC01 → L03-AC01 → L03-TC01 | Página válida | Ejecutar verificación local y CI | Formato, lint, tipos, build y smoke pasan con comandos equivalentes | Automatizada |
| L03-UC02 → L03-AC02 → L03-TC02 | Fixture temporal con enlace interno roto o error de tipos | Ejecutar check correspondiente | Check termina distinto de cero e identifica el defecto; retirar fixture tras demostrarlo | Automatizada |
| L03-UC03 → L03-AC03 → L03-TC03 | Fallo de prueba de navegación | Consultar artefactos de CI | Reporte identifica caso y revisión; captura/traza accesible sin secretos | Automatizada |

**Red/Green/Refactor:** aplicar el ciclo común a cada TC automatizado por separado; verificar los TC manuales con pasos y resultado observado.

**L03-VC01 — NOT_RUN:** evidencia inicial de la frontera indicada para los tres TC; capturas de estados visibles cuando aplique y salida de comandos para build/CI. Modificaciones posteriores requieren antes/después. Identificar revisión y referencias UC/AC/TC; cumplir la salida común antes de cerrar.

### L04 — Presentar propuesta y navegación

**Referencia de diseño:** [secciones e IDs Pen](LANDING_DESIGN_REFERENCES.md#header).

**Capturas de referencia:** [Q6PIC0](../design/landing/2026-11-25/Q6PIC0.png) · [v8LGy](../design/landing/2026-11-25/v8LGy.png) · [w7Vwm1](../design/landing/2026-11-25/w7Vwm1.png).

**Bloqueado por:** L01, L03, L13. **Actor:** Visitante. **Frontera:** Landing en navegador.

**Objetivo/alcance y pasos:** Construir header, hero y navegación por secciones; aplicar assets aprobados.

**UC → AC → TC (obligatorios; NOT_RUN)**

| IDs | Preparación | Acción / caso de uso | Resultado esperado / criterio de aceptación | Ejecución |
| --- | --- | --- | --- | --- |
| L04-UC01 → L04-AC01 → L04-TC01 | Primera visita | Leer hero | Identifica Tappy como herramienta para comercios, beneficio y acción; un h1 y ninguna oferta no aprobada | Manual + automatizada |
| L04-UC02 → L04-AC02 → L04-TC02 | Teclado y viewport estrecho | Recorrer navegación y activar ancla | Foco visible, orden lógico y sección destino visible sin ocultarse bajo header | Automatizada + manual |
| L04-UC03 → L04-AC03 → L04-TC03 | Imágenes ausentes o JS desactivado | Leer propuesta y seguir CTA | Mensaje y navegación siguen disponibles; imágenes informativas tienen alternativa y decorativas alt vacío | Automatizada |

**Red/Green/Refactor:** aplicar el ciclo común a cada TC automatizado por separado; verificar los TC manuales con pasos y resultado observado.

**L04-VC01 — NOT_RUN:** evidencia inicial de la frontera indicada para los tres TC; capturas de estados visibles cuando aplique y salida de comandos para build/CI. Modificaciones posteriores requieren antes/después. Identificar revisión y referencias UC/AC/TC; cumplir la salida común antes de cerrar.

### L05 — Explicar problema y recorrido de cobro

**Referencia de diseño:** [secciones e IDs Pen](LANDING_DESIGN_REFERENCES.md#problema-y-pasos).

**Capturas de referencia:** [aboaM](../design/landing/2026-11-25/aboaM.png) · [mBQBr](../design/landing/2026-11-25/mBQBr.png).

**Bloqueado por:** L04. **Actor:** Responsable del comercio. **Frontera:** Secciones problema y cómo funciona.

**Objetivo/alcance y pasos:** Implementar problema cotidiano y pasos ilustrados con copy aprobado.

**UC → AC → TC (obligatorios; NOT_RUN)**

| IDs | Preparación | Acción / caso de uso | Resultado esperado / criterio de aceptación | Ejecución |
| --- | --- | --- | --- | --- |
| L05-UC01 → L05-AC01 → L05-TC01 | Visitante sin conocimiento de CoDi | Leer pasos | Entiende capturar importe, solicitar y esperar evidencia validada; mostrar QR no equivale a recibir | Manual |
| L05-UC02 → L05-AC02 → L05-TC02 | Canales celular/enlace no confirmados | Consultar canales anunciados | Solo capacidades verificadas figuran disponibles; ninguna mención a NFC o Tap to Pay | Manual |
| L05-UC03 → L05-AC03 → L05-TC03 | Ancho 320 CSS px | Recorrer problema y pasos | Orden de lectura coherente y contenido completo sin scroll horizontal | Automatizada + manual |

**Red/Green/Refactor:** aplicar el ciclo común a cada TC automatizado por separado; verificar los TC manuales con pasos y resultado observado.

**L05-VC01 — NOT_RUN:** evidencia inicial de la frontera indicada para los tres TC; capturas de estados visibles cuando aplique y salida de comandos para build/CI. Modificaciones posteriores requieren antes/después. Identificar revisión y referencias UC/AC/TC; cumplir la salida común antes de cerrar.

### L06 — Mostrar beneficios con ejemplos honestos

**Referencia de diseño:** [secciones e IDs Pen](LANDING_DESIGN_REFERENCES.md#tus-cobros).

**Capturas de referencia:** [W72wy](../design/landing/2026-11-25/W72wy.png) · [NvxvB](../design/landing/2026-11-25/NvxvB.png) · [r8djG](../design/landing/2026-11-25/r8djG.png).

**Bloqueado por:** L05. **Actor:** Responsable del comercio. **Frontera:** Secciones de beneficios.

**Objetivo/alcance y pasos:** Integrar historial, resumen y material ilustrativo aprobado; optimizar imágenes.

**UC → AC → TC (obligatorios; NOT_RUN)**

| IDs | Preparación | Acción / caso de uso | Resultado esperado / criterio de aceptación | Ejecución |
| --- | --- | --- | --- | --- |
| L06-UC01 → L06-AC01 → L06-TC01 | Ejemplos con importes sintéticos | Leer beneficios y capturas | Ejemplos rotulados ilustrativos; recibido no se presenta como saldo bancario ni utilidad | Manual |
| L06-UC02 → L06-AC02 → L06-TC02 | Comprobante o avisos aún no disponibles | Revisar copy contra matriz L01 | Funciones pendientes no se anuncian como entregadas y no se inventan testimonios/cifras | Manual |
| L06-UC03 → L06-AC03 → L06-TC03 | Conexión lenta y tamaños responsive | Cargar sección | Imágenes con dimensiones reservadas, variantes adecuadas y texto legible; carga diferida fuera de vista | Automatizada + manual |

**Red/Green/Refactor:** aplicar el ciclo común a cada TC automatizado por separado; verificar los TC manuales con pasos y resultado observado.

**L06-VC01 — NOT_RUN:** evidencia inicial de la frontera indicada para los tres TC; capturas de estados visibles cuando aplique y salida de comandos para build/CI. Modificaciones posteriores requieren antes/después. Identificar revisión y referencias UC/AC/TC; cumplir la salida común antes de cerrar.

### L07 — Resolver dudas y explicar al pagador

**Referencia de diseño:** [secciones e IDs Pen](LANDING_DESIGN_REFERENCES.md#pagador-y-ayuda).

**Capturas de referencia:** [w2ypd](../design/landing/2026-11-25/w2ypd.png). FAQ y páginas informativas no tienen diseño existente; ver ampliaciones explícitas del índice.

**Bloqueado por:** L05. **Actor:** Visitante. **Frontera:** FAQ y explicación.

**Objetivo/alcance y pasos:** Redactar FAQ y responsabilidades; usar interacción semántica nativa.

**UC → AC → TC (obligatorios; NOT_RUN)**

| IDs | Preparación | Acción / caso de uso | Resultado esperado / criterio de aceptación | Ejecución |
| --- | --- | --- | --- | --- |
| L07-UC01 → L07-AC01 → L07-TC01 | Dudas sobre banco y destino del dinero | Leer FAQ | Explica cuenta receptora, banco compatible y ausencia de custodia; no garantiza compatibilidad universal | Manual |
| L07-UC02 → L07-AC02 → L07-TC02 | Teclado y lector de pantalla | Abrir y cerrar respuestas | Controles tienen nombre/estado accesible; respuestas operables y foco conservado | Automatizada + manual |
| L07-UC03 → L07-AC03 → L07-TC03 | JavaScript desactivado | Consultar explicación para pagador | Puede leer que autoriza en banco compatible sin registrarse en Tappy; no se abre checkout ni se pide información bancaria | Automatizada + manual |

**Red/Green/Refactor:** aplicar el ciclo común a cada TC automatizado por separado; verificar los TC manuales con pasos y resultado observado.

**L07-VC01 — NOT_RUN:** evidencia inicial de la frontera indicada para los tres TC; capturas de estados visibles cuando aplique y salida de comandos para build/CI. Modificaciones posteriores requieren antes/después. Identificar revisión y referencias UC/AC/TC; cumplir la salida común antes de cerrar.

### L08 — Conectar CTA a una acción disponible

**Referencia de diseño:** [secciones e IDs Pen](LANDING_DESIGN_REFERENCES.md#cta-final).

**Capturas de referencia:** [Q6PIC0](../design/landing/2026-11-25/Q6PIC0.png) · [Fo93N](../design/landing/2026-11-25/Fo93N.png).

**Bloqueado por:** L04, L07. **Actor:** Visitante. **Frontera:** CTA inicial y final.

**Objetivo/alcance y pasos:** Configurar destino aprobado; implementar alternativa interna y mensajes de demostración.

**UC → AC → TC (obligatorios; NOT_RUN)**

| IDs | Preparación | Acción / caso de uso | Resultado esperado / criterio de aceptación | Ejecución |
| --- | --- | --- | --- | --- |
| L08-UC01 → L08-AC01 → L08-TC01 | Destino demo confirmado | Activar CTA inicial y final | Ambos llegan al destino aprobado con aviso de simulación si corresponde; no prometen operación bancaria real | Automatizada + manual |
| L08-UC02 → L08-AC02 → L08-TC02 | Demo no disponible al configurar entrega | Generar y abrir landing | CTA Cómo funciona llega a sección existente; no hay href vacío, # sin destino ni alta falsa | Automatizada |
| L08-UC03 → L08-AC03 → L08-TC03 | Destino externo se retira antes de publicar | Revisar enlaces de entrega | Publicación bloqueada hasta restaurar destino o activar alternativa y repetir pruebas | Manual |

**Red/Green/Refactor:** aplicar el ciclo común a cada TC automatizado por separado; verificar los TC manuales con pasos y resultado observado.

**L08-VC01 — NOT_RUN:** evidencia inicial de la frontera indicada para los tres TC; capturas de estados visibles cuando aplique y salida de comandos para build/CI. Modificaciones posteriores requieren antes/después. Identificar revisión y referencias UC/AC/TC; cumplir la salida común antes de cerrar.

### L09 — Ofrecer información y contacto reales

**Referencia de diseño:** [secciones e IDs Pen](LANDING_DESIGN_REFERENCES.md#footer).

**Capturas de referencia:** [ezjQ3](../design/landing/2026-11-25/ezjQ3.png). FAQ y páginas informativas no tienen diseño existente; ver ampliaciones explícitas del índice.

**Bloqueado por:** L01, L08. **Actor:** Visitante. **Frontera:** Footer y páginas informativas.

**Objetivo/alcance y pasos:** Añadir privacidad/términos aprobados y contacto atendido; enlaces de retorno.

**UC → AC → TC (obligatorios; NOT_RUN)**

| IDs | Preparación | Acción / caso de uso | Resultado esperado / criterio de aceptación | Ejecución |
| --- | --- | --- | --- | --- |
| L09-UC01 → L09-AC01 → L09-TC01 | Textos y contacto aprobados por responsable de producto | Abrir enlaces del footer | Términos, privacidad y contacto tienen contenido/destino real y navegación de retorno | Automatizada + manual |
| L09-UC02 → L09-AC02 → L09-TC02 | Falta texto final o contacto atendido | Preparar publicación | Entrega queda bloqueada con pendiente explícito; no se publican plantillas ni direcciones inventadas | Manual |
| L09-UC03 → L09-AC03 → L09-TC03 | Navegación sin consentimiento de seguimiento | Inspeccionar solicitudes y almacenamiento | No hay formularios, trackers, cookies no esenciales ni captura de datos añadidos por landing | Automatizada + manual |

**Red/Green/Refactor:** aplicar el ciclo común a cada TC automatizado por separado; verificar los TC manuales con pasos y resultado observado.

**L09-VC01 — NOT_RUN:** evidencia inicial de la frontera indicada para los tres TC; capturas de estados visibles cuando aplique y salida de comandos para build/CI. Modificaciones posteriores requieren antes/después. Identificar revisión y referencias UC/AC/TC; cumplir la salida común antes de cerrar.

### L10 — Validar accesibilidad y fidelidad responsive

**Referencia de diseño:** [secciones e IDs Pen](LANDING_DESIGN_REFERENCES.md#pagina).

**Capturas de referencia:** [f0UZM](../design/landing/2026-11-25/f0UZM.png).

**Bloqueado por:** L06, L07, L08, L09, L14. **Actor:** Visitante. **Frontera:** Recorrido completo.

**Objetivo/alcance y pasos:** Corregir contraste, foco, reflow y movimiento; comparar referencia aprobada.

**UC → AC → TC (obligatorios; NOT_RUN)**

| IDs | Preparación | Acción / caso de uso | Resultado esperado / criterio de aceptación | Ejecución |
| --- | --- | --- | --- | --- |
| L10-UC01 → L10-AC01 → L10-TC01 | Tres viewports acordados y referencia L01 | Comparar página completa | Jerarquía, contenido, tokens y assets corresponden a referencia; diferencias justificadas sin recortes ni solapamientos | Manual |
| L10-UC02 → L10-AC02 → L10-TC02 | Teclado, lector, zoom 200% y reflow 320 px | Navegar todo el contenido | Skip link, landmarks, headings y foco útiles; ningún bloqueo de acceso; contraste AA verificado | Manual + automatizada |
| L10-UC03 → L10-AC03 → L10-TC03 | Preferencia reducir movimiento y auditoría automática | Abrir sitio y ejecutar auditoría | Animación no esencial se reduce; cero hallazgos serious/critical sin resolver y revisión manual completada | Automatizada + manual |

**Red/Green/Refactor:** aplicar el ciclo común a cada TC automatizado por separado; verificar los TC manuales con pasos y resultado observado.

**L10-VC01 — NOT_RUN:** evidencia inicial de la frontera indicada para los tres TC; capturas de estados visibles cuando aplique y salida de comandos para build/CI. Modificaciones posteriores requieren antes/después. Identificar revisión y referencias UC/AC/TC; cumplir la salida común antes de cerrar.

### L11 — Preparar metadatos y presupuesto de rendimiento

**Referencia de diseño:** [secciones e IDs Pen](LANDING_DESIGN_REFERENCES.md#pagina).

**Capturas de referencia:** [f0UZM](../design/landing/2026-11-25/f0UZM.png).

**Bloqueado por:** L06, L09. **Actor:** Visitante y responsable de publicación. **Frontera:** HTML generado y carga.

**Objetivo/alcance y pasos:** Añadir metadatos, OG, favicon, sitemap/robots por entorno; medir build.

**UC → AC → TC (obligatorios; NOT_RUN)**

| IDs | Preparación | Acción / caso de uso | Resultado esperado / criterio de aceptación | Ejecución |
| --- | --- | --- | --- | --- |
| L11-UC01 → L11-AC01 → L11-TC01 | URL canónica de producción confirmada | Inspeccionar HTML y sitemap | lang es-MX, title/description, canonical y OG coherentes; sitemap solo con rutas públicas indexables | Automatizada |
| L11-UC02 → L11-AC02 → L11-TC02 | Entorno preview | Consultar robots y metadatos | Preview noindex; producción indexable solo al liberar; no se publican URLs de localhost | Automatizada |
| L11-UC03 → L11-AC03 → L11-TC03 | Build de producción y perfil Lighthouse móvil fijado en reporte | Medir tres cargas limpias | Mediana Performance ≥90, LCP ≤2.5 s y CLS ≤0.1 como presupuesto de laboratorio; no se afirma resultado de usuarios reales | Automatizada |

**Red/Green/Refactor:** aplicar el ciclo común a cada TC automatizado por separado; verificar los TC manuales con pasos y resultado observado.

**L11-VC01 — NOT_RUN:** evidencia inicial de la frontera indicada para los tres TC; capturas de estados visibles cuando aplique y salida de comandos para build/CI. Modificaciones posteriores requieren antes/después. Identificar revisión y referencias UC/AC/TC; cumplir la salida común antes de cerrar.

### L12 — Verificar entrega y preparar publicación

**Referencia de diseño:** [secciones e IDs Pen](LANDING_DESIGN_REFERENCES.md#pagina).

**Capturas de referencia:** [f0UZM](../design/landing/2026-11-25/f0UZM.png).

**Bloqueado por:** L03, L10, L11. **Actor:** Responsable de publicación. **Frontera:** Hosting y smoke público.

**Objetivo/alcance y pasos:** Proveedor acordado: Cloudflare Pages Free, dos proyectos del mismo monorepo (landing y Storybook). Configurar previews por PR, HTTPS, caché y rollback; publicar cuando se autorice. Ver [investigación y condiciones verificables](../research/landing-preview-hosting.md). No se han conectado cuentas ni desplegado sitios.

**Contrato de previews de L12-TC01:** abrir PR de rama del mismo repo y comprobar dos checks/enlaces (landing y Storybook) asociados al SHA; enviar segundo commit y verificar actualización sin cambiar producción; provocar fallo de build y comprobar que no se presenta preview antigua como evidencia del nuevo SHA. Ejecutar smoke de ambas superficies, assets/rutas/404 y story iframe; verificar noindex. Registrar URLs, SHA, resultados y capturas fuera del hosting efímero. PRs de forks quedan pendientes de flujo específico y no se declaran soportados. Presupuestar ambos builds dentro de 500/mes y comprobar cuotas vigentes al configurar. Dominio propio y servicios adicionales no están incluidos en el objetivo de hosting gratuito.

**UC → AC → TC (obligatorios; NOT_RUN)**

| IDs | Preparación | Acción / caso de uso | Resultado esperado / criterio de aceptación | Ejecución |
| --- | --- | --- | --- | --- |
| L12-UC01 → L12-AC01 → L12-TC01 | Hosting y dominio confirmados, revisión aprobada | Desplegar preview del commit candidato | Dos previews por PR (landing y Storybook) pasan el contrato de actualización, fallo, smoke y noindex definido arriba; evidencia identifica SHA exacto | Automatizada + manual |
| L12-UC02 → L12-AC02 → L12-TC02 | Autorización de publicación y todos los checks verdes | Publicar y recorrer URLs finales | HTTPS, enlaces, canonical/robots y contenido corresponden al SHA aprobado; smoke sin fallos | Automatizada + manual |
| L12-UC03 → L12-AC03 → L12-TC03 | Versión anterior conocida en entorno de prueba | Ejercitar rollback y repetir smoke | Se restaura artefacto conocido con procedimiento documentado; no se afectan API ni clientes móviles | Manual |

**Red/Green/Refactor:** aplicar el ciclo común a cada TC automatizado por separado; verificar los TC manuales con pasos y resultado observado.

**L12-VC01 — NOT_RUN:** evidencia inicial de la frontera indicada para los tres TC; capturas de estados visibles cuando aplique y salida de comandos para build/CI. Modificaciones posteriores requieren antes/después. Identificar revisión y referencias UC/AC/TC; cumplir la salida común antes de cerrar.

### L13 — Habilitar Storybook con componentes reales

**Referencia de diseño:** [inventario y componentes web](LANDING_DESIGN_REFERENCES.md#inventario).

**Capturas de referencia:** [v8LGy](../design/landing/2026-11-25/v8LGy.png) · [w7Vwm1](../design/landing/2026-11-25/w7Vwm1.png) · [Fo93N](../design/landing/2026-11-25/Fo93N.png).

**Historia padre:** LW1. **Bloqueado por:** L02, L03. **Actor:** Contribuidor/revisor. **Frontera:** Storybook local y build estático.

**Objetivo/alcance y pasos:** Probar integración Astro/Storybook, fijar versiones y comandos; compartir tokens, fuentes, assets y componentes reales; crear stories iniciales de enlace/CTA y contenedor. Documentar cómo añadir stories y conservar artefacto CI. No crear componentes móviles ni duplicar markup para simular fidelidad.

| IDs | Preparación | Acción / caso de uso | Resultado esperado / criterio de aceptación | Ejecución |
| --- | --- | --- | --- | --- |
| L13-UC01 → L13-AC01 → L13-TC01 | Checkout limpio, versiones fijadas | Instalar, arrancar y construir Storybook | Catálogo abre y build estático pasa local/CI; integración y limitaciones documentadas | Automatizada |
| L13-UC02 → L13-AC02 → L13-TC02 | CTA real utilizado por Astro y story | Cambiar etiqueta/estilo en fuente compartida y renderizar ambos | Cambio aparece en landing y story sin editar una segunda implementación; mismo CSS y semántica | Automatizada + manual |
| L13-UC03 → L13-AC03 → L13-TC03 | Story inicial con variantes normal/foco/texto largo | Recorrer con teclado y consultar documentación | Variantes visibles y operables, referencia Pen/ID/ticket accesible y ningún asset roto | Automatizada + manual |

**Red/Green/Refactor:** observar fallo de render/integración por comportamiento faltante, lograr paridad mínima, simplificar configuración y repetir checks. Un fallo de instalación no cuenta como Red funcional.

**L13-VC01 — NOT_RUN:** salida de build y capturas iniciales del CTA en landing/Storybook en condiciones equivalentes; comprobar correspondencia y registrar versión del adaptador. Aplicar contrato y salida comunes, 3/3 AC.

### L14 — Completar catálogo y detectar regresiones visuales

**Referencia de diseño:** [página y secciones](LANDING_DESIGN_REFERENCES.md#pagina).

**Capturas de referencia:** [f0UZM](../design/landing/2026-11-25/f0UZM.png) · [W72wy](../design/landing/2026-11-25/W72wy.png).

**Historia padre:** LW4. **Bloqueado por:** L04, L05, L06, L07, L08, L09, L13. **Actor:** Revisor/contribuidor. **Frontera:** Stories, página integrada y artefactos CI.

**Objetivo/alcance y pasos:** Auditar catálogo de navegación, CTA, tarjetas, pasos, FAQ, footer y composiciones de sección; añadir estados faltantes e interacciones; configurar capturas deterministas y reporte visual por ticket. Mantener IDs de stories estables y enlaces desde los tickets. Comparar con referencia Pen y con baseline aprobado cuando exista.

| IDs | Preparación | Acción / caso de uso | Resultado esperado / criterio de aceptación | Ejecución |
| --- | --- | --- | --- | --- |
| L14-UC01 → L14-AC01 → L14-TC01 | Componentes L04–L09 terminados | Recorrer catálogo y activar navegación/FAQ/CTA | Cada componente y estado aplicable tiene story, referencia Pen o indicación de diseño nuevo, ticket y prueba de interacción; cero enlaces rotos | Automatizada + manual |
| L14-UC02 → L14-AC02 → L14-TC02 | Baseline aprobado y modificación temporal que recorta CTA | Ejecutar comparación visual en condiciones fijadas | Detecta cambio, produce antes/después/diff y exige revisión; revertir defecto restaura resultado esperado sin regenerar baseline | Automatizada + manual |
| L14-UC03 → L14-AC03 → L14-TC03 | Secciones nuevas o cambio visual intencional | Generar reporte y revisar página completa en tres viewports | Evidencia inicial o comparativa según caso, diferencias trazadas a AC/TC con decisión explícita; no hay regresiones abiertas ni baselines aprobados automáticamente | Manual + automatizada |

**Red/Green/Refactor:** demostrar detección del defecto controlado, configurar reporte mínimo, estabilizar fuentes/datos/animación y repetir; verificar interacciones por comportamiento observable.

**L14-VC01 — NOT_RUN:** artefactos del detector visual y capturas de stories/página; el defecto temporal no se publica ni se conserva como baseline válido. Aplicar contrato y salida comunes, 3/3 AC.

## Secuencia y decisiones pendientes

1. L01 fija referencia y contenido. L02/L03 habilitan la primera entrega verificable y L13 incorpora Storybook antes de los componentes de L04.
2. L04/L05 construyen narrativa; después L06 y L07 pueden avanzar independientemente. L08 conecta una acción real y L09 completa información pública.
3. L14 completa el catálogo y la regresión visual; L10 y L11 comprueban el conjunto; L12 verifica hosting y publicación autorizada.

Pendientes concretos: aprobar ajustes respecto al diseño inspeccionado; confirmar destino/formato de demo o aceptar ancla Cómo funciona; asignar responsable de copy/contacto y textos legales; fijar dominio y accesos, y configurar Cloudflare Pages Free como proveedor acordado. Ninguno se considera resuelto por este borrador. L01 resuelve contenido y activos; L08 destino; L09 información pública; L12 infraestructura. No se asignan fechas ficticias ni se hereda automáticamente el objetivo del 5 de diciembre como estimación.

No hay dependencia de B35 para una landing informativa con ilustraciones. Anunciar integración bancaria real sí exige evidencia externa vigente del canal anunciado. L01 debe cerrar las decisiones de copy, assets y responsive que la inspección no aprueba por sí sola; no cerrar L12 sin verificación del entorno publicado. Una demo externa pendiente puede sustituirse por la explicación interna acordada, pero nunca por un enlace roto.

Publicar historias LW y subtareas L con relaciones padre/bloqueos y enlaces al protocolo. El mapa GITHUB_BACKLOG.md registrará los números y relaciones verificados. Publicar el plan no acredita implementación ni pruebas funcionales.
