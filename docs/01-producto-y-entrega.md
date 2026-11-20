# Producto y entrega del hackathon

Propuesta v0.3 · 10 de noviembre de 2026. Equipo provisional de cuatro integrantes. Fecha interna objetivo confirmada por el usuario: 5 de diciembre, con pruebas y demo grabada. Dos clientes solicitados: Expo/TypeScript y SwiftUI. La dedicación por integrante y el presupuesto siguen pendientes.

## 1. Objetivo del producto

Permitir que un micronegocio mexicano solicite un cobro desde su teléfono, sepa cuándo recibió un pago confirmado y consulte sus ingresos por periodo, sin depender de capturas de pantalla del pagador.

La hipótesis de valor es que capturar un importe, seguir el cobro y encontrar la operación en un historial comprensible facilita el trabajo cotidiano respecto a coordinar esos pasos por separado. La demo probará funcionamiento y claridad de interacción; no demostrará todavía adopción, rentabilidad ni compatibilidad con todos los bancos.

## 2. Objetivo del hackathon

Demostrar de principio a fin, en un negocio ficticio con cuenta receptora autorizada, que Tappy crea una solicitud CoDi mediante pey, procesa evidencia auténtica de recepción y refleja la transferencia una sola vez en el cobro, historial y resumen.

Ejemplo central: el operador captura un importe permitido para la prueba → genera un QR → un colaborador paga desde su banco → el backend valida la notificación o consulta de conciliación → la app muestra «Pago recibido» → historial y resumen registran el importe.

La marca del negocio de demo puede ser ficticia. La titularidad del receptor, sus datos de registro y el beneficiario mostrado al pagador deben corresponder a la cuenta autorizada. No se inventarán datos de onboarding bancario.

## 3. Qué cuenta como MVP

### Núcleo indispensable propuesto — P0

| ID | Capacidad | Condición de aceptación |
| --- | --- | --- |
| F01 | Acceso del operador | Sesión de un usuario preautorizado y recuperación de sesión; sin registro abierto |
| F02 | Negocio de demo | Nombre comercial, beneficiario y estado real de la cuenta receptora configurada |
| F03 | Crear cobro | MXN con centavos enteros, importe fijo positivo y referencia única |
| F04 | QR CoDi | Solicitud auténtica mediante pey y representación exacta del contenido devuelto |
| F05 | Seguir estado | Distinguir creando, esperando pago, verificando, recibido y vencido; incertidumbre explícita |
| F06 | Confirmación confiable | Firma, cuenta, importe, referencia y deduplicación; nunca confirmar desde UI o redirección |
| F07 | Vencimiento y recuperación | Autoridad del servidor, consulta de estado y reintento sin duplicar el cobro |
| F08 | Historial y detalle | Cobros e intentos identificables, pendientes y transferencias confirmadas |
| F09 | Resumen diario/semanal/mensual | Total recibido y número de transferencias; número de ventas pagadas diferenciado |
| F10 | Landing | Explicar propuesta, funcionamiento y límites; enlace a demo pública sin generación bancaria abierta |
| F11 | Operación y seguridad | Credenciales en servidor, autorización, límites, registro seguro y trabajos recuperables |
| F12 | Accesibilidad básica | Escalado, lector de pantalla, targets amplios, errores claros y estado con texto |

### Alcance objetivo adicional — P1

P1 define orden de construcción, no una decisión del usuario de eliminar estos canales.

| ID | Capacidad | Condición de aceptación |
| --- | --- | --- |
| F13 | Solicitud al celular | Número válido y solicitud creada mediante pey; éxito de envío distinto de pago |
| F14 | Enlace compartible | URL oficial creada mediante pey, compartida desde la app y conciliada con transferencia |

Se recomienda completar ambos después de estabilizar QR. Su inclusión como compromiso de entrega depende de plazo, dispositivos, acceso y pruebas del proveedor. Antes de congelar alcance se decidirá expresamente si los tres canales son obligatorios para el hackathon. Un canal sin validar no se mostrará como funcional.

### Fuera del proyecto actual

NFC, tarjetas/Tap to Pay, Mesa Abierta, inventario, citas, empleados/roles avanzados, múltiples sucursales, custodia de fondos, onboarding bancario público, contabilidad y devolución automática. La autenticación administrada y el historial básico sí forman parte del MVP.

No hay cobro offline. Una pantalla cacheada de un pago previamente confirmado puede mostrar ese dato con su última actualización; no acredita un cobro nuevo.

## 4. Entregables propuestos

1. Dos clientes instalables con el mismo núcleo funcional P0: Expo para iOS/Android y SwiftUI nativo para iOS. Verificar las tres combinaciones implementación/plataforma; no considerar lista la versión nativa por mostrar solo un prototipo visual.
2. Un backend compartido con HTTPS, persistencia, webhooks y conciliación; se recomienda Supabase completo sin servidor NestJS adicional. Configuración reproducible sin secretos en el repositorio.
3. Landing adaptable a móvil y escritorio, con explicación honesta y acceso público para ver o probar una simulación.
4. Demostración de integración auténtica separada de la simulación pública; evidencia e instrucciones reproducibles para el jurado.
5. Documento de alcance, arquitectura, contratos internos, historias y reporte de pruebas ejecutadas con resultados y limitaciones.
6. Video breve del flujo completo, descripción del proyecto y declaración de activos previos/de terceros, ajustados a las bases confirmadas.

La demo pública no expondrá un usuario con permiso para mandar solicitudes a teléfonos arbitrarios o crear cobros reales sin control. Puede ofrecer un recorrido simulado claramente rotulado y una evidencia de la integración auténtica. Hay que confirmar con organizadores que esta forma de acceso satisface la evaluación; una simulación sola no sustituye la integración.

## 5. Dependencias externas

- **Sandbox:** documentación y términos de pey presentan información que necesita aclaración; no se considera un entorno disponible hasta tener acceso verificado. Un adaptador local de pruebas es simulación de Tappy.
- **Producción:** requiere credenciales, receptor elegible y activación. Que el pagador tenga CoDi habilitado no activa por sí solo una cuenta receptora en pey.
- **Cuenta personal:** no asumir elegibilidad de cualquier cuenta del equipo. Confirmar titularidad, requisitos del integrador y autorización del receptor antes de usar dinero real.
- **Evento:** las fechas aportadas por el usuario coinciden con las [bases de Hackatón México](https://hackatonmexico.com/reglas), adoptadas como referencia operativa pendiente de confirmación explícita del enlace. La postulación cierra el 10 de diciembre y la entrega el 12, ambas a las 23:59 de Ciudad de México. El equipo fija el 5 de diciembre como límite interno para llegar con margen. Las secciones 6.2–6.3 requieren integración demostrable en producción; el plan no puede descansar únicamente en mocks.
- **Multi-comercio:** resolver el acuerdo correspondiente antes de habilitar comercios externos. La demo de una cuenta no demuestra autorización para operar a favor de terceros.

Evidencia, contratos y fuentes específicos: [validación de pey](research/pey-validation.md).

## 6. Reglas de producto

1. Todo cobro tiene importe fijo, moneda MXN y comercio propietario. No admitir QR de importe abierto en el MVP.
2. Un cobro puede tener varios intentos. Solo un intento activo de creación/cobro a la vez por cobro en esta versión.
3. Una solicitud aceptada queda pendiente; no implica entrega, lectura, autorización o transferencia.
4. La ausencia de notificación no significa rechazo. Una respuesta ambigua conserva el intento para conciliación.
5. Expirar u ocultar un QR en Tappy no garantiza revocarlo en el proveedor. El usuario debe ser advertido al generar otro intento.
6. Un pago auténtico tardío se registra. Si un segundo intento también fue pagado, ambas transferencias se conservan y se abre incidencia.
7. Importes o destinatarios discrepantes no confirman automáticamente el cobro. La evidencia se conserva para revisión.
8. El operador no puede marcar un cobro como pagado manualmente en el MVP ni cambiar el destinatario desde la app.
9. Los datos de simulación y los datos de producción se separan por entorno. Las métricas sintéticas se identifican como demostración.
10. Cambiar el monto después de emitir una solicitud exige otro cobro; el intento anterior conserva su importe original y su trazabilidad.

## 7. Pantallas mínimas y diseño

Acceso → inicio/importe → revisión y método → QR o solicitud → seguimiento → resultado → historial/detalle → resumen por periodo. Para celular se añade el formulario del número; para enlace, la acción de compartir y el estado. Configuración de receptor de demo será operativa, no un onboarding público.

Se propone teléfono como objetivo principal. Tablet tendrá una disposición utilizable y sin bloqueo artificial cuando sea viable; anunciar soporte formal requiere incluirla en la matriz de pruebas. No construir una segunda app de tablet para la demo.

El usuario solicita mantener Expo y SwiftUI en paralelo. La paridad cubre requisitos funcionales y seguridad del mismo MVP; los componentes y la navegación pueden adaptarse a cada plataforma. [Plan de ambas apps](05-apps-paralelas.md). Ese trabajo adicional requiere responsables y QA por cliente sin extender automáticamente el objetivo del 5-dic.

Inventario provisional comunicado: aproximadamente cuatro iPhones y tres Android; confirmar disponibilidad de iPhones por contradicción en la descripción verbal y registrar modelos/SO. Esto permite proponer QA en ambas plataformas, sin prometer soporte a versiones o dispositivos aún no comprobados. La distribución de la build de iOS y sus requisitos deben resolverse temprano, no durante la grabación final.

Reutilizar tokens y dirección visual de [marca](../TAPPY_BRAND_IDENTITY_SPEC.md) y [sistema web](../design-system/README.md). Revisar el diseño externo de Panda Dev antes de elegir una ruta móvil. Compartir conceptos, tokens y contratos; los componentes nativos y web tendrán sus implementaciones correspondientes.

La landing inicial explica Tappy y abre la demo. Captura de correos/lista de espera es opcional y añade tratamiento de datos y control de abuso; no es requisito del núcleo.

El diseño de Panda Dev/Pen Dev se incorporará al directorio por el usuario, y una eventual conexión MCP está pendiente. No se sustituye ese diseño ni se considera evaluado mientras no esté disponible.

## 8. Métricas y criterios de éxito

Objetivos propuestos, todavía no mediciones:

- Un flujo QR completo con evidencia auténtica y trazable al cobro.
- Todas las pruebas críticas de dinero, acceso y deduplicación aprobadas antes de la entrega.
- Un webhook repetido no altera el total después del primer procesamiento.
- App en primer plano refleja un cambio persistido dentro de 10 segundos en la red de la demo. Se mide desde el registro en Tappy, separado de la latencia del banco/proveedor.
- El backend no contacta a pey por cada consulta de pantalla; el seguimiento lee la base de Tappy.
- Un operador puede identificar importe, receptor y estado sin depender de un color.
- Credenciales, datos personales y movimientos reales no aparecen en el recorrido público de simulación.

El resumen usa `America/Mexico_City`: día calendario local, semana de lunes a domingo y mes calendario. Persistencia de fechas en UTC. La fecha de ingreso será la fecha bancaria confirmada si existe y su semántica está validada; en su ausencia se usará recepción de la evidencia, indicada como tal. Las llegadas tardías pueden corregir un periodo anterior.

## 9. Qué no demuestra esta entrega

Un negocio ficticio sirve para comprobar el sistema y presentar la experiencia. La facilidad para personas ajenas al equipo, la disposición a pagar y el beneficio para un segmento concreto siguen siendo hipótesis que necesitarán observación con comerciantes.
