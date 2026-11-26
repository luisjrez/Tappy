# Landing — índice de diseño para tickets

Inspección MCP del 25 de noviembre de 2026. Referencia: [tappy-design.pen](../../tappy-design.pen), frame **Landing A · Mostrador**, ID `f0UZM`. Documento abierto inspeccionado: `/Users/luisjuarez/dev/Tappy/tappy-design.pen`; también se consultó el frame y sus hijos en el archivo del worktree. No se editó ni guardó Pen. Este índice no acredita implementación.

Los enlaces siguientes llevan a fichas de sección; cada ficha identifica el nodo exacto. No se dispone de un permalink de Pen verificado que seleccione automáticamente un nodo. Para localizarlo con MCP, abrir el archivo y consultar `Get` con su ID. Al publicar tickets, enlazar este índice a un commit concreto junto con el ID. No inventar un fragmento de URL como si fuera un deep link funcional.

## Capturas locales verificadas

Exportadas por MCP a PNG 1×, con [manifest de integridad](../design/landing/2026-11-25/manifest.json). Estas imágenes permiten revisar sin tener Pen abierto. Son referencia del diseño original; las correcciones de copy y secciones nuevas siguen documentadas abajo.

| Referencia | PNG |
| --- | --- |
| Página completa · `f0UZM` | [Abrir captura](../design/landing/2026-11-25/f0UZM.png) |
| Header completo · `Q6PIC0` | [Abrir captura](../design/landing/2026-11-25/Q6PIC0.png) |
| Navegación · `v8LGy` | [Abrir captura](../design/landing/2026-11-25/v8LGy.png) |
| Hero · `w7Vwm1` | [Abrir captura](../design/landing/2026-11-25/w7Vwm1.png) |
| Problema · `aboaM` | [Abrir captura](../design/landing/2026-11-25/aboaM.png) |
| Cómo funciona · `mBQBr` | [Abrir captura](../design/landing/2026-11-25/mBQBr.png) |
| Tus cobros · `W72wy` | [Abrir captura](../design/landing/2026-11-25/W72wy.png) |
| Resumen e historial · `NvxvB` | [Abrir captura](../design/landing/2026-11-25/NvxvB.png) |
| Comprobantes, avisos y día por día · `r8djG` | [Abrir captura](../design/landing/2026-11-25/r8djG.png) |
| Para tu cliente · `w2ypd` | [Abrir captura](../design/landing/2026-11-25/w2ypd.png) |
| CTA final · `Fo93N` | [Abrir captura](../design/landing/2026-11-25/Fo93N.png) |
| Footer · `ezjQ3` | [Abrir captura](../design/landing/2026-11-25/ezjQ3.png) |

## Pagina

Frame `f0UZM`: 1440 × 5924, siete bloques, orden vertical. Cabecera clara con ilustraciones de teléfonos; problema en verde oscuro; pasos sobre blanco; beneficios en verde; pagador sobre crema; CTA verde; footer oscuro. Solo se encontró una composición de landing de escritorio entre los nodos superiores; adaptación responsive se especifica en L01 y verifica en L10, no se atribuye a un frame móvil existente.

| Sección | Node ID | Y relativo / alto | Tickets |
| --- | --- | --- | --- |
| [Header](#header) | Q6PIC0 | 0 / 1019 | L04, L08 |
| [Problema](#problema-y-pasos) | aboaM | 1019 / 727 | L05 |
| [Cómo funciona](#problema-y-pasos) | mBQBr | 1746 / 964 | L05 |
| [Tus cobros](#tus-cobros) | W72wy | 2710 / 1607 | L06 |
| [Para tu cliente](#pagador-y-ayuda) | w2ypd | 4317 / 940 | L07 |
| [CTA Final](#cta-final) | Fo93N | 5257 / 560 | L08 |
| [Footer](#footer) | ezjQ3 | 5817 / 107 | L09 |

L02/L03/L11/L12 usan la página como contexto; sus entregas técnicas no tienen un frame propio. L10/L14 verifican todo el conjunto. L13 usa los componentes pertinentes del inventario.

## Inventario

L01: referencia global `f0UZM` y todas las fichas. Completar inventario de assets exportables/licencias, fuentes, tokens, temas y reglas responsive antes de implementar. Las imágenes de teléfonos se usan como material ilustrativo de web, no como implementación de mobile.

L13/L14: catálogo web propuesto de enlace/CTA, navegación, tarjeta de problema, paso, tarjeta de beneficio, FAQ y footer, además de composición de las secciones. Debe consumir las piezas reales que renderiza la landing. El catálogo de componentes reutilizables del documento contiene también piezas móviles: no incorporarlas automáticamente. No existe un frame de FAQ en esta landing; sus stories deben decir «diseño nuevo» hasta aprobar la referencia.

## Header

`Q6PIC0` contiene navegación `v8LGy` (71 px de alto) y hero `w7Vwm1` (948 px). Navegación: Cómo funciona, Tus cobros, Para tu cliente, Ayuda y Probar Tappy. Hero: propuesta, dos CTA, chips, teléfonos y ejemplos de importe. Decoración `dfoKC` (Waves · motion).

L04: conservar jerarquía y navegación accesible; implementar anclas válidas. L08: unificar acción disponible. Textos a revisar: `KmZi2` «Empieza gratis», `b0dyB` tres canales anunciados, `vuQjv` «Cobra en segundos». Los importes sintéticos deben rotularse ilustrativos. Evidencia: hero completo, foco y versión estrecha; movimiento reducido para decoración.

## Problema y pasos

Problema `aboaM`, encabezado `Ah6oc`, tarjetas `sJOI7`. Tres motivos: capturas no prueban recepción, consultar repetidamente el banco y cuentas manuales al cierre. Decoración `AvH4C`.

Cómo funciona `mBQBr`, encabezado `c7cWn`, pasos `fHFO8`. Escribir monto, elegir canal, esperar confirmación. Decoración `eG6dF`. Revisar `z8o4Co` «Tres toques» y `alA1q` disponibilidad de QR/celular/enlace. Conservar regla de recepción validada, sin prometer tiempo ni recorrido universal.

L05: evidencia de ambas secciones y orden de pasos en ancho estrecho. Mantener lectura sin decoraciones ni JS.

## Tus cobros

`W72wy`, encabezado `DmPmz`, primera fila `NvxvB`, segunda fila `r8djG`, decoración `SgF0s`. Cinco beneficios: resumen, historial, comprobantes, avisos y día por día.

L06: revisar disponibilidad de filtros (`YvDtP`), desglose por canales (`O4Ta1`), compartir comprobante (`Lx5RA`) y notificación con app cerrada (`NDCGV`). No suprimir silenciosamente tarjetas: registrar conservar, reformular como visión o retirar según alcance aprobado. «Recibido» no equivale a ventas, saldo ni utilidad. Evidencia: cada tarjeta, textos y ejemplos, responsive y carga de imágenes.

## Pagador y ayuda

Para tu cliente `w2ypd`, visual `Jwm0J`, copy `s5XdS`, decoración `qGjFf`. Explica revisar datos y autorizar con banco compatible. `Az7b1` promete informar bancos compatibles: requiere información sustentada o reformulación. Comprobante `ThVYe` depende de disponibilidad.

**Ayuda/FAQ no existe como sección en este frame**, aunque navegación `H9wQS8` dice Ayuda. L07 añade FAQ y destino de ancla aprobado; es una ampliación explícita al diseño. Evidencia: sección del pagador y FAQ nueva abierta/cerrada, teclado, foco y lector. No crear un checkout.

## CTA final

`Fo93N`, contenido `mR9RT`, decoraciones `G6wzDh` y `Q1U0Cy`. Frase de marca `BoTpk`: «Cobra fácil. Sigue creciendo.» Texto `r1fKtr`: alta en minutos; CTA `Y2Spr`: gratis; secundario `GfXgk`: hablar con nosotros.

L08 reemplaza promesas no confirmadas por acción disponible y copy aprobado. Alinear CTA de header/hero/final. Contacto secundario se verifica con L09. Evidencia: destino demo aprobado o alternativa interna, foco y movimiento reducido.

## Footer

`ezjQ3`, wordmark `HOPZo`, aviso `TX4dP` y copyright `X4png5`. **No contiene enlaces de términos, privacidad ni contacto**. L09 los incorpora como ampliación explícita y requiere textos/destino aprobados. Páginas informativas tampoco tienen frame en esta landing.

Evidencia: footer responsive, rutas informativas y retorno; no publicar enlaces vacíos ni datos de contacto inventados.

## Cómo revisar diferencias

Aplicar la sección «Evidencia visual revisable por ticket» del [borrador](LANDING_TICKETS_DRAFT.md#evidencia-visual-revisable-por-ticket). Referencia Pen + primera implementación para lo nuevo; antes/después/diff para cambios posteriores. Cada diferencia debe tener motivo, ticket, criterio y decisión. Esta inspección no aprueba los cambios de copy ni las nuevas secciones: forman parte de la revisión solicitada del borrador.
