# Tappy · Sistema de diseño web

Versión 1.0 · Dirección Encuentro. Sistema para la landing y los componentes web de cobros y ventas. Conserva la voz en español de México, la jerarquía de importe y estado, y los temas claro y oscuro de la [especificación de marca](../TAPPY_BRAND_IDENTITY_SPEC.md).

> **Alcance actualizado · 10 de noviembre de 2026:** NFC queda fuera del proyecto actual. Las láminas conservan su valor como referencias visuales; sus estados no demuestran capacidades bancarias. El alcance y la correspondencia entre estados de UI y de cobro se definen en la [documentación del hackathon](../docs/README.md). En particular, `cancelled` no implica cancelación bancaria y la incertidumbre no se presenta como rechazo.

## Láminas

| Lámina | Contenido |
| --- | --- |
| [01 · Color y temas](laminas/01-color-y-temas.png) | Superficies, texto, acciones y colores semánticos |
| [02 · Tipografía, espacio e iconos](laminas/02-tipografia-espacio-iconos.png) | Jerarquías, cifras tabulares, retícula y radios |
| [03 · Acciones y formularios](laminas/03-acciones-y-formularios.png) | Botones, importe, foco, error y envío |
| [04 · Navegación y capas](laminas/04-navegacion-y-capas.png) | Pestañas, navegación, menú y diálogo |
| [05 · Estados y avisos](laminas/05-estados-y-avisos.png) | Estados del cobro, desconexión y contenido vacío |
| [06 · Datos y métricas](laminas/06-datos-y-metricas.png) | Total, gráfica y tabla |
| [07 · Patrones web](laminas/07-patrones-web.png) | Aviso de lanzamiento y selección de método |
| [08 · Movimiento y accesibilidad](laminas/08-movimiento-y-accesibilidad.png) | Fotogramas de Encuentro, foco y movimiento reducido |

Los PNG son referencias visuales. Para implementar colores, medidas y comportamiento, usa [tappy-theme.css](tappy-theme.css) y esta guía.

## Integración con shadcn/ui

1. En un proyecto web con Tailwind CSS v4, activa `tailwind.cssVariables` en `components.json`. Mantén los imports y estilos base de la instalación.
2. Importa `tappy-theme.css` desde la hoja global, después de los imports de Tailwind y shadcn/ui y antes de las reglas de estilo. Sustituye las declaraciones del tema anterior que definan los mismos tokens.
3. Alterna `.dark` en el elemento raíz con el proveedor de tema de la aplicación. Expón Inter en `--font-inter` en ese mismo elemento si usas un cargador de fuentes. El tema incluye fallback a la fuente del sistema.
4. En los componentes copiados de shadcn/ui, ajusta los controles primarios a `min-h-control rounded-lg`. Si el control solo contiene un icono, aplica también `min-w-control` y dale un nombre accesible. Para contornos funcionales usa `border-input`. Reserva `border-border` para divisores y contornos decorativos.
5. En el foco de teclado, aplica un contorno sólido de 2 px con separación de 2 px. Usa `outline-ring` en las superficies normales y `outline-brand-ring` en la franja de marca. Revisa las clases de foco del preset para evitar indicadores duplicados o una opacidad que reduzca el contraste.

[Temas de shadcn/ui](https://ui.shadcn.com/docs/theming) · [Configuración de shadcn/ui](https://ui.shadcn.com/docs/components-json)

## Fundamentos

- **Marca.** Wordmark en minúsculas y símbolo Encuentro. Conserva la separación y el desplazamiento vertical entre las dos mitades. Valida la legibilidad del conjunto a 24 px de alto y la del símbolo a 20 × 20 px. Al preparar el SVG maestro, documenta la zona de seguridad con la altura del trazo principal como mínimo, según la especificación de marca.
- **Color.** Usa superficies cálidas como base. El verde bosque o menta identifica las acciones principales según el tema. Para confirmar, esperar o recuperar un error usa fondo semántico, icono y etiqueta. En la franja de lanzamiento usa la familia fija `brand-surface` y `brand-action`.
- **Espacio.** Retícula de 4 px con pasos de 4, 8, 12, 16, 24, 32 y 48 px. Contenedor máximo de 80 rem y márgenes fluidos de 1 a 2.5 rem. Al reducir el ancho, apila columnas conservando el orden de lectura.
- **Forma.** 12 px en controles, 16–20 px en tarjetas y 24 px en superficies grandes. Sombras suaves solo para capas flotantes. Los controles principales crecen con el contenido desde un objetivo de 48 × 48 CSS px.
- **Iconos.** Usa Lucide como referencia, con trazos de 1.75–2 px en una retícula de 24 px. Acompaña los iconos de estados y acciones críticas con texto visible. El símbolo de marca y los iconos funcionales tienen funciones separadas.
- **Importes.** Formatea con `Intl.NumberFormat("es-MX", { style: "currency", currency: "MXN" })`. Usa `tabular-nums` y alinea cifras a la derecha en tablas. Identifica MXN en el importe o en el encabezado de un grupo.

| Rol | Tamaño y línea | Peso |
| --- | --- | --- |
| Hero de la landing | Fluido de 40 a 80 px, línea 1.05 | 650–700 |
| Importe destacado | 40–48 px, línea 1.1 | 650–700 |
| Título de página | 28–32 px, línea 1.2 | 650–700 |
| Título de sección | 20–24 px, línea 1.3 | 600–650 |
| Cuerpo y campos | 16–18 px, línea 1.5 | 400–500 |
| Etiqueta | 16 px, línea 1.4 | 500–600 |
| Ayuda y metadatos | 14–16 px, línea 1.4 | 400–500 |

Usa unidades relativas en la implementación y permite que el texto se distribuya en varias líneas. En la landing, la fotografía editorial usa luz natural y comercios mexicanos como contexto visual. El titular y la acción permanecen como HTML.

## Componentes

| Familia | Primitivas shadcn/ui | Reglas de Tappy |
| --- | --- | --- |
| Acciones | Button, Button Group | `default` para una acción principal por bloque, `secondary` y `outline` para alternativas, `ghost` para acciones de apoyo, `link` para navegación en línea, `destructive` para acciones irreversibles. Si es sólido, combina `bg-destructive` con `text-destructive-foreground`. |
| Entrada de datos | Field, Input, Input Group, Textarea | Etiqueta persistente y ayuda asociada. Usa `data-invalid` en Field, `aria-invalid` en el control y `aria-describedby` para enlazar el error. Conserva el valor cuando falle el envío. |
| Selección | Radio Group, Select, Checkbox, Switch | Radio Group para una opción entre pocas alternativas visibles. Select para listas largas. Checkbox para aceptación o selección múltiple. Switch para preferencias de efecto inmediato. |
| Navegación | Navigation Menu, Breadcrumb, Tabs, Pagination | Enlaces para cambiar de página, Tabs para contenido del mismo contexto. Marca la página actual y la pestaña seleccionada con semántica además de estilo. |
| Capas | Dropdown Menu, Popover, Tooltip, Dialog, Alert Dialog, Sheet | Menú para acciones, Popover para controles breves, Dialog para revisar el cobro, Alert Dialog para confirmar una acción destructiva y Sheet para detalle ampliado. Tooltip complementa el nombre accesible. Devuelve el foco al disparador al cerrar. |
| Avisos | Badge, Alert, Empty, Skeleton, Spinner | Badge con texto e icono. Alert persistente para problemas que requieren acción. Empty explica qué falta y cómo empezar. En carga, conserva el espacio y ofrece texto de progreso. |
| Datos | Card, Table, Data Table, Chart | Periodo visible y totales en MXN. Ordenamiento y filtros en Data Table cuando aporten valor. En Chart, añade `accessibilityLayer`, un resumen y una vista de tabla con los mismos datos. |
| Marketing | Accordion, Separator, Field, Button | Accordion para preguntas frecuentes. El CTA primario «Avísame del lanzamiento» apunta al registro, que usa etiqueta de correo visible y un enlace de privacidad. |

[Variantes de Button](https://ui.shadcn.com/docs/components/button) · [Errores en Field](https://ui.shadcn.com/docs/components/field) · [Accesibilidad de Chart](https://ui.shadcn.com/docs/components/chart#accessibility)

**Estados de interacción.** En hover y active, usa un cambio tonal discreto y conserva el contraste. Focus-visible conserva la apariencia base y añade el contorno. Durante el envío, conserva el ancho del botón, muestra texto como «Enviando…» e impide el envío duplicado. Si una opción está deshabilitada por compatibilidad o por un requisito pendiente, explica el motivo con texto visible.

## Patrones de cobro

| Estado de dominio | Etiqueta | Tratamiento |
| --- | --- | --- |
| `draft` | Borrador | Neutral · documento |
| `creating` | Creando solicitud | Neutral · indicador de carga con texto |
| `pending` | Pendiente | Ámbar · reloj. «Solicitud enviada. Esperando pago.» |
| `paid` | Pago recibido | Verde · círculo con palomita. Muestra importe, fecha e identificador después de la verificación. |
| `expired` | Vencido | Neutral · calendario. «La solicitud venció. Puedes crear otra.» |
| `failed` | Pago fallido | Rojo · círculo con cruz. Explica el problema y la acción disponible. |
| `cancelled` | Cancelado | Neutral · círculo tachado |
| `unknown` | Sin verificar | Neutral · icono de ayuda. Explica por qué la verificación está pendiente, si se conoce el motivo. |

- **MoneyInput.** Compón `Field` e `Input Group` con prefijo $, sufijo MXN y teclado decimal. Durante la edición conserva el texto para permitir entradas parciales. Valida y representa el valor monetario en centavos al confirmar. En el diálogo muestra comercio, concepto si existe, importe y «Crear solicitud».
- **PaymentMethodPicker.** Presenta QR, celular y enlace según disponibilidad. Solo incluye NFC en un contexto experimental con compatibilidad comprobada y un método alternativo. En el checkout identifica comercio e importe y explica que el cliente autoriza en su banco compatible, sin cuenta de Tappy.
- **PaymentStatus.** El backend es la fuente del estado `paid`. Si la conexión se pierde antes de verificar, conserva el importe y explica que el estado sigue sin verificar. Anuncia las transiciones relevantes en una región `aria-live="polite"`, sin repetir el anuncio durante cada consulta.
- **TransactionRow y MetricCard.** En el historial muestra método, fecha, monto, referencia y estado de cada operación. Para el resumen, deriva el total, la gráfica y su tabla alternativa del mismo conjunto filtrado de pagos confirmados. En la lámina 06, 300 + 450 + 750 = 1,500 MXN. La solicitud pendiente de 120 MXN queda fuera de ese total.
- **Registro de lanzamiento.** Define reposo, validación, enviando, error y registro confirmado. Confirma con «Te avisaremos cuando Tappy esté listo» al recibir respuesta satisfactoria. En pantallas estrechas apila campo y botón.

## Movimiento

| Uso | Duración | Comportamiento |
| --- | --- | --- |
| Hover y press | 120 ms | Cambio de color, borde u opacidad |
| Menú, pestaña y aviso | 180 ms | Transición breve. Foco y cambio semántico inmediatos. |
| Aparición de capa | 220 ms | Opacidad y desplazamiento máximo de 8 px |
| Encuentro en portada y cierre | 520 ms | Las mitades se acercan una vez, conservan el eje y se detienen antes de tocarse. El texto y el formulario permanecen fijos. |

Usa `--tappy-ease-out` para las entradas. En «Cómo funciona», anima el trazo de la línea sin ocultar los pasos. En confirmación y métricas, el estado y los datos se actualizan inmediatamente. El trazo y el crecimiento de las barras pueden acompañarlos de forma decorativa. Con `prefers-reduced-motion`, muestra la composición final, detén los bucles decorativos y sustituye el giro del spinner por un indicador estático con texto.

## Accesibilidad y verificación

Los pares sólidos de la paleta se comprobaron en ambos temas. El contraste mínimo medido en los pares de texto evaluados fue 5.77:1 y el de bordes funcionales 3.46:1. Los indicadores de foco evaluados alcanzaron al menos 4.59:1. Las pruebas se hicieron sobre los valores CSS, con el color aplicado a opacidad completa. [WCAG 2.2 · Contraste de texto](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html) · [WCAG 2.2 · Contraste no textual](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html)

Al integrar los componentes, verifica teclado y foco, lectura de montos y estados con lector de pantalla, reflujo a 320 CSS px, zoom al 200%, ambos temas, errores de formulario y movimiento reducido. Comprueba cada estado renderizado con sus fondos y opacidades reales. Los valores de la paleta y las láminas sirven de referencia para esa revisión.
