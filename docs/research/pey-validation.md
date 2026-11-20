# Validación documental de pey para Tappy

Fecha de consulta: **10 de noviembre de 2026**. Investigación de fuentes primarias; no se realizaron llamadas autenticadas, altas, transferencias ni pruebas de integración. Leer documentación no demuestra compatibilidad bancaria ni autorización contractual.

## Resultado para la planificación

**No basar la entrega en un sandbox disponible.** La documentación técnica anuncia el ambiente de pruebas como próximo y publica solamente producción. Los términos describen un sandbox; esta diferencia exige confirmación directa. El comercio puede ser ficticio en la narrativa, pero el titular, las credenciales y la cuenta receptora de una prueba real deben corresponder al modelo autorizado.

Para desarrollo interno, Tappy puede usar un adaptador simulado identificado como tal. Esto es una propuesta arquitectónica; no equivale al sandbox de pey ni a demostrar una integración real.

## Entornos y acceso: evidencia y discrepancias

- La portada indica `api.pey.mx` para producción y ambiente de pruebas «Próximamente». Recomienda validar con bancos reales y montos pequeños. [Portada técnica](https://docs.pey.mx/).
- El tutorial indica activación de cuenta bancaria en **5 días hábiles**. Ofrece temporalmente una cuenta publicada por pey que recibe dinero real; advierte que esos pagos no se devuelven. Esa cuenta no es un sandbox. No se incluyen aquí sus datos bancarios. [Crear una API key](https://docs.pey.mx/docs/tutorials/getting-started/create-an-api-key/).
- Los términos, cláusula 3.5, describen un sandbox. La documentación operativa aún no publica su acceso. **Pendiente:** obtener confirmación de disponibilidad, URL, credenciales, datos permitidos y eventos simulables. [Términos del API](https://pey.mx/legal/terminos-api).

## Contrato técnico consultado

La referencia OpenAPI declara versión `2026-10-20` y servidor de producción. Es una fotografía documental, no una garantía de comportamiento observado. [OpenAPI oficial](https://docs.pey.mx/openapi.json).

| Operación | Endpoint documentado | Referencia |
| --- | --- | --- |
| Crear QR | `POST /codi/qr` | [Crear QR](https://docs.pey.mx/docs/api/create-qr/) |
| Solicitud al celular | `POST /codi/pn` | [Crear push](https://docs.pey.mx/docs/api/create-push-notification/) |
| Crear checkout alojado | `POST /payment-link/create` | [Crear enlace](https://docs.pey.mx/docs/api/create-payment-link/) |
| Registrar cuenta | `POST /bank-account` | [Registrar cuenta](https://docs.pey.mx/docs/api/register-bank-account/) |
| Consultar cuenta | `GET /bank-account/{id}` | [Consultar cuenta](https://docs.pey.mx/docs/api/get-bank-account/) |
| Consultar transferencia | `GET /transaction/{id}` | [Consultar transacción](https://docs.pey.mx/docs/api/get-transaction/) |

Detalles extraídos del [OpenAPI oficial](https://docs.pey.mx/openapi.json):

- Autenticación: `Authorization: Bearer <api-key>`. Importes en MXN.
- QR: `201`, devuelve `id` y `qrString`; imagen opcional. No devuelve `transactionId` al crearlo. `expiration`: segundos; `0` sin vencimiento, positivo mínimo `360`. `amount: 0` permite importe libre. `numRef`: 1–7 dígitos.
- Push: `200`, devuelve `transactionId` y `codiId`; celular de 10 dígitos, importe positivo; expiración mínima y predeterminada `360` segundos.
- QR/push aceptan `bankAccountId`, que exige cuenta `ACTIVE`.
- Enlace: `200`, devuelve `id` y `url`; requiere importe positivo, `successUrl` y `backUrl` HTTPS. El esquema de creación no expone `bankAccountId`, selección de métodos ni expiración.
- Conciliación adicional: `GET /transaction/codi/qr/{id}` (20 por página), `/transaction/api-key` y `/transaction/bank-account/{id}` (80 por página), con `nextToken`.
- Consulta de enlace admite `pending`, `processing`, `paid`, `partial`; su webhook enumera solamente los primeros tres.

**Consecuencias propuestas para Tappy:** guardar centavos enteros y convertir en el adaptador; referencias internas independientes de `numRef`; guardar el ID del QR antes de esperar una transferencia. Un timeout de creación tiene resultado incierto: no repetir ciegamente el POST. La consulta de transferencias por QR mejora la recuperación cuando todavía no conocemos `transactionId`.

## Webhooks documentados

| Evento | Evidencia pública y matiz |
| --- | --- |
| `codi.qr.payment_received` | Pago recibido; incluye `codiQrId`, `transactionId`, importe, `apiKeyId`, fecha y metadata. `bankAccountId` solo aparece si se envió al crear QR. [QR pagado](https://docs.pey.mx/docs/webhooks/codi/qr/) |
| `codi.pn.payment_received` | Pago completado; incluye `transactionId`, importe, `apiKeyId`, fecha y metadata; cuenta explícita bajo la misma condición. [Push pagado](https://docs.pey.mx/docs/webhooks/codi/pn/) |
| `payment_link.status_updated` | Estados `pending`, `processing`, `paid`; contiene transacciones liquidadas con método, desglose e identificadores. [Estado de enlace](https://docs.pey.mx/docs/webhooks/payment-link/status-update/) |
| `bank.account.updated` | Exclusivamente transición a `ACTIVE`; los estados `PENDING`, `PROCESSING`, `ERROR` se consultan por API. [Cuenta activada](https://docs.pey.mx/docs/webhooks/bank-account/updated/) |

La configuración vincula un solo webhook a cada API key y proporciona un secreto rotatable. pey recomienda los SDK de Standard Webhooks. Su ejemplo verifica el **cuerpo crudo** y usa `webhook-id` para deduplicar. El portal ofrece historial de intentos de entrega. [Configuración](https://docs.pey.mx/docs/tutorials/getting-started/set-up-webhooks/), [Introducción](https://docs.pey.mx/docs/webhooks/introduction/).

El estándar firma cuerpo, ID y timestamp; define `webhook-id`, `webhook-timestamp`, `webhook-signature` y exige controlar antigüedad para limitar replay. Sus sugerencias de reintentos son recomendaciones del estándar, **no un calendario confirmado de pey**. [Especificación Standard Webhooks](https://github.com/standard-webhooks/standard-webhooks/blob/main/spec/standard-webhooks.md).

En las páginas revisadas no se documentan eventos de QR escaneado/expirado, push entregado/leído/rechazado/expirado ni una consulta universal de enrolamiento por teléfono. Tampoco se encontró una garantía pública de idempotencia de creación, calendario de reintentos o ventana de retención. Confirmar con soporte; no convertir ausencia de evidencia en una función prometida.

## Condiciones contractuales relevantes

Los [términos del API](https://pey.mx/legal/terminos-api), actualizados el 13 de octubre de 2026, distinguen:

- Cláusulas 3.3/5.4: habilitar comercios terceros requiere autorización escrita mediante Contrato Particular; cada comercio valida su registro y recibe en cuenta propia. La cuenta concentradora está prohibida.
- Cláusula 3.8: un proveedor tecnológico puede operar con credenciales del negocio titular, conservando este la responsabilidad e informando a pey.
- Cláusula 4.3: permite productos propios como POS/gestión/conciliación; restringe revender API o sustituir su infraestructura.
- Cláusula 5.5: exige medidas móviles contra permisos de administración no autorizados, revisión estática/dinámica y verificación de integridad, conforme a guías publicadas.
- Anexo B: el límite de solicitudes depende del contrato; no publica una cifra universal.

Estas disposiciones no confirman que Tappy ya esté autorizado. **Pendiente:** modalidad aplicable a la demo, titular receptor, requisitos de alta, controles móviles exigibles y tratamiento de datos permitido. La denominación ficticia del negocio nunca debe ocultar al pagador el beneficiario real.

## Hackatón localizado: confirmar que sea la convocatoria del equipo

Se encontró Hackatón México 2026, cuyo portal es pey.build. Síntesis de sus [reglas oficiales](https://hackatonmexico.com/reglas), actualizadas el 4 de noviembre de 2026:

- Construcción: 14 de noviembre–12 de diciembre. Postulación: 10 de diciembre, 23:59; entrega: 12 de diciembre, 23:59, Ciudad de México.
- Exige integración funcional en producción; simulaciones solas no cumplen.
- Entrega: descripción ≤500 palabras, demo pública con acceso de prueba cuando aplique, video ≤3 minutos, declaración de materiales previos/terceros, instrucciones ≤1000 palabras e integrantes. Repositorio opcional.
- Diseño/código previo permitidos con declaración. La sección 9.3 permite IA sin obligación de declararla. La integración y trabajo sustancial deben realizarse durante construcción.
- Evaluación: CoDi/API 30%, impacto 25%, técnica 15%, experiencia/diseño 15%, originalidad 15%.
- Producción exige validación del titular; menciona persona moral o física con actividad empresarial. No garantiza alta antes del cierre.
- Prohíbe estrés/carga artificial o investigación de vulnerabilidades de pey sin autorización escrita.

**Propuesta para la especificación:** mantener controles de acceso para operaciones monetarias aunque la demo sea públicamente accesible. Ofrecer recorrido de evaluación con datos ficticios y acceso controlado al flujo real; confirmar con organizadores que satisface la modalidad de demo elegida. No presentar una simulación como integración ni inventar métricas, comercios o usuarios.

## Preguntas externas que deben cerrarse

1. ¿Existe sandbox operativo hoy y qué pruebas soporta? ¿Cómo se resuelve la diferencia entre términos y documentación?
2. ¿Qué cuenta y titular puede usar el equipo en producción? ¿La cuenta personal propuesta es elegible y el titular cumple la condición de actividad empresarial de la convocatoria? ¿Qué validación y plazo aplican? **Bloquea la prueba real hasta confirmarlo.**
3. ¿Está autorizado el alcance de Tappy como POS para un negocio demo? ¿Qué se requiere después para varios comercios?
4. ¿Cuotas por cuenta/API key, tratamiento de `429`, timeouts e idempotencia de POST?
5. ¿Reintentos de webhooks, replay manual, retención y rotación del secreto sin perder entregas?
6. ¿Puede limitarse checkout a CoDi? ¿Cómo paga el cliente en su mismo teléfono y cómo se determina la cuenta receptora del enlace?
7. ¿Qué guías móviles concretas aplican a integridad y root/jailbreak en una demo Expo?
8. ¿Qué datos se consideran no almacenables y durante cuánto tiempo pueden conservarse eventos para auditoría?

No se enviaron estas preguntas a pey ni a organizadores. Requieren respuesta del equipo o comunicación expresamente autorizada.
