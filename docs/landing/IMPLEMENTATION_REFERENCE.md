# L01 — referencia para implementar la landing

Ticket: [#93](https://github.com/luisjrez/Tappy/issues/93). Base: `96287d7`. Alcance aprobado: landing Astro estática y Storybook. Esta entrega fija inventario, copy y destinos; no es una web funcionando. Su aceptación humana corresponde al PR de L01.

## Diseño y assets

Referencia única de composición: [índice Pen](../planning/LANDING_DESIGN_REFERENCES.md), frame `f0UZM`, siete secciones a 1440 px. [Capturas originales y hashes](../design/landing/2026-11-25/manifest.json). El [inventario de archivos](ASSETS.json) identifica los 13 PNG y 6 shaders efectivamente referenciados por la landing, dimensiones, hashes y procedencia. No se incluyen otras pantallas móviles como alcance.

Los PNG/shaders proceden del material de diseño aportado en este repositorio. No hay un archivo de licencia específico para ellos: se reutilizan como material del proyecto solicitado por su autor, sin atribuirles una licencia abierta ni ofrecerlos como librería redistribuible. El responsable de producto conserva la confirmación de titularidad antes de publicación externa. Las capturas originales contienen copy anterior y no deben usarse como una sola imagen de la página.

Inter es la única familia leída en Pen. Incorporar la distribución oficial fijada a versión y su licencia SIL OFL 1.1 cuando L02/L04 empaquete la fuente; conservar el aviso. [Licencia oficial](https://github.com/rsms/inter/blob/master/LICENSE.txt). Fallback: system-ui, sans-serif. No solicitar fuentes a terceros durante navegación.

Los PNG con pantallas incluyen funciones pendientes y textos incrustados. Mantenerlos como referencia; para la landing pública, exportar/crear ilustraciones web corregidas en L04–L07, rotuladas «Ejemplo ilustrativo». Revisar específicamente el método experimental/NFC en `elige-metodo.png`, expiración en `esperando-pago.png`, avisos, filtros y compartir comprobantes. No reutilizar un bitmap contradictorio solo porque su texto no sea seleccionable.

## Decisiones visuales para web

- Tema claro con bandas verdes tal como Pen; sin selector de tema en esta primera entrega. El CSS oscuro previo es referencia de otros contextos, no una segunda landing comprometida.
- Inter; texto principal `#19221D`, secundario `#47564D`, marca `#185C46`, menta `#9AE6C0`; fondo `#FAFAF8`, hero `#F1F6F2`, sección pagador `#F5F0E6`, banda oscura `#0E3328`. Coinciden con Pen; conservar roles del sistema web.
- Contenido de escritorio 1200 px centrado (márgenes 120 a 1440); tipografía hero fluida 40–64 px, cuerpo 16–20 px. Espaciado en múltiplos de 4; controles al menos 48 px, foco 2 px con separación 2 px.
- A 768 px o menos: una columna, texto antes de ilustración, tarjetas y pasos en orden de lectura; navegación visible que puede envolver líneas sin ocultar enlaces. Márgenes 20 px, 16 px a 360 o menos. Evitar alturas fijas para copy. Comprobar 320, 360, 768 y 1440 px y zoom 200%.
- Fondos de waves/contour/dots/plus y barras son decorativos. Implementar equivalentes estáticos ligeros con CSS/SVG antes de añadir movimiento; no importar WebGL por defecto. Toda animación posterior respeta reduced-motion y nunca oculta contenido.
- Iconos de acción con nombre accesible; iconos decorativos fuera del árbol accesible. Logos e ilustraciones no sustituyen títulos o contenido HTML.

## Copy y decisiones por sección

Este copy concreta los ajustes previamente aprobados en el plan. Evita afirmar disponibilidad comercial; aceptación final en el PR. La columna original es referencia histórica, no copy publicable.

| Sección / nodo | Original | Decisión y copy de implementación | Fundamento |
| --- | --- | --- | --- |
| Hero `vuQjv` | Cobra en segundos | Corregir: «Cobra con claridad. Entrega cuando el pago esté confirmado.» | Sin promesa de tiempo; PRODUCT_BASE §4/6 |
| Hero `b0dyB` | QR, celular o enlace disponibles | Corregir: «Tappy está diseñado para ayudarte a solicitar cobros y consultar su recepción. El dinero llega a la cuenta bancaria de tu comercio.» | Canales pendientes no equivalen a oferta habilitada |
| Hero/chips | Sin terminal / directo a tu cuenta / no instala nada | Conservar con contexto: «Sin terminal», «A tu cuenta bancaria», «Tu cliente autoriza con su banco compatible» | No compatibilidad universal |
| CTA `KmZi2`, `Y2Spr`, `Bh2b1` | Empieza gratis / Probar Tappy | Corregir: «Cómo funciona» → `/#como-funciona` | Alta/precio/demo sin destino confirmado |
| Problema `aboaM` | Capturas, banco abierto y cuentas manuales | Conservar motivos; sustituir «Y entregas el pedido igual» por «Necesitas comprobar la recepción antes de entregar.» | No normalizar entregar sin evidencia |
| Pasos `z8o4Co` | Tres toques y el dinero va directo | Corregir: «Del importe a la confirmación, paso a paso.» | Sin garantizar cantidad de acciones ni recepción |
| Paso 1 | Escribe el monto | Conservar; indicar importe en MXN y concepto opcional | Dominio de cobro |
| Paso 2 `alA1q` | QR, celular o enlace | Corregir: «Genera la solicitud por un canal habilitado. La disponibilidad depende del recorrido bancario compatible.» | No anunciar los tres como operativos |
| Paso 3 `D4UX9` | Cuando el banco confirma… ni antes ni después | Corregir: «Comprueba el estado. “Pago recibido” aparece solo después de validar la evidencia de recepción.» | No inferir confirmación inmediata |
| Tus cobros `W72wy` | Capacidades en presente | Titular: «Así se verá el seguimiento de tus cobros». Subtítulo: «Ejemplos ilustrativos de la experiencia diseñada; las funciones disponibles se confirmarán al habilitar el acceso.» | Distinguir diseño y disponibilidad |
| Resumen / día por día | Ventas y desglose por métodos | Corregir: «Consulta lo recibido por día, semana y mes». Solo transferencias confirmadas; no saldo, utilidad ni ventas | CONTEXT / PRODUCT_BASE §6 |
| Historial `YvDtP` | Filtra por estado y método | Corregir: «Distingue cobros confirmados y pendientes.» | Filtros amplios no comprometidos |
| Comprobantes `Lx5RA` | Compártelo en un toque | Reformular: «Comprobantes: función diseñada, pendiente de disponibilidad.» | No prometer entrega implementada |
| Avisos `NDCGV` | Aunque tengas la app cerrada | Reformular: «Avisos: función diseñada, pendiente de disponibilidad.» Retirar promesa de segundo plano | Backend no garantiza push |
| Pagador `w2ypd` | Pagar es tan fácil… | Corregir: «Tu cliente revisa y autoriza desde su banco compatible.» Sin registro Tappy; compatibilidad depende del banco/canal | PRODUCT_BASE §5.1 |
| Compatibilidad `Az7b1` | Te decimos cuáles son compatibles | Corregir: «La compatibilidad depende de la institución bancaria y del canal habilitado.» | Sin lista validada |
| CTA final `r1fKtr` | Configura… en minutos | Corregir: «Conoce cómo Tappy busca simplificar los cobros de tu negocio.» Conservar «Cobra fácil. Sigue creciendo.» | Alta pública fuera de alcance |
| Contacto `GfXgk` | Hablar con nosotros | No habilitar enlace hasta definir contacto atendido; condición de L09/L12 | No inventar correo o teléfono |
| Footer `TX4dP` | Tappy no es un banco | Conservar; aclarar «Tappy no custodia fondos. El pago se autoriza desde una institución bancaria compatible.» | Producto y dominio |

## FAQ nueva (L07)

1. **¿Tappy guarda mi dinero?** No. El dinero llega a la cuenta bancaria receptora del comercio; Tappy no es una billetera.
2. **¿Ver un QR significa que ya recibí el pago?** No. La solicitud no confirma recepción; debes esperar la evidencia validada.
3. **¿Mi cliente necesita instalar Tappy?** No necesita registrarse en Tappy. Debe contar con un recorrido compatible en su institución bancaria.
4. **¿Puedo crear una cuenta ahora?** El alta pública aún no está disponible. Esta página explica la experiencia diseñada.
5. **¿Qué pasa si el estado no está confirmado?** No asumas recepción. Comprueba el estado antes de entregar; una captura del pagador no sustituye la validación.

## Destinos y responsables

| Acción | Destino | Estado / desbloqueo | Responsable |
| --- | --- | --- | --- |
| Logo | `/` | Disponible al implementar L04 | Implementador L04 |
| Cómo funciona / CTA | `/#como-funciona` | Alternativa acordada mientras no hay demo | Implementador L05/L08 |
| Tus cobros | `/#tus-cobros` | Sección ilustrativa L06 | Implementador L06 |
| Para tu cliente | `/#para-tu-cliente` | Sección L07 | Implementador L07 |
| Ayuda | `/#ayuda` | FAQ nueva en L07 | Implementador L07 |
| Ver demo | Sin URL | No habilitar; requiere demo accesible y etiquetada | Producto: persona por asignar |
| Contacto | Sin URL/correo | L09/L12 bloquean publicación hasta contacto atendido | Producto: persona por asignar |
| Privacidad / términos | `/privacidad`, `/terminos` propuestas | L09 requiere textos aprobados; no publicar placeholders | Producto: persona por asignar |
| Dominio público | Sin dominio | Cloudflare Pages Free acordado; accesos en L12 | Operación: persona por asignar |

Pendientes de destino no bloquean la base técnica ni redactar esta referencia: L01-AC03 exige registrarlos con responsable por asignar y condición. Sí bloquean declarar L09/L12 completos. No cerrar L01 ni levantar su bloqueo de L02 automáticamente: requiere revisión humana del PR.
