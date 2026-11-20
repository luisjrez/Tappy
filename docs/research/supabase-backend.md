# Supabase como backend completo de Tappy

Consulta: **10 de noviembre de 2026**. Fuentes oficiales. Estado: investigación y recomendación; no se provisionaron servicios, no se instaló software y no se ejecutaron pruebas de integración.

## Conclusión para la planificación

**Supabase puede cubrir el backend del MVP sin un servicio NestJS separado.** Es una inferencia arquitectónica a partir de las capacidades documentadas, no un resultado probado para pey. La opción mínima propuesta es Auth + PostgreSQL + Edge Functions + Cron, con trabajos durables en PostgreSQL. Realtime y Queues existen, pero no son requisitos del primer flujo.

Expo y SwiftUI pueden consumir el mismo contrato HTTP y autenticación. La lógica que determina que un cobro está pagado debe existir una sola vez en el backend. La landing continúa siendo una aplicación web con hosting estático; no hace falta forzar todo el producto dentro de un único proveedor.

## Capacidades comprobadas

| Necesidad | Capacidad documentada | Aplicación propuesta en Tappy |
| --- | --- | --- |
| Lógica de servidor | Edge Functions | Invocar pey y validar solicitudes/webhooks |
| Identidad | Supabase Auth e integración de funciones | Mismo sistema de sesión para Expo y SwiftUI |
| Integridad financiera | PostgreSQL y funciones SQL/RPC | Reserva idempotente y aplicación atómica de evidencia |
| Recuperación | Cron y funciones periódicas | Reintentar consultas y procesar trabajos pendientes |
| Cola administrada | Queues/pgmq | Alternativa a tablas de trabajos, si aporta simplicidad al equipo |
| Actualización en app | Realtime o lecturas HTTP | Empezar con polling; añadir canales privados si conviene |
| Archivos | Storage | Opcional para recursos que realmente deban subirse; no necesario para generar el QR desde su contenido |

Las funciones son código de servidor TypeScript sobre un runtime compatible con Deno. Pueden llamar servicios externos. La documentación admite dependencias npm, módulos JSR y APIs Node compatibles; recomienda configuración `deno.json` por función. Esto no convierte el runtime en un servidor Node persistente ni asegura compatibilidad de cualquier paquete npm. [Edge Functions](https://supabase.com/docs/guides/functions), [dependencias](https://supabase.com/docs/guides/functions/dependencies).

Las credenciales de pey y el secreto de webhooks pueden almacenarse como secretos del entorno de las funciones y leerse con `Deno.env.get`. Los secretos de Supabase que habilitan administración tampoco se entregan a los clientes. [Variables de entorno](https://supabase.com/docs/guides/functions/secrets).

## Autenticación de cada entrada

La documentación actual recomienda `@supabase/server` y `withSupabase`:

- App: `auth: 'user'` exige JWT de usuario y proporciona contexto del solicitante y cliente con RLS.
- Worker: `auth: 'secret'` comprueba una clave secreta en `apikey`; se desactiva `verify_jwt` para esta función.
- Webhook: `auth: 'none'` y `verify_jwt = false`; la función comprueba la firma del proveedor por sí misma, antes de mutar datos.
- `supabaseAdmin` omite RLS: su disponibilidad no significa que sea apropiado usarlo para cualquier consulta del operador.

El modo de autenticación no resuelve autorización por comercio: Tappy debe validar membresía y propiedad de cada recurso. [Guía de autenticación de funciones](https://supabase.com/docs/guides/functions/auth).

**Precaución con ejemplos antiguos:** las referencias actuales indican que `verify_jwt` soporta tokens HS256 y firmas asimétricas nuevas. También acepta API keys por compatibilidad. Por tanto, el flag por sí solo no demuestra que exista una sesión de usuario; no se debe autorizar una operación monetaria porque una clave publicable pasó el gateway. Mantener la comprobación explícita del modo `user` y probar claves publicables sin JWT, tokens ajenos, vencidos y alterados. [Headers y verificación](https://supabase.com/docs/guides/functions/auth-headers).

El ejemplo oficial de webhook utiliza `req.text()` y verifica firma sobre ese cuerpo original. El patrón es aplicable a Standard Webhooks de pey, pero habrá que comprobar su SDK en el runtime elegido. No analizar y volver a serializar JSON antes de verificar. [Ejemplo de webhook](https://supabase.com/docs/guides/functions/examples/stripe-webhooks). Esto es evidencia de la capacidad del runtime, no una recomendación de integrar Stripe.

## Transacciones, funciones SQL y exposición

PostgREST ejecuta cada petición dentro de una transacción. **Varias llamadas independientes de `supabase-js` no forman una sola transacción**, aunque estén en la misma Edge Function. Propuesta: una RPC para reservar cobro/intento/idempotencia/cuota y otra para aplicar evidencia/transferencia/estado de manera atómica. La llamada HTTP a pey queda entre ambas, sin mantener bloqueos SQL durante la red externa. [Transacciones de PostgREST](https://docs.postgrest.org/en/stable/references/transactions.html).

Supabase documenta controles separados de grants y RLS, además de esquemas API dedicados. Se pueden dejar tablas y helpers internos en un esquema no expuesto y ofrecer wrappers acotados. RLS no protege automáticamente funciones SQL; su ejecución se controla con privilegios. [Asegurar la Data API](https://supabase.com/docs/guides/api/securing-your-api).

Las funciones SQL usan `security invoker` por defecto. Si una RPC necesita `security definer`, fijar `search_path` seguro, calificar nombres de esquemas y comprobar propiedad en su cuerpo. Revocar `EXECUTE` de `PUBLIC`, `anon` y otros grants no necesarios, concediendo solo a los roles requeridos. Cambiar únicamente `search_path` no restringe quién puede invocarla. Las funciones creadas por `postgres` pueden omitir RLS. [Seguridad de funciones SQL](https://supabase.com/docs/guides/database/functions).

**Diseño mínimo sugerido:** clientes llaman Edge Functions para operaciones del cobro; tablas financieras privadas; RPC privilegiadas solo invocables por backend; identidad del operador obtenida del token verificado, no del JSON del cliente. Si después se exponen lecturas directas o RPC al usuario, diseñar grants/RLS y pruebas específicas. No permitir que el operador modifique `PAID`, destinatario o transferencias directamente.

## Trabajo recuperable y límites

Los límites documentados de Edge Functions alojadas son 256 MB, CPU de 2 segundos por solicitud, duración de worker de 150 segundos en Free y 400 en planes de pago, además de timeout de respuesta inactiva de 150 segundos. Las bibliotecas que necesitan multithreading no están soportadas. Estos valores deben volver a verificarse al elegir plan. [Límites](https://supabase.com/docs/guides/functions/limits).

`EdgeRuntime.waitUntil` permite continuar trabajo después de devolver la respuesta. El worker todavía termina al alcanzar límites y las tareas pueden fallar. **No equivale a una cola durable ni a una garantía de completar efectos monetarios.** Persistir la tarea primero y tratar esa ejecución como aceleración opcional, con recuperación independiente. [Tareas de fondo](https://supabase.com/docs/guides/functions/background-tasks).

Supabase soporta `pg_cron` y `pg_net` para invocar funciones periódicamente, con claves en Vault. La guía muestra invocación cada minuto y autenticación mediante clave secreta. También advierte que `pg_net` conserva temporalmente la clave descifrada en su cola HTTP, visible a roles de base con LOGIN. Restringir estrictamente esos accesos; no conceder login SQL a usuarios de la app. [Programación periódica](https://supabase.com/docs/guides/functions/schedule-functions).

Queues está construido sobre pgmq y persiste mensajes en PostgreSQL. La afirmación documental de entrega una vez está acotada a la ventana de visibilidad; **no garantiza que una llamada externa o una aplicación de pago suceda exactamente una vez**. El consumidor debe confirmar/eliminar después de completar y ser idempotente frente a una nueva entrega. [Queues](https://supabase.com/docs/guides/queues), [consumo desde funciones](https://supabase.com/docs/guides/queues/consuming-messages-with-edge-functions).

### Configuración mínima recomendada para Tappy

1. Una función de API del operador, una de webhook y una de worker, con módulos compartidos de dominio/adaptador; separar estas entradas por autenticación.
2. Tablas persistentes de eventos y conciliación con `runAt`, intentos, lease y estado; insertar evento y trabajo atómicamente antes de ACK.
3. Procesar inmediatamente la evidencia suficiente mediante RPC; si requiere consultar pey o falta asociación, dejar trabajo durable.
4. Worker reclama un lote pequeño mediante SQL, libera bloqueo antes de consultar pey y aplica resultado por RPC idempotente. Un fallo deja el trabajo recuperable tras vencer el lease.
5. Cron cada minuto recupera pendientes. Una invocación inmediata opcional acelera el procesamiento; la recuperación no depende de esa invocación.
6. Los reintentos automáticos se aplican a consultas/efectos internos idempotentes. No repetir POST de creación ambiguo a pey sin evidencia de que es seguro.

Esta es una propuesta de diseño. Si el equipo prefiere Queues para evitar implementar semántica de entrega, puede sustituir la tabla de trabajo, manteniendo referencias, backoff, incidencias y deduplicación de transferencias. No combinar las dos alternativas sin una necesidad clara.

## Realtime y abuso

Realtime permite Broadcast/Presence con políticas sobre `realtime.messages` y canales privados; los cambios PostgreSQL con RLS se entregan según acceso de lectura. Se debe diseñar autorización por topic/comercio, reconexión y recuperación. Propuesta para el MVP: polling de estado persistido en primer plano; Realtime es opcional y nunca la autoridad del pago. [Autorización de Realtime](https://supabase.com/docs/guides/realtime/authorization).

Los límites de Auth cubren endpoints de autenticación, no las cuotas de negocio de creación de cobros. La guía de rate limiting de funciones muestra un limitador adicional con Redis. No implica que Tappy necesite Redis: a escala de demo puede reservar cuotas atómicamente en PostgreSQL antes de llamar a pey. [Límites de Auth](https://supabase.com/docs/guides/auth/rate-limits), [limitación de funciones](https://supabase.com/docs/guides/functions/examples/rate-limiting).

Supabase describe salvaguardas de plataforma ante ráfagas y un modelo de responsabilidad compartida. No se encontró una garantía que sustituya controles propios de acceso, cantidad de operaciones, tamaño del cuerpo y volumen hacia pey. Free puede pausarse por inactividad; resolver disponibilidad y backup del plan elegido antes de la evaluación. [Preparación de producción](https://supabase.com/docs/guides/deployment/going-into-prod).

El Spend Cap de Pro incluye invocaciones de funciones y ciertos consumos, pero no es un presupuesto total configurable: excluye compute y complementos como dominio/PITR, y al alcanzar cuotas puede restringir servicio. Presupuesto, límites de gasto, cantidad de proyectos y seguimiento de consumo deben elegirse expresamente. [Control de costos](https://supabase.com/docs/guides/platform/cost-control).

## Pendientes antes de congelar arquitectura

- Prueba corta de runtime: Standard Webhooks, petición a pey y auth en ambos SDK clientes; sin asumir compatibilidad solo por soporte npm.
- Verificar disponibilidad/privilegios de Cron y la política de recuperación en el proyecto/plan real.
- Probar RPC ante concurrencia, rollback y eventos duplicados, y probar que la API key pública no permite invocarlas directamente.
- Confirmar límites de pey y el contrato de integración ya investigado; Supabase no resuelve activación del receptor, sandbox ni elegibilidad.
- Elegir plan y política de protección de funciones públicas/costos. Una fachada externa no elimina el acceso directo al endpoint de funciones si este sigue habilitado sin una comprobación equivalente.
- Validar cuánto SQL acepta mantener el equipo: Edge Functions evita un servidor adicional, pero conserva código de servidor y transacciones SQL que requieren revisión y pruebas.

NestJS queda como alternativa futura si aparecen procesos permanentes, trabajos largos, dependencias incompatibles o una necesidad operativa concreta. No se necesita introducirlo únicamente para invocar una API HTTP y recibir webhooks.
