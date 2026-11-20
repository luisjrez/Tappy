# Tappy — Base de producto

Fecha: 20 de noviembre de 2026. Estado: síntesis para orientar el arranque y acordar el alcance. No es una especificación técnica ni acredita una integración implementada.

## 1. Goal del proyecto

**Ayudar a micronegocios mexicanos a solicitar cobros desde su teléfono, saber con certeza cuándo recibieron el dinero y entender cuánto han recibido por día, semana y mes.**

Tappy reúne tres momentos de la operación cotidiana: pedir el pago, comprobar su recepción y consultar lo recibido. La promesa de marca es «Cobra fácil. Sigue creciendo.»; el resultado concreto es que el comercio pueda atender una venta sin depender de capturas del pagador ni reconstruir sus cobros al cerrar el día.

El dinero llega a la cuenta bancaria receptora del comercio. Tappy coordina solicitudes CoDi y consulta evidencia de recepción mediante pey; la autorización del pagador corresponde a su institución bancaria compatible. No hay saldo ni fondos custodiados en Tappy.

La hipótesis por validar es que reunir estos pasos reduzca esfuerzo e incertidumbre para el comercio. Las referencias disponibles muestran una experiencia diseñada; todavía no prueban adopción, facilidad de uso con comerciantes ni viabilidad comercial.

## 2. Personas y necesidades

| Persona | Qué necesita lograr | Qué debe entregarle Tappy |
| --- | --- | --- |
| Dueña, dueño o responsable del comercio | Cobrar, atender y revisar su jornada | Importe claro, confirmación verificable, historial y resumen comprensible |
| Operador | Ejecutar el cobro cotidiano del comercio | Pocos pasos, estado inequívoco y recuperación si pierde conexión |
| Pagador | Revisar destinatario, monto y concepto antes de autorizar | Un camino compatible con su banco, sin instalar Tappy ni registrarse en él |

El operador es quien usa la app; el comercio es el negocio. En la primera entrega pueden coincidir propietario y operador. Empleados con permisos diferenciados pertenecen a una evolución posterior.

El contexto incluye poco tiempo, atención frente al cliente, equipos pequeños, conectividad variable y distintos niveles de familiaridad digital. La experiencia debe funcionar con texto grande y lectores de pantalla, y ser entendible por personas mayores.

## 3. Visión y primera entrega

La visión es una herramienta cotidiana de cobros y seguimiento para micronegocios. La primera entrega demostrará el recorrido completo con un negocio ficticio, operadores y participantes autorizados, y una cuenta receptora válida. La identidad ficticia de la demo nunca sustituye la identidad real del beneficiario bancario.

El contexto anterior fija el 5 de diciembre de 2026 como objetivo interno de entrega, con pruebas y materiales. Esa fecha es un objetivo registrado, no evidencia de avance ni una estimación actualizada. El cumplimiento de las bases del evento y sus fechas se debe revisar por separado antes de presentar el proyecto.

| Nivel | Alcance de producto |
| --- | --- |
| Núcleo de la primera entrega | Acceso autorizado, comercio y receptor configurados, captura y revisión de importe, QR, seguimiento confiable, recuperación, historial, detalle, resumen diario/semanal/mensual, ayuda básica y landing |
| Canales incluidos en la visión actual | QR, solicitud al celular y enlace compartible. QR es la secuencia inicial recomendada; el compromiso de entregar los tres depende de validación y capacidad y sigue abierto |
| Diseñado, por priorizar | Comprobante compartible, búsqueda y filtros amplios, avisos, preferencias, perfil detallado y comparaciones de periodos |
| Evolución posterior | Alta pública de comercios, empleados y permisos avanzados, sucursales, Mesa Abierta y servicios operativos |
| Fuera del proyecto actual | NFC, Tap to Pay, procesamiento propio de tarjetas, inventario, citas, custodia de fondos, contabilidad integral y devoluciones automáticas |

La primera entrega puede mostrar una simulación pública identificada como tal y un flujo real de acceso controlado. Son experiencias separadas: una simulación permite entender el producto, pero no demuestra recepción bancaria auténtica.

## 4. Cómo funciona el sistema

1. El operador accede a su comercio. Tappy muestra el receptor configurado y si está habilitado para recibir.
2. Captura un importe positivo en MXN y, opcionalmente, un concepto. Revisa importe y beneficiario antes de emitir la solicitud.
3. Elige un canal habilitado: QR, celular o enlace. El sistema conserva el cobro y crea un intento asociado.
4. El pagador recibe o abre la solicitud, revisa los datos y autoriza por el recorrido bancario compatible. Mostrar un QR o abrir un enlace no acredita el pago.
5. Tappy recibe o consulta evidencia del proveedor y valida su correspondencia con el comercio, receptor, importe y cobro.
6. Solo tras esa validación muestra «Pago recibido» y registra la transferencia una vez en el historial y los resúmenes.
7. El operador puede consultar el detalle y, si la función está incluida, compartir un comprobante de recepción.

Si el proceso se interrumpe, la app recupera el cobro existente. La incertidumbre se presenta como «Sin comprobar» o «Verificando», con una acción comprensible. No se crea otro cobro automáticamente para resolver una respuesta incierta.

### Conceptos compartidos por todas las capas

| Concepto | Significado de producto |
| --- | --- |
| Comercio | Negocio al que pertenecen los cobros |
| Cuenta receptora | Cuenta autorizada para recibir; no es una billetera de Tappy |
| Cobro | Venta por un importe fijo esperado; puede tener varios intentos |
| Intento | Solicitud concreta por un canal; crearla no significa haber recibido dinero |
| Transferencia confirmada | Movimiento bancario cuya recepción ha sido verificada |
| Conciliación | Comprobar y asociar evidencia con el cobro correspondiente |
| Incidencia | Discrepancia de importe, referencia, receptor o cantidad de transferencias que requiere revisión |

### Estados que la persona debe comprender

| Estado visible | Qué significa | Acción o resultado |
| --- | --- | --- |
| Capturando | Todavía no se emitió la solicitud | Editar y revisar |
| Creando solicitud | Se está procesando su creación | Evitar envíos duplicados |
| Esperando pago | Existe una solicitud, sin recepción confirmada | Mostrar instrucciones y consultar estado |
| Verificando / Sin comprobar | La evidencia o la conexión aún no permiten concluir | Recuperar y comprobar; conservar los datos |
| Pago recibido | La recepción correspondiente fue validada | Mostrar detalle y actualizar historial/resumen |
| Solicitud vencida | Terminó la ventana de uso informada | Revisar antes de generar otro intento; conservar trazabilidad |
| No se pudo crear / Fallo confirmado | Existe evidencia suficiente del problema | Explicar la causa conocida y la siguiente acción |
| Requiere revisión | Hay discrepancias o más de una transferencia | Mostrar incidencia sin ocultar dinero recibido |

Cerrar una pantalla no cancela una solicitud bancaria. Vencimiento tampoco garantiza que un intento anterior no pueda recibir un pago tardío. Un rechazo solo se anuncia cuando existe evidencia; falta de notificación no significa rechazo.

## 5. Separación de capas

Frontend comprende las experiencias que ven las personas: landing, superficies web del pagador y app móvil. Mobile es un frente propio dentro de esa capa por sus necesidades de operación cotidiana, accesibilidad y recuperación. El backend mantiene las reglas y el registro común del sistema.

| Capa | Responsabilidad | Resultado que entrega |
| --- | --- | --- |
| Landing pública | Explicar Tappy, generar confianza y conducir a una acción disponible | La persona entiende para quién sirve, cómo funciona y cómo probarlo |
| Web del pagador | Presentar solicitud y orientar al recorrido de pago compatible | Destinatario, importe, concepto y siguientes pasos claros |
| Mobile del comercio | Capturar, presentar, seguir y consultar cobros | Una operación cotidiana sencilla y recuperable |
| Backend | Autorizar, coordinar solicitudes, verificar evidencia y conservar registros | Una única verdad de cobros, transferencias, incidencias y totales |
| Proveedor e institución bancaria | Tramitar la solicitud y la autorización/transferencia según sus capacidades | Evidencia externa que Tappy debe validar |

Las pantallas solicitan acciones y presentan resultados. La decisión de que un pago está recibido pertenece al backend; ninguna interfaz puede marcarlo manualmente como recibido.

### 5.1 Landing page

**Objetivo:** que un comerciante comprenda el beneficio, el reparto de responsabilidades y la siguiente acción, sin conocer detalles de integración.

La landing existente en Pen propone esta narrativa:

1. Propuesta principal: cobrar y entregar después de confirmar la recepción.
2. Problema cotidiano: capturas, consultas repetidas al banco y cierre manual.
3. Cómo funciona: escribir monto, elegir canal y esperar confirmación.
4. Beneficios: historial, comprobantes y resumen por periodos.
5. Experiencia del pagador: revisa y autoriza con su banco compatible, sin instalar Tappy.
6. Ayuda y límites: compatibilidad, papel de Tappy y dudas frecuentes.
7. Acción final y acceso a términos, privacidad y contacto disponibles.

Para la primera entrega se recomienda «Ver demo» o «Probar demostración» como acción principal mientras el alta pública no exista. Una lista de espera es opcional y requiere definir finalidad, consentimiento y destino de los datos. No debe mostrarse un formulario sin proceso de atención.

La landing debe adaptarse a teléfono y escritorio, permitir navegación accesible y distinguir capturas ilustrativas de resultados reales. No se publicarán cifras de adopción, compatibilidad universal, precios, gratuidad ni disponibilidad de funciones sin respaldo.

### 5.2 Frontend web del pagador

Es una superficie transaccional distinta de la landing. Debe mostrar comercio y beneficiario con claridad, importe MXN, concepto si existe, referencia útil, instrucciones y estado verificable. No requiere cuenta Tappy.

El enlace puede abrir una experiencia alojada por el proveedor. Antes de construir un checkout propio hay que verificar qué presenta ese recorrido y qué páginas de orientación o retorno necesita Tappy. No se presupone un portal web de administración para el comercio en el MVP.

Volver desde el banco o desde una página de éxito solo inicia una comprobación de estado. Si el pago desde el mismo teléfono no tiene un recorrido compatible, se explica la limitación y se ofrece un canal validado.

### 5.3 Mobile del comercio

La navegación diseñada contiene **Inicio, Historial, Resumen y Ayuda**, con accesos secundarios a perfil y notificaciones.

| Área | Comportamiento esperado |
| --- | --- |
| Acceso y preparación | Entrar, recuperar sesión y conocer comercio/receptor. Primera entrega con usuarios preautorizados |
| Inicio | Total confirmado de hoy, pendientes separados, últimas operaciones y «Nuevo cobro» |
| Nuevo cobro | Importe protagonista, concepto opcional, revisión y canal; conservar captura ante errores |
| Seguimiento | QR o instrucciones de canal, importe, referencia, vencimiento cuando corresponda y estado actualizado |
| Resultado y detalle | Evidencia de recepción o explicación concreta del problema, sin atribuir causas desconocidas |
| Historial | Consultar operaciones y sus estados; añadir búsqueda/filtros según prioridad acordada |
| Resumen | Total recibido y número de transferencias por día/semana/mes; distinguir ventas cubiertas de pagos recibidos |
| Ayuda | Qué es CoDi, compatibilidad, pagos pendientes y qué hacer sin conexión |
| Perfil y avisos | Consultar datos y cerrar sesión; priorizar preferencias y avisos por separado del núcleo |

Debe recuperar el estado al reabrir, volver del banco o recuperar internet. Puede presentar datos previamente confirmados con su última actualización, pero no emitir cobros nuevos offline ni inventar una confirmación.

El contexto previo solicita dos implementaciones móviles en paralelo, con paridad del núcleo en iOS y Android según corresponda. Se conserva el requisito de producto sin fijar aquí su tecnología. La paridad significa mismo comportamiento, estados, seguridad y datos; las interacciones pueden adaptarse a cada plataforma. Tablet sigue sin compromiso formal.

### 5.4 Backend

**Objetivo:** sostener la confianza del producto y permitir que todas las interfaces consulten el mismo resultado.

| Dominio | Responsabilidad de producto |
| --- | --- |
| Identidad y acceso | Reconocer al operador, su comercio y las operaciones que puede realizar |
| Comercio y receptor | Mantener beneficiario y estado de habilitación; impedir nuevos cobros si no está listo |
| Cobros e intentos | Conservar importe, concepto, referencias, canal y relación entre reintentos |
| Integración | Crear solicitudes y traducir respuestas del proveedor a estados comprensibles |
| Evidencia y conciliación | Verificar recepción, recuperar casos inciertos y evitar duplicar efectos |
| Historial y reportes | Entregar detalle y agregaciones coherentes de transferencias confirmadas |
| Incidencias y operación | Conservar discrepancias, permitir investigación y recuperar tareas interrumpidas |
| Avisos, si se incluyen | Originar mensajes a partir del estado validado; controlar preferencias y duplicados |

El registro debe permitir reconstruir qué se pidió, qué respondió el proveedor, qué se recibió y por qué se cambió un estado. El acceso se limita al comercio correspondiente; datos bancarios completos y credenciales no forman parte de la información pública ni del contenido compartible.

### 5.5 Monorepo como organización del producto

Se adopta la organización en monorepo solicitada para mobile, coordinada con los demás frentes. Debe reunir o referenciar claramente: clientes móviles, landing y superficies web, backend, contratos de comportamiento y datos, vocabulario, diseño/copy, escenarios de prueba y documentación.

Se comparten reglas de producto, definiciones de estados, contratos, ejemplos, criterios de aceptación y significado de los tokens visuales. Cada superficie mantiene sus interacciones y componentes apropiados. Estar en un monorepo no obliga a compartir todas las piezas de interfaz ni a desplegar todo junto.

Este documento no prescribe carpetas, herramientas de organización, lenguajes, frameworks, bases de datos ni alojamiento. Esas elecciones se harán después, a partir de estas responsabilidades.

## 6. Reglas de confianza y métricas

- Solicitud creada, compartida o enviada no equivale a pago recibido.
- Un cobro admite varios intentos, con un solo intento activo de creación/cobro a la vez en esta versión. Cambiar el monto después de emitir exige un cobro nuevo.
- Repetir la misma notificación no suma dinero dos veces. Dos transferencias bancarias distintas se conservan como dos movimientos, aunque correspondan a una venta.
- Un pago tardío auténtico se registra; importes discrepantes o cobros duplicados abren incidencia. No hay resolución mediante devolución automática en el MVP.
- Las capturas del pagador, los avisos del dispositivo y los retornos de navegación no sustituyen la verificación del sistema.
- El resumen informa importe recibido, no saldo bancario, utilidad ni facturación fiscal. Pendientes y solicitudes vencidas quedan fuera del total confirmado.
- Día calendario local, semana de lunes a domingo y mes calendario usan la zona de Ciudad de México. La fecha bancaria validada determina el periodo cuando está disponible; si se usa fecha de recepción de evidencia debe explicarse. Evidencia tardía puede corregir un periodo anterior.
- Ticket promedio y comparaciones se añaden con una base explícita: no mezclar transferencias con ventas ni comparar periodos desiguales sin explicación. Las incidencias no se ocultan en promedios.

## 7. Marca, conceptos y copy

La especificación de marca plantea una herramienta amable, serena y confiable. Pen concreta esa dirección con verde bosque, fondos cálidos, grandes importes, listas agrupadas, ilustraciones discretas y acciones principales claras. La marca escrita en minúsculas y el símbolo Encuentro conectan las superficies.

Se revisaron las tres rutas de conceptos: **Mostrador**, con composición práctica y sobria; **Recibo**, con superficies y separadores inspirados en un comprobante; y **Jornada**, con presencia de marca en encabezados y énfasis en el día de trabajo. Son exploraciones, no tres productos ni funciones adicionales. El Pen actual desarrolla una composición propia y contiene una landing llamada «Mostrador»; eso no acredita una elección final de toda la ruta móvil.

El sistema web documenta temas claro/oscuro, espaciado, formularios, navegación, capas, estados, métricas y movimiento reducido. Pen añade componentes reutilizables para teclado de importe, métodos, QR, vencimiento, comprobante, reportes y perfil. La base está avanzada visualmente; falta consolidar qué versión gobierna cada componente antes de implementarlo.

Principios que deben conservar todas las superficies:

- Monto, receptor y estado tienen prioridad visual y de lectura.
- Español de México breve, cálido y respetuoso; una acción principal por contexto.
- Estados con texto e icono; ningún significado depende solo de color, sonido o animación.
- Texto adaptable, controles amplios, foco visible, lectores de pantalla y movimiento reducido.
- Gráficas acompañadas por valores y una alternativa de consulta textual.
- Las ilustraciones acompañan; no sustituyen evidencia ni mensajes de estado.

Copy base: «Nuevo cobro», «Solicitud creada. Esperando pago», «Aún no podemos comprobar este pago» y «Pago recibido: $300». Evitar «Cobrado» al emitir una solicitud o «No recibiste dinero» cuando todavía existe incertidumbre.

### Diferencias que hay que reconciliar antes de construir

| Hallazgo en diseño/documentación | Tratamiento para el arranque |
| --- | --- |
| NFC experimental todavía visible en conceptos y Pen | Retirarlo del alcance implementable y de la comunicación; está excluido por decisión previa |
| «Crear cuenta» y conexión bancaria de autoservicio en Pen | Conservar como visión futura; demo con acceso autorizado y receptor preparado |
| «Cancelar solicitud» y «Esta solicitud ya no se puede pagar» | No anunciar revocación bancaria sin capacidad comprobada; distinguir abandonar, vencer y cancelar |
| Cambiar método o «Cobrar de nuevo» como acción inmediata | Recuperar/verificar primero y explicar riesgo de pago tardío; conservar la misma venta cuando corresponda |
| Enlace llamado CoDi con expiración fija | Validar métodos, receptor y vigencia del checkout antes de usar ese copy |
| Avisos «aunque tengas la app cerrada» | Función diseñada, pendiente de alcance e implementación; recibir evidencia en servidor no entrega por sí solo un aviso al teléfono |
| «Empieza gratis», alta «en minutos» y tres canales como disponibles en landing | Ajustar a la oferta y capacidades realmente habilitadas; precio y plazo no están acordados |
| Tipografía, tamaños y colores semánticos con variantes entre marca, CSS y Pen | Consolidar una referencia por superficie; probar texto grande y contraste real |
| Documentos antiguos dicen que Pen aún no está disponible | Ya se revisó el archivo actual por su herramienta; no implica que esté implementado o aprobado |

## 8. Qué necesitamos para empezar

### Preparación por frente

| Frente | Definir o conseguir | Evidencia de preparación |
| --- | --- | --- |
| Producto | Alcance de la primera entrega y canales comprometidos | Lista de capacidades con aceptación observable y exclusiones |
| Diseño/copy | Ruta visual de referencia y corrección de diferencias anteriores | Flujos de éxito, espera, error, incertidumbre y recuperación coherentes |
| Mobile | Plataformas/dispositivos, paridad y recorrido de instalación | Matriz de escenarios por cliente y dispositivo; responsables disponibles |
| Landing/web | CTA real, destino de demo, contenido y recorrido del pagador | Narrativa sin promesas pendientes y límites de información pública |
| Backend | Receptor autorizado, estados y reglas de evidencia, recuperación e incidencias | Contrato de producto común con ejemplos de cada resultado |
| Integración externa | Acceso del equipo, activación de receptor y comportamiento real por canal | Prueba autorizada trazable; dudas del proveedor identificadas |
| Operación | Presupuesto, responsables, soporte, conservación de datos y recuperación | Acuerdos concretos para operar la demo y atender incidencias |

### Validación externa consultada para esta síntesis

Se contrastaron el 20 de noviembre de 2026 tres páginas oficiales, sin crear cuentas, enviar solicitudes bancarias ni hacer transferencias:

1. La documentación de pey sigue presentando producción y un entorno de pruebas próximo. Por ello, no podemos dar por disponible un sandbox; una simulación interna debe identificarse como tal. [Documentación oficial](https://docs.pey.mx/).
2. La guía informa un plazo de cinco días hábiles para registrar la cuenta bancaria. La preparación del receptor es una dependencia temprana, y el alta en minutos del diseño no debe anunciarse como plazo garantizado. No se utilizaron cuentas de prueba publicadas ni datos bancarios de terceros. [Guía de alta](https://docs.pey.mx/docs/tutorials/getting-started/create-an-api-key/).
3. El proveedor ofrece un checkout alojado que puede incluir varios medios de pago. La creación de enlaces consultada no establece por sí sola selección de método, cuenta receptora o vencimiento. Hay que validar su recorrido para mantener la propuesta CoDi del proyecto y evitar ampliar alcance a tarjetas de forma accidental. [Descripción de medios](https://docs.pey.mx/), [creación de enlaces](https://docs.pey.mx/docs/api/create-payment-link/).

La lectura de páginas no demuestra compatibilidad de un banco concreto, acceso del equipo, receptor activado o autorización para operar múltiples comercios. Los análisis anteriores conservan preguntas sobre condiciones de terceros, cuotas, evidencia y conservación de datos; requieren respuestas y pruebas antes de anunciar esas capacidades.

### Decisiones pendientes, sin elegir tecnología

1. ¿Los tres canales son obligatorios en la primera entrega o se acepta entregar QR antes que celular/enlace?
2. ¿Quién es el receptor autorizado y qué falta para habilitarlo?
3. ¿Qué paridad y dispositivos se comprometen para cada cliente móvil? ¿Qué soporte de tablet, si alguno, se ofrece?
4. ¿Comprobante, notificaciones con app cerrada y preferencias entran en la primera entrega o en una iteración posterior?
5. ¿La landing conduce a demo, descarga disponible o lista de espera? ¿Quién atiende contacto e incidencias?
6. ¿Quién resuelve pagos tardíos, duplicados e importes discrepantes y qué información verá el operador?
7. ¿Cuál es la capacidad real del equipo y el presupuesto para mantener la entrega disponible?

Estos pendientes no bloquean consolidar diseño, contratos de producto y escenarios simulados. Receptor/acceso y validación del canal sí condicionan las pruebas y la declaración de integración real.

## 9. Secuencia y criterio de éxito

1. Consolidar alcance, copy y reglas; corregir las diferencias del diseño.
2. Preparar receptor y accesos mientras se definen estados, datos y escenarios compartidos.
3. Construir un recorrido completo de QR: captura → espera → evidencia validada → resultado → historial → resumen.
4. Comprobar pérdida de red, reintentos, evidencia repetida, pagos tardíos e incidencias.
5. Incorporar celular/enlace según el alcance acordado, con el mismo motor y validación propia por canal.
6. Completar las superficies y materiales públicos con las capacidades realmente verificadas.

El núcleo está listo cuando un operador autorizado puede completar el recorrido, recuperar una operación interrumpida y encontrar el mismo importe/estado en detalle, historial y resumen. Evidencia repetida no altera el total, una transferencia distinta se conserva, y nadie ve «Pago recibido» sin validación. La experiencia debe permitir identificar importe, receptor y estado con texto grande y lector de pantalla.

Después se medirá con comerciantes: tiempo y errores al crear un cobro, comprensión de pendiente frente a recibido, facilidad para encontrar una operación y utilidad del cierre por periodo. No se fijan resultados ni metas numéricas inventadas; se establecerá una línea base con observación. La demo valida funcionamiento; la investigación con personas valida utilidad.

## 10. Fuentes y relación con los documentos existentes

- [Contexto y vocabulario](CONTEXT.md).
- [Especificación de marca](TAPPY_BRAND_IDENTITY_SPEC.md).
- [Sistema de diseño web](design-system/README.md), sus ocho láminas y tokens visuales.
- [Diseño Pen](tappy-design.pen): mapa, flujos 00–05, sistema de componentes y Landing A. Se inspeccionaron estructura, textos y capturas del flujo de cobro y landing mediante la herramienta de diseño.
- Conceptos visuales de `mobile-concepts/`: Mostrador, Recibo y Jornada; activos de pantallas y marca en `landing/screens/`.
- [Producto anterior](docs/01-producto-y-entrega.md), [arquitectura propuesta](docs/02-arquitectura.md), [historias y pruebas](docs/03-historias-y-pruebas.md), [decisiones y plan](docs/04-decisiones-y-plan.md), [clientes paralelos](docs/05-apps-paralelas.md).
- [Investigación previa de pey](docs/research/pey-validation.md) y [evaluación previa de backend](docs/research/supabase-backend.md). Se usan como antecedentes y registro de preguntas; sus propuestas tecnológicas no son decisiones de esta base.

Este archivo es el punto de entrada de producto para la siguiente conversación. No modifica acuerdos previos ni aprueba automáticamente funciones dibujadas. Las recomendaciones se mantienen identificadas y la elección de tecnologías se deja para una etapa posterior.
