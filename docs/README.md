# Tappy: definición previa a implementación

Fecha: 10 de noviembre de 2026. Versión: 0.3. Estado: **propuesta para discusión**, salvo las decisiones del usuario señaladas como confirmadas. No se ha implementado la aplicación ni ejecutado pruebas bancarias o de software durante esta preparación.

## Objetivo de esta carpeta

Definir qué demuestra Tappy en el hackathon, qué comportamiento debe funcionar y cómo se construirá y comprobará. Esta documentación precede al desarrollo; no convierte las hipótesis en resultados comprobados.

| Documento | Pregunta que responde |
| --- | --- |
| [Producto y entrega](01-producto-y-entrega.md) | ¿Para qué existe, cuál es el MVP y qué se entrega? |
| [Arquitectura](02-arquitectura.md) | ¿Cómo funciona, dónde vive cada responsabilidad y cómo se protege? |
| [Historias y pruebas](03-historias-y-pruebas.md) | ¿Qué hace cada persona y cómo se comprueba el resultado? |
| [Decisiones y plan](04-decisiones-y-plan.md) | ¿Qué está acordado, qué falta resolver y en qué orden avanzar? |
| [Expo y SwiftUI](05-apps-paralelas.md) | ¿Qué comparten las dos apps y cómo se comprueba paridad? |
| [Validación de pey](research/pey-validation.md) | ¿Qué dicen las fuentes oficiales y qué sigue pendiente? |
| [Investigación de Supabase](research/supabase-backend.md) | ¿Puede cubrir el backend completo y con qué límites? |
| [Glosario](../CONTEXT.md) | ¿Qué significan cobro, intento, transferencia y conciliación? |

## Decisiones confirmadas por el usuario

- NFC queda fuera del proyecto actual, incluyendo el entregable del hackathon.
- Se empieza con un negocio ficticio para la demo y participantes autorizados; no con un piloto en comercios reales.
- QR, solicitud al celular y enlaces forman parte del alcance que se quiere estructurar.
- Hay que definir objetivo, requisitos, arquitectura, historias y pruebas antes de implementar.
- Se desea app móvil y landing; la compatibilidad formal con tablet está por decidir.
- El proyecto de citas y anticipos por WhatsApp sigue siendo independiente.
- El equipo cuenta provisionalmente con cuatro integrantes; no se ha fijado dedicación por persona ni un stack común.
- La fecha interna objetivo es el **5 de diciembre de 2026**, incluyendo pruebas, demo grabada y materiales listos. Se buscará terminar durante la primera semana de diciembre y conservar margen para contingencias.
- El usuario sitúa el arranque el 14 de noviembre y la postulación alrededor del 10 de diciembre, coincidentes con las bases investigadas. No confundir postulación con entrega final: la fuente oficial indica 10 y 12 de diciembre, respectivamente.
- El diseño externo se añadirá al directorio; el usuario explorará conectar su herramienta de diseño por MCP. No se considera conectado ni revisado todavía.
- Se mantendrán dos implementaciones en paralelo: Expo/TypeScript y SwiftUI nativa. El usuario prioriza rapidez y el menor número de servicios, y solicita evaluar Supabase como backend completo.

## Recomendaciones aún por acordar

- Priorizar un flujo QR completo como primera entrega técnica; incorporar celular y enlace con el mismo motor de cobros.
- Backend Supabase completo: Auth, PostgreSQL, Edge Functions TypeScript y Cron. Esta recomendación sustituye la anterior de NestJS después de analizar la prioridad de reducir servicios; falta acordar configuración/plan y validar runtime con pey.
- Expo iOS/Android y SwiftUI iOS consumen un único contrato y motor de pagos; no duplicar integración bancaria. Dos responsables móviles y un frente de backend con respaldo.
- Un comercio y una cuenta receptora autorizada en la integración de demostración. Conservar límites de acceso por comercio sin habilitar una plataforma multi-comercio real.
- Consulta periódica de estado en la app para la primera versión, con procesamiento confiable de webhooks en servidor.
- Landing pequeña y demo pública separada del acceso que permite generar cobros reales.
- Teléfono en Android e iOS como objetivo provisional de pruebas: se mencionaron aproximadamente cuatro iPhones y tres Android, con una contradicción verbal sobre disponibilidad de iPhones que falta aclarar. No hay modelos, versiones ni tablets confirmados.

## Estado del repositorio al iniciar

Existen [especificación de identidad](../TAPPY_BRAND_IDENTITY_SPEC.md), [sistema visual web y CSS](../design-system/README.md) y tres rutas de imágenes en `mobile-concepts/`: Mostrador, Recibo y Jornada. Son referencias y activos de diseño, no evidencia de una app implementada. El diseño externo mencionado de Panda Dev aún no ha sido revisado.

Las referencias históricas que muestran NFC o estados como `cancelled` no definen el nuevo alcance ni prueban que pey ofrezca esas capacidades. Los estados y el alcance de esta carpeta tienen prioridad para la propuesta técnica; se actualizarán los diseños durante la revisión de interfaz.

## Cómo cerrar esta definición

Resolver los pendientes críticos de [decisiones](04-decisiones-y-plan.md), acordar el alcance y convertir cada historia aceptada en trabajo ejecutable. Los casos de prueba están **definidos y no ejecutados**. Se ajustará el contrato de integración con los esquemas oficiales y las respuestas observadas antes de desarrollar cada canal.
