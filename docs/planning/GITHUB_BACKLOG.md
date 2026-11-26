# Backend Tappy — mapa de GitHub

Tracker: [luisjrez/Tappy](https://github.com/luisjrez/Tappy/issues). Publicación y relaciones verificadas mediante API de GitHub. Todos los issues están abiertos; ninguna implementación o prueba funcional se ha ejecutado.

8 historias padre, 42 subtareas, 42 relaciones de sub-issue y 68 bloqueos nativos.

[Protocolo de calidad](TICKET_QUALITY_PROTOCOL.md) · [Plan detallado](BACKEND_TICKETS_DRAFT.md) · [Plantilla de evidencia](EVIDENCE_COMPARISON_TEMPLATE.md).

Cada subtarea contiene UC/AC/TC, TDD, criterios, dependencias, evidencia inicial/comparativa según aplique y salida por review/PR. `ready-for-agent` no elimina bloqueos. B35 requiere ejecución humana; celular/enlace están etiquetados como alcance adicional.

## [H1 — Base local verificable](https://github.com/luisjrez/Tappy/issues/1)

| Subtarea | Issue | Bloqueada por |
| --- | --- | --- |
| B01 — Arrancar API modular y health | [#9](https://github.com/luisjrez/Tappy/issues/9) | Sin bloqueos internos |
| B02 — Levantar Postgres y aplicar primera migración | [#10](https://github.com/luisjrez/Tappy/issues/10) | [B01](https://github.com/luisjrez/Tappy/issues/9) |
| B03 — Ejecutar checks y pruebas en CI | [#11](https://github.com/luisjrez/Tappy/issues/11) | [B02](https://github.com/luisjrez/Tappy/issues/10) |

## [H2 — Identidad y acceso operativo](https://github.com/luisjrez/Tappy/issues/2)

| Subtarea | Issue | Bloqueada por |
| --- | --- | --- |
| B04 — Provisionar el primer administrador | [#12](https://github.com/luisjrez/Tappy/issues/12) | [B02](https://github.com/luisjrez/Tappy/issues/10) |
| B05 — Iniciar sesión y consultar identidad | [#13](https://github.com/luisjrez/Tappy/issues/13) | [B04](https://github.com/luisjrez/Tappy/issues/12) |
| B06 — Expirar, renovar y revocar sesiones | [#14](https://github.com/luisjrez/Tappy/issues/14) | [B05](https://github.com/luisjrez/Tappy/issues/13) |
| B07 — Entrar y salir de Starlette Admin | [#15](https://github.com/luisjrez/Tappy/issues/15) | [B06](https://github.com/luisjrez/Tappy/issues/14) |
| B08 — Administrar operadores autorizados | [#16](https://github.com/luisjrez/Tappy/issues/16) | [B07](https://github.com/luisjrez/Tappy/issues/15) |

| B41 — Solicitar recuperación de contraseña por correo | [#49](https://github.com/luisjrez/Tappy/issues/49) | [B05](https://github.com/luisjrez/Tappy/issues/13), [B07](https://github.com/luisjrez/Tappy/issues/15) |
| B42 — Restablecer contraseña y revocar sesiones anteriores | [#50](https://github.com/luisjrez/Tappy/issues/50) | [B41](https://github.com/luisjrez/Tappy/issues/49), [B06](https://github.com/luisjrez/Tappy/issues/14) |

## [H3 — Comercio y receptor autorizado](https://github.com/luisjrez/Tappy/issues/3)

| Subtarea | Issue | Bloqueada por |
| --- | --- | --- |
| B09 — Configurar comercio y membresía | [#17](https://github.com/luisjrez/Tappy/issues/17) | [B08](https://github.com/luisjrez/Tappy/issues/16) |
| B10 — Configurar y consultar receptor | [#18](https://github.com/luisjrez/Tappy/issues/18) | [B09](https://github.com/luisjrez/Tappy/issues/17) |

## [H4 — Solicitar y recuperar un cobro QR](https://github.com/luisjrez/Tappy/issues/4)

| Subtarea | Issue | Bloqueada por |
| --- | --- | --- |
| B11 — Crear y consultar un cobro | [#19](https://github.com/luisjrez/Tappy/issues/19) | [B10](https://github.com/luisjrez/Tappy/issues/18) |
| B12 — Repetir creación sin duplicar venta | [#20](https://github.com/luisjrez/Tappy/issues/20) | [B11](https://github.com/luisjrez/Tappy/issues/19) |
| B13 — Reservar un único intento activo | [#21](https://github.com/luisjrez/Tappy/issues/21) | [B12](https://github.com/luisjrez/Tappy/issues/20) |
| B14 — Mostrar QR pendiente con proveedor simulado | [#22](https://github.com/luisjrez/Tappy/issues/22) | [B13](https://github.com/luisjrez/Tappy/issues/21) |
| B15 — Crear QR auténtico mediante pey | [#23](https://github.com/luisjrez/Tappy/issues/23) | [B14](https://github.com/luisjrez/Tappy/issues/22) |
| B16 — Recuperar creación QR incierta | [#24](https://github.com/luisjrez/Tappy/issues/24) | [B15](https://github.com/luisjrez/Tappy/issues/23) |

## [H5 — Comprobar recepción sin duplicar dinero](https://github.com/luisjrez/Tappy/issues/5)

| Subtarea | Issue | Bloqueada por |
| --- | --- | --- |
| B17 — Recibir y conservar webhook válido | [#25](https://github.com/luisjrez/Tappy/issues/25) | [B14](https://github.com/luisjrez/Tappy/issues/22) |
| B18 — Confirmar una recepción exacta | [#26](https://github.com/luisjrez/Tappy/issues/26) | [B17](https://github.com/luisjrez/Tappy/issues/25) |
| B19 — Deduplicar eventos y transferencias | [#27](https://github.com/luisjrez/Tappy/issues/27) | [B18](https://github.com/luisjrez/Tappy/issues/26) |
| B20 — Conservar discrepancias como incidencia | [#28](https://github.com/luisjrez/Tappy/issues/28) | [B18](https://github.com/luisjrez/Tappy/issues/26) |
| B21 — Procesar eventos anticipados y desordenados | [#29](https://github.com/luisjrez/Tappy/issues/29) | [B19](https://github.com/luisjrez/Tappy/issues/27) |
| B22 — Conciliar QR cuando falta notificación | [#30](https://github.com/luisjrez/Tappy/issues/30) | [B16](https://github.com/luisjrez/Tappy/issues/24), [B18](https://github.com/luisjrez/Tappy/issues/26) |
| B23 — Recuperar trabajos tras reinicio | [#31](https://github.com/luisjrez/Tappy/issues/31) | [B22](https://github.com/luisjrez/Tappy/issues/30), [B19](https://github.com/luisjrez/Tappy/issues/27) |
| B24 — Vencer QR sin inventar cancelación | [#32](https://github.com/luisjrez/Tappy/issues/32) | [B21](https://github.com/luisjrez/Tappy/issues/29) |
| B25 — Reintentar la misma venta con control | [#33](https://github.com/luisjrez/Tappy/issues/33) | [B24](https://github.com/luisjrez/Tappy/issues/32), [B23](https://github.com/luisjrez/Tappy/issues/31) |
| B26 — Registrar pago tardío y doble recepción | [#34](https://github.com/luisjrez/Tappy/issues/34) | [B25](https://github.com/luisjrez/Tappy/issues/33), [B20](https://github.com/luisjrez/Tappy/issues/28) |

## [H6 — Consultar y operar el negocio](https://github.com/luisjrez/Tappy/issues/6)

| Subtarea | Issue | Bloqueada por |
| --- | --- | --- |
| B27 — Consultar historial paginado | [#35](https://github.com/luisjrez/Tappy/issues/35) | [B18](https://github.com/luisjrez/Tappy/issues/26) |
| B28 — Compartir datos de comprobante verificado | [#36](https://github.com/luisjrez/Tappy/issues/36) | [B18](https://github.com/luisjrez/Tappy/issues/26) |
| B29 — Consultar resumen diario | [#37](https://github.com/luisjrez/Tappy/issues/37) | [B27](https://github.com/luisjrez/Tappy/issues/35), [B26](https://github.com/luisjrez/Tappy/issues/34) |
| B30 — Consultar semana y mes con fechas locales | [#38](https://github.com/luisjrez/Tappy/issues/38) | [B29](https://github.com/luisjrez/Tappy/issues/37) |
| B31 — Inspeccionar cobros desde back office | [#39](https://github.com/luisjrez/Tappy/issues/39) | [B07](https://github.com/luisjrez/Tappy/issues/15), [B27](https://github.com/luisjrez/Tappy/issues/35), [B28](https://github.com/luisjrez/Tappy/issues/36) |
| B32 — Revisar incidencias desde back office | [#40](https://github.com/luisjrez/Tappy/issues/40) | [B31](https://github.com/luisjrez/Tappy/issues/39), [B20](https://github.com/luisjrez/Tappy/issues/28), [B23](https://github.com/luisjrez/Tappy/issues/31) |

## [H7 — Operación e integración comprobable](https://github.com/luisjrez/Tappy/issues/7)

| Subtarea | Issue | Bloqueada por |
| --- | --- | --- |
| B33 — Limitar creación y consultas externas | [#41](https://github.com/luisjrez/Tappy/issues/41) | [B16](https://github.com/luisjrez/Tappy/issues/24), [B23](https://github.com/luisjrez/Tappy/issues/31) |
| B34 — Diagnosticar y restaurar operación | [#42](https://github.com/luisjrez/Tappy/issues/42) | [B23](https://github.com/luisjrez/Tappy/issues/31), [B31](https://github.com/luisjrez/Tappy/issues/39) |
| B35 — Verificar QR real de extremo a extremo | [#43](https://github.com/luisjrez/Tappy/issues/43) | [B15](https://github.com/luisjrez/Tappy/issues/23), [B26](https://github.com/luisjrez/Tappy/issues/34), [B30](https://github.com/luisjrez/Tappy/issues/38), [B33](https://github.com/luisjrez/Tappy/issues/41), [B34](https://github.com/luisjrez/Tappy/issues/42) |

## [H8 — Canales adicionales y contrato para clientes](https://github.com/luisjrez/Tappy/issues/8)

| Subtarea | Issue | Bloqueada por |
| --- | --- | --- |
| B36 — Crear solicitud al celular | [#44](https://github.com/luisjrez/Tappy/issues/44) | [B13](https://github.com/luisjrez/Tappy/issues/21), [B16](https://github.com/luisjrez/Tappy/issues/24), [B33](https://github.com/luisjrez/Tappy/issues/41) |
| B37 — Conciliar y confirmar pago al celular | [#45](https://github.com/luisjrez/Tappy/issues/45) | [B36](https://github.com/luisjrez/Tappy/issues/44), [B23](https://github.com/luisjrez/Tappy/issues/31), [B19](https://github.com/luisjrez/Tappy/issues/27) |
| B38 — Crear y compartir enlace oficial | [#46](https://github.com/luisjrez/Tappy/issues/46) | [B13](https://github.com/luisjrez/Tappy/issues/21), [B16](https://github.com/luisjrez/Tappy/issues/24), [B33](https://github.com/luisjrez/Tappy/issues/41) |
| B39 — Conciliar y confirmar pago por enlace | [#47](https://github.com/luisjrez/Tappy/issues/47) | [B38](https://github.com/luisjrez/Tappy/issues/46), [B23](https://github.com/luisjrez/Tappy/issues/31), [B20](https://github.com/luisjrez/Tappy/issues/28) |
| B40 — Verificar contrato común para mobile | [#48](https://github.com/luisjrez/Tappy/issues/48) | [B30](https://github.com/luisjrez/Tappy/issues/38), [B28](https://github.com/luisjrez/Tappy/issues/36), [B35](https://github.com/luisjrez/Tappy/issues/43) |

## Cómo empezar

B01 es la frontera inicial sin bloqueos internos. Resolver un incremento con su protocolo completo antes de ampliar alcance. Después avanzar solo a subtareas cuyos bloqueos estén cerrados y dependencias externas disponibles. Las historias no se cierran automáticamente ni por promedio de completitud. GitHub es la fuente del estado vivo; este archivo registra el mapa publicado.


# Landing Tappy — mapa publicado

18 issues abiertos: 4 historias y 14 subtareas; 14 relaciones padre/hijo y 31 bloqueos nativos verificados mediante API. Publicación no implica implementación: AC/TC/VC siguen NOT_RUN. L01/L12 requieren intervención humana; el resto ready-for-agent sujeto a bloqueos.

[Plan aprobado](LANDING_TICKETS_DRAFT.md) · [Diseño y capturas](LANDING_DESIGN_REFERENCES.md) · [Hosting acordado](../research/landing-preview-hosting.md).

## [LW1 — Base web y catálogo de componentes](https://github.com/luisjrez/Tappy/issues/89)

| Subtarea | Issue | Bloqueada por |
| --- | --- | --- |
| L01 — Consolidar referencia y copy web | [#93](https://github.com/luisjrez/Tappy/issues/93) | Sin bloqueos internos |
| L02 — Servir la primera página estática | [#94](https://github.com/luisjrez/Tappy/issues/94) | [L01](https://github.com/luisjrez/Tappy/issues/93) |
| L03 — Verificar cambios web en CI | [#95](https://github.com/luisjrez/Tappy/issues/95) | [L02](https://github.com/luisjrez/Tappy/issues/94) |
| L13 — Habilitar Storybook con componentes reales | [#96](https://github.com/luisjrez/Tappy/issues/96) | [L02](https://github.com/luisjrez/Tappy/issues/94), [L03](https://github.com/luisjrez/Tappy/issues/95) |

## [LW2 — Explicar qué hace Tappy](https://github.com/luisjrez/Tappy/issues/90)

| Subtarea | Issue | Bloqueada por |
| --- | --- | --- |
| L04 — Presentar propuesta y navegación | [#97](https://github.com/luisjrez/Tappy/issues/97) | [L01](https://github.com/luisjrez/Tappy/issues/93), [L03](https://github.com/luisjrez/Tappy/issues/95), [L13](https://github.com/luisjrez/Tappy/issues/96) |
| L05 — Explicar problema y recorrido de cobro | [#98](https://github.com/luisjrez/Tappy/issues/98) | [L04](https://github.com/luisjrez/Tappy/issues/97) |
| L06 — Mostrar beneficios con ejemplos honestos | [#99](https://github.com/luisjrez/Tappy/issues/99) | [L05](https://github.com/luisjrez/Tappy/issues/98) |

## [LW3 — Resolver dudas y permitir continuar](https://github.com/luisjrez/Tappy/issues/91)

| Subtarea | Issue | Bloqueada por |
| --- | --- | --- |
| L07 — Resolver dudas y explicar al pagador | [#100](https://github.com/luisjrez/Tappy/issues/100) | [L05](https://github.com/luisjrez/Tappy/issues/98) |
| L08 — Conectar CTA a una acción disponible | [#101](https://github.com/luisjrez/Tappy/issues/101) | [L04](https://github.com/luisjrez/Tappy/issues/97), [L07](https://github.com/luisjrez/Tappy/issues/100) |
| L09 — Ofrecer información y contacto reales | [#102](https://github.com/luisjrez/Tappy/issues/102) | [L01](https://github.com/luisjrez/Tappy/issues/93), [L08](https://github.com/luisjrez/Tappy/issues/101) |

## [LW4 — Validar y entregar la landing](https://github.com/luisjrez/Tappy/issues/92)

| Subtarea | Issue | Bloqueada por |
| --- | --- | --- |
| L14 — Completar catálogo y detectar regresiones visuales | [#103](https://github.com/luisjrez/Tappy/issues/103) | [L04](https://github.com/luisjrez/Tappy/issues/97), [L05](https://github.com/luisjrez/Tappy/issues/98), [L06](https://github.com/luisjrez/Tappy/issues/99), [L07](https://github.com/luisjrez/Tappy/issues/100), [L08](https://github.com/luisjrez/Tappy/issues/101), [L09](https://github.com/luisjrez/Tappy/issues/102), [L13](https://github.com/luisjrez/Tappy/issues/96) |
| L10 — Validar accesibilidad y fidelidad responsive | [#104](https://github.com/luisjrez/Tappy/issues/104) | [L06](https://github.com/luisjrez/Tappy/issues/99), [L07](https://github.com/luisjrez/Tappy/issues/100), [L08](https://github.com/luisjrez/Tappy/issues/101), [L09](https://github.com/luisjrez/Tappy/issues/102), [L14](https://github.com/luisjrez/Tappy/issues/103) |
| L11 — Preparar metadatos y presupuesto de rendimiento | [#105](https://github.com/luisjrez/Tappy/issues/105) | [L06](https://github.com/luisjrez/Tappy/issues/99), [L09](https://github.com/luisjrez/Tappy/issues/102) |
| L12 — Verificar entrega y preparar publicación | [#106](https://github.com/luisjrez/Tappy/issues/106) | [L03](https://github.com/luisjrez/Tappy/issues/95), [L10](https://github.com/luisjrez/Tappy/issues/104), [L11](https://github.com/luisjrez/Tappy/issues/105) |
