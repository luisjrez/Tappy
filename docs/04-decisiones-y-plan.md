# Decisiones abiertas y secuencia de trabajo

Propuesta v0.3 · 10 de noviembre de 2026. El usuario solicita Expo y SwiftUI en paralelo y analizar Supabase completo. La distribución del trabajo, el stack backend revisado y los hitos intermedios son recomendaciones, no asignaciones aceptadas.

## 1. Registro de decisiones

| ID | Tema | Estado | Propuesta o dato necesario | Impacto |
| --- | --- | --- | --- | --- |
| D01 | NFC | Confirmado por usuario | Fuera del proyecto actual | Retirar de navegación y mensajes de entrega |
| D02 | Negocio inicial | Confirmado por usuario | Negocio ficticio y colaboradores consentidos | Demo técnica; no se presume validación con comercios |
| D03 | Planificación antes de código | Confirmado por usuario | Alcance, arquitectura, historias y pruebas primero | Esta carpeta es la primera entrega |
| D04 | Evento/bases | Fechas concordantes; enlace pendiente | Arranque 14-nov confirmado por usuario; bases de referencia: postulación 10-dic, entrega 12-dic | Planear entrega interna antes de ambos cierres |
| D05 | Equipo y tiempo | Parcialmente confirmado por usuario | Cuatro integrantes provisionales; todo listo el 5-dic. Faltan horas/roles por persona | Calendario tentativo; capacidad no estimada todavía |
| D06 | Sandbox | Validación externa pendiente | Confirmar acceso efectivo; fuentes públicas no coinciden | No hacerlo dependencia exclusiva de la demo |
| D07 | Cuenta/titular de integración | Validación externa pendiente | Elegibilidad, titularidad y receptor activado | Bloquea pruebas reales, no diseño ni pruebas locales |
| D08 | Canales obligatorios | Propuesta | QR como núcleo; celular y enlace como objetivo posterior en el hackathon | Confirmar compromiso tras plazo y contratos |
| D09 | Backend | Propuesta revisada tras investigación | Supabase Auth/Postgres/Edge Functions/Cron, sin NestJS inicial | Menos servicios; probar runtime, RPC, firma y controles de acceso |
| D10 | Plataforma de demo | Inventario provisional | Aproximadamente 4 iPhones/3 Android; aclarar contradicción sobre iPhones y registrar modelos/SO | Proponer ambas plataformas; verificar distribución temprano; tablet fuera de compromiso |
| D11 | Diseño móvil | Incorporación anunciada por usuario | Usuario añadirá diseño al directorio y explorará conexión MCP; aún no disponible/revisado | Revisar referencia antes de cerrar componentes y pantallas |
| D12 | Presupuesto/hosting | Pendiente | Plan Supabase y hosting estático; sin hosting Node adicional | Verificar disponibilidad, respaldos y controles/límites de consumo |
| D13 | Actualización de estado | Propuesta | Consulta REST cada 3 s en espera, lectura DB | Menos piezas; objetivo de actualización dentro de 10 s |
| D14 | Reintento y pagos tardíos | Propuesta | Conciliar, conservar venta, avisar riesgo, registrar ambos pagos si llegan | Confirmar copy y resolución operativa de incidencias |
| D15 | Demo pública | Propuesta con validación del evento | Recorrido sintético público + evidencia/acceso controlado de integración | Cumplir evaluación sin operaciones monetarias anónimas |
| D16 | Uso de enlaces | Pendiente de contrato/prueba | Cuenta receptora, CoDi disponible, redirecciones y mismo teléfono | No tratarlos como QR con URL ni asumir expiración |
| D17 | Multi-comercio | Fuera de demo; validación futura | Permisos por comercio en modelo; no alta de terceros sin acuerdo | Evitar asumir facultades de plataforma |
| D18 | Importes y cuotas de demo | Pendiente | Mínimo/máximo por prueba, volumen y números consentidos | Configuración antes de dinero real |
| D19 | Retención y controles móviles | Pendiente externo | Guías aplicables de pey, integridad, datos permitidos y conservación | Puede afectar librerías/build y validación productiva |
| D20 | Cliente SQL/ORM | Propuesta revisada | SDK Supabase, migraciones SQL y RPC para operaciones atómicas; sin ORM adicional | Requiere revisión de permisos y transacciones SQL |
| D21 | Dos implementaciones móviles | Confirmado por usuario | Expo/TypeScript y SwiftUI nativo mantenidos en paralelo | Una lógica backend, dos interfaces y QA para Expo Android/Expo iOS/SwiftUI iOS |
| D22 | Responsable y entorno SwiftUI | Pendiente | Experiencia/disponibilidad dedicada, Mac/Xcode, firma y distribución | Dependencia adicional para cumplir ambas versiones el 5-dic |

Los acuerdos duraderos sobre arquitectura/servicios se registrarán como ADR breves cuando se acepten. No se presenta la recomendación como una decisión tomada por el usuario.

## 2. Validaciones que cambian el plan

1. Si no es la convocatoria encontrada, reemplazar requisitos de evento antes de congelar la entrega.
2. Si solo hay simulación y las bases exigen producción, el proyecto puede avanzar como prototipo pero no cumple todavía el requisito de integración.
3. Si el titular propuesto no es elegible, resolver con pey una modalidad autorizada; no usar un tercero o inventar datos para evitar la validación.
4. Si la guía móvil exige capacidades no disponibles en la configuración elegida, ajustar Expo/build/módulos antes de comprometer producción.
5. Si checkout no garantiza receptor/método apropiados, mantenerlo fuera de la demo funcional hasta resolverlo. QR y celular no heredan ese problema automáticamente.

Fuentes y preguntas externas: [investigación](research/pey-validation.md). No se ha contactado a pey ni a los organizadores; esta planificación no envía mensajes a terceros.

## 3. Secuencia propuesta

| Fase | Resultado concreto | Condición de salida |
| --- | --- | --- |
| 0. Cerrar definición | Alcance acordado, dispositivos, equipo, bases, stack y criterios | D04/D05/D08–D12/D22 definidos; requisitos externos identificados |
| 1. Despejar integración | Contrato oficial guardado, acceso/alta adecuados, fixture por canal y respuestas | Receptor elegible/activo para real; firma y referencias comprendidas |
| 2. Diseñar contratos y flujo | Estados, wireflow, contrato HTTP/fixtures compartidos por TS/Swift y esquema/RPC revisados | Correspondencia ambas UI → mismas reglas → pruebas; D14/D16/D19 resueltos cuando aplican |
| 3. Base técnica | Sesión, permisos, migraciones, despliegue, secretos y simulador aislado | Pruebas de acceso/aislamiento y operación aprobadas |
| 4. Corte vertical QR | Crear → esperar → evidencia → historial/resumen | QA críticos y HP01 en entorno de integración correspondiente |
| 5. Celular y enlace | Cada canal sobre el mismo motor, sin repetir lógica financiera | HP02/HP03 y casos específicos, según alcance acordado |
| 6. Diseño y robustez | Componentes accesibles, red incierta, expiración, incidentes y recuperación | Matriz de QA y limitaciones documentadas |
| 7. Materiales de entrega | Landing, video, demo pública, descripción y declaración de activos | Formato de bases cumplido y demostración reproducible |

El calendario siguiente distribuye hitos hacia el 5 de diciembre; no representa una estimación de esfuerzo validada. Faltan horas disponibles por integrante y resultados de las dependencias externas. El corte QR incluye interfaz, API, base y pruebas, para comprobar el sistema completo temprano.

### Calendario hacia la entrega interna

Todas las fechas son de 2026 y se entienden en Ciudad de México. El objetivo del 5 de diciembre no se desplaza automáticamente al cierre oficial.

| Ventana | Resultado esperado | Evidencia para darlo por cerrado |
| --- | --- | --- |
| 10–13 nov | Planificación: alcance, diseño disponible, responsables, requisitos de acceso y cuenta | Documentos revisados; dependencias y preparación de alta identificadas. Sin comenzar integración ni desarrollo sustancial antes del periodo del evento |
| 14–17 nov | Supabase/auth/RPC/funciones/CI y build inicial de Expo Android, Expo iOS y SwiftUI iOS | Acceso al mismo contrato y entorno; rutas de instalación verificadas en las tres combinaciones |
| 18–21 nov | QR completo en ambos clientes, historial/resumen mínimos y evidencia del proveedor | Flujo trazable desde cada implementación, si acceso auténtico habilitado; pruebas críticas backend comunes ejecutadas |
| 22–25 nov | Celular/enlace y reportes con paridad sobre el motor común | Validación de canal, cuenta, banco y ambos clientes. Decisión expresa de alcance de cada canal a más tardar el 25 |
| 26–29 nov | Pantallas, landing y recuperación; congelar funcionalidades en ambas apps el 29 | Recorridos y paridad revisados; sin añadir funciones después del corte |
| 30 nov–2 dic | Regresión/accesibilidad de Expo Android, Expo iOS y SwiftUI iOS | Reporte por implementación/plataforma; sin fallos críticos/altos de dinero/acceso; diferencias documentadas |
| 3–4 dic | Grabar demo, preparar descripción, instrucciones y revisar enlaces | Video e instrucciones basados en flujo realmente comprobado; paquete ensayado por alguien distinto de quien lo implementó |
| **5 dic** | **Todo listo internamente** | Ambas apps identificadas por versión, evidencia de paridad, materiales completos, pruebas relevantes aprobadas, secretos protegidos y acceso de evaluación comprobado |
| 6–9 dic | Colchón para contingencias y correcciones | Regresión de cada corrección; no ampliar alcance. Cerrar postulación antes de su límite oficial |
| 10/12 dic | Cierres oficiales de referencia | Postulación y entrega verificadas en el portal; no esperar al último día para subir materiales |

Si al 21 de noviembre no hay acceso productivo/receptor activo, revisar inmediatamente el riesgo de entrega y la modalidad autorizada con pey; no declarar cumplido el hito con un mock. Si el núcleo sigue inestable el 25, resolver expresamente si se recortan canales adicionales; no consumir el periodo de QA para aparentar más funciones.

Las [bases oficiales de referencia](https://hackatonmexico.com/reglas), secciones 5, 9 y 10, distinguen postulación y entrega, permiten preparación previa y requieren que la integración y el trabajo sustancial se realicen durante construcción. La demo debe seguir disponible durante evaluación; el 5 de diciembre no es una fecha para apagar servicios.

### Distribución sugerida para cuatro integrantes

| Frente | Responsabilidad principal | Revisión y respaldo |
| --- | --- | --- |
| A. Expo | App iOS/Android, navegación, estado y UI de reportes | B revisa flujos iOS y paridad; D respalda builds/QA |
| B. SwiftUI | App iOS nativa, sesión, flujos y UI de reportes | A revisa contrato/paridad; D respalda builds/QA |
| C. Backend Supabase | Auth/permisos/RPC, adaptador pey, webhooks y conciliación | D revisa y respalda pagos/SQL/operación; A/B verifican contrato |
| D. Web/plataforma/calidad | Landing, tokens comunes, CI/builds y coordinación de pruebas | C respalda servicios; A/B prueban sus clientes; D comparte revisión de seguridad |

Son frentes, no puestos exclusivos ni personas ya asignadas. Cada integrante prueba su trabajo; D no concentra toda la responsabilidad de calidad. Registrar una persona principal y una de respaldo para despliegue, acceso a servicios y grabación, sin compartir secretos en documentos. Acordar contratos antes de dividir pantallas, API y datos.

El segundo cliente aumenta trabajo de UI, sesión, distribución y regresión; el calendario mantiene el 5-dic como objetivo, pero no se considera validado sin D22 y dedicación por integrante. No se retrasa ni recorta una implementación por defecto: cualquier ajuste debe ser explícito. Detalle: [apps en paralelo](05-apps-paralelas.md).

## 4. Proceso para avanzar con menos retrabajo

Cada pieza de implementación tendrá: requisito/historia vinculada, contrato de entrada/salida, estados y errores, pruebas relevantes, dependencias y criterio de terminado. Primero se revisan los casos de dinero y acceso; después se implementa una porción utilizable y se verifica antes de ampliar canales.

Un cambio a monto, receptor, definición de pago, reintentos o métricas se refleja en producto, arquitectura, historias y pruebas. Una variación puramente visual no requiere reabrir todo el sistema. Cada bug se reproduce y se añade una prueba cuando protege una regla significativa.

La planificación reduce ambigüedad; no elimina hallazgos durante la integración. Se reservan puntos de ajuste después de verificar payloads reales y probar dispositivos. No se inventará certeza para completar el documento.

## 5. Definition of Ready / Definition of Done

**Listo para desarrollar:** la historia tiene alcance acordado, diseños/estados relevantes, datos y contrato definidos, criterio verificable y dependencias conocidas. Una dependencia externa puede sustituirse temporalmente con simulación explícita, pero esa simulación no permite cerrar una integración real.

**Terminado:** comportamiento implementado y revisado, pruebas pertinentes aprobadas, accesibilidad correspondiente comprobada, secretos/datos protegidos, error/recuperación implementados y documentación actualizada. Un canal externo exige evidencia auténtica para declararse integrado.

## 6. Decisiones prioritarias para la siguiente conversación

Confirmar responsable/entorno SwiftUI, disponibilidad por integrante y presupuesto; revisar el diseño cuando el usuario lo añada. Cerrar el compromiso de los tres canales y adoptar o ajustar la propuesta Supabase completa. Cuatro integrantes, dos implementaciones paralelas y objetivo del 5-dic ya se incorporaron; no hace falta volver a preguntarlos. Las respuestas externas sobre cuenta, sandbox e integridad siguen pendientes.
