# Historias, recorridos y casos de prueba

Propuesta v0.3 · 10 de noviembre de 2026. **Todos los casos están definidos y NO EJECUTADOS.** Ningún caso demuestra compatibilidad real con un banco. P0/P1 corresponde a [producto](01-producto-y-entrega.md). Esta revisión añade backend Supabase completo y clientes Expo/SwiftUI.

## 1. Historias y criterios de aceptación

| Historia | Como… quiero… para… | Aceptación observable | Prioridad y trazabilidad |
| --- | --- | --- | --- |
| US01 | Operador, acceder a mi negocio para cobrar con mi cuenta autorizada | Solo usuario preautorizado; sesión válida; datos del comercio correcto; sesión inválida no permite operar; receptor inactivo bloquea creación con explicación | P0 · F01/F02 · QA01–03, QA31 |
| US02 | Operador, capturar y revisar un importe para evitar cobrar una cantidad equivocada | MXN, importe positivo, máximo configurable, precisión de centavos; revisar importe y beneficiario; errores conservan entrada; sin envío si no hay red | P0 · F03 · QA04–06, QA28 |
| US03 | Operador, generar un QR para que el cliente pague desde su banco | Solicitud real o simulada identificada por entorno; QR representa exactamente payload del proveedor; monto/receptor visibles; doble toque no genera otra operación | P0 · F04 · QA07–09, QA15, QA42 |
| US04 | Operador, seguir el cobro para saber si puedo considerar recibido el dinero | Solicitud creada queda pendiente; app consulta estado persistido; éxito solo con evidencia verificada; desconexión y antigüedad visibles | P0 · F05/F06 · QA10–14, QA26–28 |
| US05 | Operador, recuperar un intento vencido o incierto para continuar sin perder la venta | Reloj del servidor; verificación antes del reintento; mismo cobro; un intento activo; aviso de pago tardío; no repetir POST ambiguo | P0 · F07 · QA15–20, QA25 |
| US06 | Operador, ver historial y detalle para localizar qué pasó con un cobro | Filtro, paginación, importe, fecha, estado, intentos y referencias; no se confunden intentos con ventas ni transferencias | P0 · F08 · QA21, QA31 |
| US07 | Operador, consultar día/semana/mes para entender cuánto recibí | Solo transferencias verificadas; periodo local explícito; duplicados de evento no suman; dos transferencias distintas sí; ventas cubiertas y número de transferencias diferenciados | P0 · F09 · QA21–24 |
| US08 | Operador con necesidades de accesibilidad, completar el cobro para operar sin depender de visión/color/tamaño fijo | Texto escalable; montos sin truncar; controles etiquetados; lector de pantalla anuncia transición una vez; movimiento reducido | P0 · F12 · QA29/QA30 |
| US09 | Visitante/jurado, entender y explorar Tappy para evaluar su propuesta | Landing explica flujo y límites, no promete NFC; demo pública rotulada; datos de prueba; no permite activar operaciones bancarias arbitrarias | P0 · F10 · QA34/QA43 |
| US10 | Operador, enviar solicitud al celular para que el pagador la autorice en su banco | 10 dígitos según contrato; consentimiento en demo; aceptación del proveedor no es lectura ni pago; recepción no garantizada; cuota de reenvío; alternativa QR | P1 · F13 · QA35–37 |
| US11 | Operador, compartir enlace para ofrecer otro acceso al checkout | URL oficial HTTPS; compartir/cancelar hoja de compartir no confirma ni duplica cobro; sin promesa de deep link universal; cuenta/método validados antes de activar | P1 · F14 · QA38–40 |
| US12 | Responsable técnico, recibir y recuperar eventos para no perder ni duplicar evidencia | Firma sobre bytes originales; deduplicación durable; ACK después de persistir; reintentos recuperables; conflictos no acreditan la venta | P0 · F06/F11 · QA10–20, QA25/QA32/QA33/QA41 |

El pagador no inicia sesión en Tappy ni instala una app del proyecto. El camino de autorización depende de su institución. Los estados bancarios no documentados se describen como falta de confirmación; no se inventan callbacks de lectura, rechazo o expiración.

Las historias móviles aplican por igual a Expo y SwiftUI. Los casos de dominio/backend se ejecutan una vez sobre el motor común; los de UI, sesión, red, ciclo de vida e integración de cliente se registran para Expo Android, Expo iOS y SwiftUI iOS. Cada cliente debe demostrar su creación de solicitud y recuperación de estado; observar el mismo backend no prueba que ambas implementaciones envían datos correctos.

## 2. Recorridos exitosos

### HP01 — QR, recorrido principal

Precondiciones: operador autorizado; comercio configurado; receptor activo; backend accesible; pagador con banco y CoDi compatibles. En prueba simulada se sustituyen banco/proveedor por fixtures identificados. En prueba real se usa el importe mínimo acordado y participantes autorizados.

1. Operador introduce monto y concepto opcional.
2. Revisa monto, beneficiario y método QR; confirma una sola operación lógica.
3. Backend crea cobro/intento y solicita QR a pey con referencia correlacionable.
4. App muestra QR, importe, beneficiario, instrucciones y vencimiento del servidor.
5. Pagador escanea desde su banco, revisa los datos y autoriza.
6. Backend recibe evidencia, verifica y persiste transferencia/estado de forma idempotente.
7. App obtiene «Pago recibido»; historial y resumen contienen una transferencia.

Evidencia de aceptación: ID del cobro, ID del intento, solicitud/transferencia del proveedor, evento o consulta conciliada y resultado visible, sin secretos ni datos completos del pagador en capturas.

### HP02 — Solicitud al celular

Además de HP01: número del colaborador consentido y habilitado; canal probado con ese banco. Operador introduce número → backend solicita push → app dice «Solicitud creada. Esperando pago» → banco presenta solicitud → pagador autoriza → mismo procesamiento confiable de HP01. El paso de presentación se observa en el dispositivo del pagador; no se infiere de HTTP 200.

### HP03 — Enlace

Además de HP01: checkout validado para cuenta/método permitidos. Operador crea y comparte URL oficial → pagador abre y revisa → continúa con opción compatible → autoriza fuera de Tappy según el proveedor → servidor concilia transacción → operador ve recepción. Visitar `successUrl` no cambia el estado a pagado.

Si el banco/checkout no permite un camino claro en el mismo teléfono, se registra la limitación y se ofrece QR desde el dispositivo del comercio o celular cuando esté habilitado. No se declara exitoso HP03 por solo abrir una URL.

## 3. Datos y preparación de pruebas

- Entorno sintético aislado: comercio A con receptor activo A, operador A; comercio B y operador B solo como fixtures de seguridad, sin registrar otro negocio en pey.
- Cobro sintético S1: 30,000 centavos ($300 MXN), concepto de prueba, referencia única. Ningún caso exige transferir $300 reales.
- Receptor inactivo, cuenta distinta, token vencido, token alterado y credencial de prueba deliberadamente inválida.
- Eventos de test con firma válida del secreto de pruebas, duplicados, timestamps fuera de tolerancia, payload alterado e IDs no asociados.
- Base PostgreSQL real de pruebas para integridad, concurrencia y recuperación; sin sustituir SQL por mocks en esos casos.
- Proveedor simulado controlable: respuesta correcta, error definitivo, timeout antes/después de aceptar, webhook anticipado, respuesta duplicada y latencia.
- Historial: una transferencia de $300, otra de $150, un pendiente de $200 y un evento repetido. Total esperado: $450, dos transferencias, dos ventas cubiertas.
- Reloj controlable para casos de vencimiento, medianoche y cambio de periodo.
- Inventario provisional: aproximadamente cuatro iPhones y tres Android, con disponibilidad de iPhones por aclarar. Registrar modelo, SO, banco, versión de app y red en pruebas manuales; agrupar cobertura por plataforma/versión/capacidades, no solamente por cantidad de equipos.
- Planificar validación de builds al 17-nov, regresión del 30-nov al 2-dic y paquete completo al 5-dic, según [calendario propuesto](04-decisiones-y-plan.md). Fechas objetivo no equivalen a ejecución ni aprobación de los casos.

Las pruebas reales no se ejecutan desde CI. No generar notificaciones a terceros ni hacer carga contra pey. Las pruebas de abuso/concurrencia se hacen contra la infraestructura propia y el proveedor simulado.

## 4. Casos de prueba

Cada fila define preparación/estímulo y resultado esperado. El reporte de ejecución añadirá fecha, entorno, dispositivo, evidencia, resultado y bug relacionado; hasta entonces su resultado es **no ejecutado**.

### Acceso, captura y creación

| ID | Preparación y acción | Resultado esperado | Nivel |
| --- | --- | --- | --- |
| QA01 | Iniciar sesión como operador autorizado y consultar negocio; renovar sesión tras expirar access token | Comercio correcto; renovación permite continuar sin perder un cobro en curso | API + móvil |
| QA02 | Token ausente, vencido no renovable, alterado, algoritmo/emisor/audience incorrectos; llamar cada ruta protegida | 401, ninguna mutación ni llamada a pey; app pide sesión sin exponer secretos | API |
| QA03 | Receptor PENDING/ERROR/inactivo; intentar cada método | Creación bloqueada con explicación; cero llamadas de generación | API + UI |
| QA04 | Probar vacío, cero, negativo, >máximo, demasiados decimales, notación no admitida e integer fuera de rango | Rechazo explícito en cliente y servidor; no redondeo silencioso ni llamada externa | Dominio + API |
| QA05 | Introducir 0.01, 300 y 300.10; serializar y recibir respuesta en pesos desde adaptador | 1, 30000 y 30010 centavos exactos; formato MXN correcto | Dominio/adaptador |
| QA06 | Revisar cobro antes de emitir; cambiar entrada y validar error | Beneficiario y monto completos; monto inválido no se envía; edición no altera intento emitido | UI |
| QA07 | Pey simulado devuelve QR con id y qrString, sin transactionId | PENDING, guardar id del QR; QR decodificado coincide byte a byte con payload; no se fabrica ID bancario | API + UI |
| QA08 | Dos POST concurrentes con misma clave y mismo contenido | Un cobro/intento y como máximo una invocación de creación; misma referencia recuperable | Integración SQL/API |
| QA09 | Reutilizar clave con otro monto/método; crear dos intentos simultáneos con claves distintas sobre la misma venta | 409 sin mutación indebida; restricción durable mantiene un intento activo | Integración SQL/API |

### Evidencia de pago y concurrencia

| ID | Preparación y acción | Resultado esperado | Nivel |
| --- | --- | --- | --- |
| QA10 | Enviar evento válido para solicitud, cuenta e importe esperados | Una transferencia; intento PAID; venta cubierta; commit consistente | Integración |
| QA11 | Alterar bytes/espacios del cuerpo firmado, firma, timestamp fuera de tolerancia o estructura | No confirmar ni crear transferencia; rechazo según protocolo; registro mínimo seguro | API |
| QA12 | Entregar mismo eventId varias veces, incluso concurrentemente | ACK del duplicado persistido; transferencia, métricas y efecto de negocio una sola vez | Integración SQL/API |
| QA13 | Dos eventId distintos para mismo providerTransactionId; entregar también evidencia por conciliación | Una transferencia y un efecto de negocio, independientemente del canal | Integración SQL/API |
| QA14 | Evento firmado con importe distinto, receptor ajeno, moneda o IDs incompatibles | No confirmar la venta por aproximación; incidencia. Transferencia solo se registra como recibida si su recepción y cuenta se verifican; cuenta ajena nunca suma al comercio | Integración |
| QA15 | Webhook llega antes de persistir respuesta de creación; después llega respuesta PENDING | Evento durable se asocia/reprocesa; resultado final PAID; respuesta no degrada pago | Integración SQL/API |
| QA16 | Timeout de POST, simulando que proveedor sí creó solicitud; reintento móvil con misma clave | RECONCILING, referencia local visible, no segundo POST automático; no falso FAILED | Integración |
| QA17 | Error definitivo documentado antes de crear solicitud, frente a 5xx ambiguo | Solo error definitivo pasa a FAILED; ambiguo va a RECONCILING; conserva trazabilidad | Adaptador + API |
| QA18 | Expirar QR y generar nuevo intento tras conciliación; llega pago auténtico del primero | Mismo cobro; pago tardío reconocido; retirar presentación cobrable del nuevo y advertir riesgo si no es revocable | Integración + UI |
| QA19 | Dos providerTransactionId distintos pagan el mismo cobro, incluso simultáneamente | Dos transferencias conservadas; total recibido suma ambas; venta cubierta una vez; REVIEW/incidencia, sin devolución automática | Integración SQL/API |
| QA20 | Pago y tarea de expiración compiten; evento pending antiguo llega después de paid | PAID no se degrada; saldo/transferencias consistentes sin depender del orden | Integración SQL/API |

### Historial, métricas y recuperación

| ID | Preparación y acción | Resultado esperado | Nivel |
| --- | --- | --- | --- |
| QA21 | Cargar fixtures $300+$150, pendiente $200 y evento repetido; paginar y abrir detalles | Total $450, 2 transferencias, 2 ventas cubiertas; pendiente visible separado; intentos no inflan ventas | Integración + UI |
| QA22 | Agregar otro movimiento bancario real distinto de $300 para S1 | Total $750 y 3 transferencias; 2 ventas cubiertas; S1 con incidencia visible | Integración |
| QA23 | Movimientos a ambos lados de medianoche local, lunes y cambio de mes | Agrupación por America/Mexico_City, semana lunes-domingo; UTC no altera periodo local | Dominio/SQL |
| QA24 | Transferencia ocurrida al cierre de mes notificada al siguiente; timestamp bancario ausente en otro caso | Corregir periodo de ocurrencia validada; si no existe usar recepción con semántica explícita; sin duplicados | Dominio/SQL |
| QA25 | Confirmar pago sin webhook; conciliar por QR id con varias páginas; simular 429/timeouts | Encontrar transferencia y aplicar una vez; respetar esperas/cuotas; ausencia de evidencia conserva incertidumbre | Adaptador + integración |
| QA26 | Terminar app mientras espera, reabrir; volver del banco; reloj local adelantado/atrasado | Estado recuperado del servidor; vencimiento no depende del reloj local; no recrear solicitud | Móvil |
| QA27 | Persistir PAID y medir app en primer plano; enviar 20 consultas del mismo estado | Reflejar dentro de objetivo de demo; consultas leen DB y no producen 20 llamadas a pey | API + móvil |
| QA28 | Sin red antes de crear, durante POST o durante espera | Antes: no emitir y conservar monto. POST incierto: misma clave y conciliación. Espera: no éxito nuevo; mostrar última actualización | Móvil + integración |

### Accesibilidad, seguridad y operación

| ID | Preparación y acción | Resultado esperado | Nivel |
| --- | --- | --- | --- |
| QA29 | Texto grande/200%, pantalla pequeña, teclado visible, ambos temas implementados, reducción de movimiento | Monto/beneficiario/acciones sin truncar; controles alcanzables; contraste evaluado en estados reales | Manual |
| QA30 | VoiceOver/TalkBack y teclado web; transiciones de estado y consultas repetidas | Orden lógico, nombres claros, lectura de MXN y anuncio único por cambio significativo | Manual |
| QA31 | Operador A intenta listar/abrir/conciliar recursos B, cambia IDs y merchantId; probar Data API sin privilegios | No obtiene datos ni modifica recursos; tablas privadas inaccesibles desde claves públicas | API + DB |
| QA32 | Exceder cuota de creación/lectura/push, cuerpo y paginación; llamar también URL directa de Supabase | 429/413/validación apropiada, sin llamadas externas excedentes; cuotas durables no se evaden entre funciones ni por endpoint directo | Integración + configuración |
| QA33 | Interrumpir función antes/después de guardar evento y durante procesamiento; DB indisponible al recibir | Sin ACK previo al commit; evento persistido se recupera con Cron/lease; cero duplicidad monetaria | Integración |
| QA34 | Entrar sin invitación al recorrido público y buscar generación real, datos de integración o secretos | Simulación rotulada, aislada y utilizable; sin acceso monetario o datos personales reales | Web/API + revisión |

### Canales adicionales y comprobación externa

| ID | Preparación y acción | Resultado esperado | Nivel |
| --- | --- | --- | --- |
| QA35 | Número inválido y número de demo autorizado; crear push aceptado | Inválido no sale al proveedor; aceptado queda pendiente, sin afirmar notificación entregada/leída | API + UI |
| QA36 | Banco/número habilitado, no habilitado, notificaciones apagadas, solicitud ignorada/rechazada/vencida | Documentar observación real; Tappy no inventa estado de entrega/rechazo; ausencia de pago conserva pendiente/conciliación y alternativa | Manual externo controlado |
| QA37 | Pagar push autorizado y reenviar solicitud repetidamente | Confirmación por evidencia auténtica; deduplicación; cuota protege al número consentido | Integración + manual externo |
| QA38 | Crear link, abrir y cancelar compartir; abrir successUrl directamente sin pagar | URL oficial, misma venta, sin falso PAID; no se declara vencido el checkout por temporizador local | API + UI |
| QA39 | Webhook link pending/processing/paid/partial, transacción de otro método/cuenta o sin evidencia suficiente | No degradar paid; conciliar transferencia; REVIEW para parcial o incompatibilidad; no confirmar por texto del estado | Integración |
| QA40 | Completar checkout desde mismo teléfono con banco A y B disponibles | Registrar pasos, método, beneficiario y resultado observado; solo habilitar experiencia validada; sin prometer universalidad | Manual externo controlado |
| QA41 | Inspeccionar bundles, git, respuestas/logs, backup y configuración; verificar medidas móviles exigibles | Sin credenciales/datos completos; permisos mínimos; restauración comprobada y requisitos de integridad pendientes resueltos antes de real | Revisión + operación |
| QA42 | HP01 en dispositivos/bancos del equipo, importe mínimo acordado, integración autorizada | Solicitud auténtica y recepción verificada ligada al historial; evidencia sanitizada; observaciones separadas de pruebas simuladas | Manual externo controlado |
| QA43 | Abrir landing y materiales en móvil/escritorio; revisar declaraciones de producto y trabajo previo | Objetivo, canales disponibles, acceso y limitaciones coherentes; sin NFC ni métricas inventadas | Manual |

### Supabase y paridad entre clientes

| ID | Preparación y acción | Resultado esperado | Nivel |
| --- | --- | --- | --- |
| QA44 | Llamar API de operador solo con clave publicable, token alterado y luego JWT válido; invocar worker sin clave interna/con clave de usuario; entregar webhook sin JWT pero firmado | Exigir identidad de usuario en API; rechazar usuario/anon en worker; webhook válido llega a verificación de firma sin pedir JWT Supabase | Funciones/API |
| QA45 | Invocar RPC privilegiadas y tablas privadas desde Data API con `anon`/`authenticated`; intentar actor/comercio falsos en JSON de la app | Acceso directo denegado; actor procede solo del token verificado; membresía y pertenencia comprobadas dentro de RPC | SQL/API |
| QA46 | Fallar dentro de la RPC después de insertar transferencia pero antes de actualizar cobro/evento; repetir evidencia | Rollback completo; luego un solo commit consistente. Las llamadas SDK separadas no se aceptan como sustituto de esta atomicidad | Integración SQL |
| QA47 | Worker interrumpido con lease activo; Cron vuelve a invocar; dos ejecuciones reclaman pendientes al mismo tiempo | Recuperación tras lease, sin pérdida de tarea ni efecto monetario doble; lotes/cuotas acotados | Funciones/SQL |
| QA48 | Finalizar tarea de fondo después del ACK antes de procesar evento; retrasar Cron temporalmente | Trabajo sigue persistido; recuperación al siguiente ciclo; no mostrar recibido hasta commit; alertar retraso | Funciones/SQL |
| QA49 | Decodificar fixtures comunes en TS y Swift: centavos, fechas UTC, campos opcionales, errores, estado desconocido | Datos equivalentes; sin float monetario ni crash ante estado desconocido; presentar incertidumbre sin inventar PAID | Contrato TS/Swift |
| QA50 | Abrir misma venta desde Expo y SwiftUI; crear intentos concurrentes y recibir pago | Un intento activo según regla común; conflicto explícito en segundo cliente; ambos recuperan el mismo resultado confirmado | Integración de clientes |
| QA51 | Ejecutar captura → método → espera → resultado → historial/resumen en Expo Android, Expo iOS y SwiftUI iOS | Paridad funcional del alcance acordado y evidencias por combinación; sin duplicar motor ni declarar aprobado el cliente no probado | Móvil/manual |
| QA52 | Instalar Expo iOS y SwiftUI a la vez, iniciar sesión por separado, revisar bundles y almacenamiento | Identidades instalables distintas; sesiones almacenadas con protección explícita; ningún secreto de pey/administración ni tokens copiados entre apps | iOS + revisión |
| QA53 | En cada cliente salir, bloquear pantalla, cancelar consulta, regresar del banco y provocar respuestas fuera de orden | Consultas ligadas al ciclo de vida; sin congelar UI ni aplicar respuesta obsoleta sobre PAID; recuperar estado y no repetir POST incierto | Expo/SwiftUI |

## 5. Edge cases y decisiones de comportamiento

| Caso | Comportamiento de producto | Evitar |
| --- | --- | --- |
| QR vencido pero fotografiado | Ocultarlo en Tappy, conciliar y admitir evidencia tardía | Afirmar que ya no puede recibir dinero |
| Webhook antes del ID del proveedor | Guardar y asociar/reprocesar con referencias verificables | Descartarlo porque aún no aparece el intento |
| Cobro duplicado por dos transferencias | Registrar ambas, advertir y abrir revisión | Deduplicarlas por monto o borrar una |
| Pago por importe distinto | Conservar evidencia validada e incidencia sin cubrir automáticamente la venta | Ajustar importe original o asumir propina |
| Pagador muestra captura | Mantener pendiente hasta evidencia del backend | Botón de confirmación manual |
| No llega push | Orientación y alternativa; controlar reenvíos | Asegurar que no tiene CoDi o que rechazó |
| Resultado HTTP ambiguo | Verificar con misma referencia; no recrear a ciegas | Reintento automático de POST monetario |
| Se paga un intento viejo con uno nuevo activo | Aceptar pago auténtico y retirar nueva presentación; advertir que no hay revocación garantizada | Mantener dos solicitudes visibles sin advertencia |
| App vuelve del banco o checkout | Recuperar estado del servidor | Mostrar éxito por deep link de retorno |
| Proveedor o DB caídos | Explicar indisponibilidad y recuperar trabajos; no emitir éxito | Perder eventos después de responder 2xx |
| Se desconoce banco/compatibilidad | Ayuda y opciones comprobadas | Diagnóstico universal de enrolamiento inexistente |
| Cuenta se desactiva o queda incierta | Bloquear nuevos cobros hasta verificar estado; conservar historial | Borrar pagos ya confirmados |

## 6. Estrategia y condiciones para entregar

Pruebas de dominio para importes, estados y periodos; pruebas de integración con PostgreSQL para invariantes de dinero y acceso; pruebas del adaptador con fixtures oficiales versionados; recorridos manuales de app y landing; pruebas externas pequeñas y autorizadas para lo que los mocks no pueden demostrar.

No exigir cobertura porcentual arbitraria ni escribir pruebas que solo repliquen componentes. Priorizar los riesgos de acreditar dinero inexistente, duplicar operaciones, perder evidencia y exponer datos.

Criterio de salida: casos críticos de acceso, creación, firma, duplicidad, recuperación e importes aprobados; HP01 auténtico comprobado para anunciar integración; P1 solo se anuncia funcional si sus recorridos y pruebas aplicables se completan. Añadir QA44–53 y matriz Expo Android/Expo iOS/SwiftUI iOS para cerrar backend Supabase y paridad. Incidencias conocidas y dispositivos/bancos se incluyen en la entrega. Un test con fixture válido no prueba el webhook real de pey.

Formato futuro de ejecución: `QAxx | fecha | commit | entorno | dispositivo/SO/banco | resultado PASS/FAIL/BLOCKED | evidencia | incidencia`. Una dependencia externa bloqueada no se reporta como aprobada.
