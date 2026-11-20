# Expo y SwiftUI en paralelo

Propuesta v0.1 · 10 de noviembre de 2026. **Requisito del usuario:** mantener una versión Expo/TypeScript y otra nativa SwiftUI en paralelo. **Recomendación técnica:** un único backend Supabase y un contrato común. No se ha creado ninguno de los clientes.

## 1. Propósito de los dos clientes

Entregar el mismo flujo comercial y comparar el esfuerzo, experiencia y mantenimiento de una implementación multiplataforma con una nativa iOS. SwiftUI no es solamente una maqueta ni queda pospuesto por defecto; ambos clientes deben recorrer el núcleo acordado del MVP.

Hay dos implementaciones de interfaz y tres combinaciones de implementación/plataforma para verificar: Expo Android, Expo iOS y SwiftUI iOS. No se crea un cliente Android nativo adicional. iPad/tablet sigue sin compromiso formal para el hackathon.

## 2. Qué se comparte y qué se implementa dos veces

| Elemento | Compartido | Propio de cada cliente |
| --- | --- | --- |
| Comercios, cuentas y sesiones | Mismo proyecto Auth y base por entorno; mismo modelo de permisos | Tokens y almacenamiento seguro independientes; no copiar sesiones entre apps |
| API | Misma versión HTTP/JSON y política de idempotencia | Transporte TS y Swift, renovación y errores locales |
| Estado del cobro | Un único motor en servidor | Presentación y ciclo de vida de consultas |
| Integración pey | Edge Functions y SQL; una sola implementación | Ningún SDK de pey ni secreto dentro de clientes |
| Dinero y periodos | Mismas reglas, centavos, zona y contratos | Formato accesible local, sin usar float para calcular pagos |
| Diseño | Referencia, tokens semánticos, copy y jerarquía | Componentes React Native y vistas SwiftUI; navegación nativa correspondiente |
| Contratos de prueba | Fixtures JSON, casos y resultados esperados | Pruebas de interfaz, compilación y accesibilidad por implementación |
| Analítica de comparación | Mismos escenarios y condiciones registradas | Medición por plataforma/build, sin asumir ventaja de un framework |

No se comparte código TypeScript directamente con Swift. Se comparte la especificación y los datos de prueba. Los modelos de cada lenguaje deben coincidir con el contrato, sin duplicar en los clientes reglas que acreditan dinero.

## 3. Paridad funcional mínima

| Capacidad | Expo Android | Expo iOS | SwiftUI iOS |
| --- | --- | --- | --- |
| Acceso, sesión y negocio | Obligatoria | Obligatoria | Obligatoria |
| Captura/revisión MXN | Obligatoria | Obligatoria | Obligatoria |
| QR y seguimiento del cobro | Obligatoria | Obligatoria | Obligatoria |
| Vencimiento, conexión incierta y recuperación | Obligatoria | Obligatoria | Obligatoria |
| Historial, detalle y resumen día/semana/mes | Obligatoria | Obligatoria | Obligatoria |
| Accesibilidad de acciones y montos | Obligatoria | Obligatoria | Obligatoria |
| Celular y enlace | Mismo alcance de producto una vez acordado | Mismo alcance | Mismo alcance |
| iPad/tablet | Sin compromiso formal | Sin compromiso formal | Sin compromiso formal |

La paridad se define por comportamientos, datos y seguridad, no por reproducir cada pixel o componente. Un canal no se declarará listo en las dos apps porque solo se probó en una. Si hay riesgo de fecha, el equipo decidirá explícitamente qué cambia; no se degradará silenciosamente SwiftUI a una pantalla de muestra.

## 4. Contrato común y organización propuesta

Un contrato OpenAPI HTTP versionado y ejemplos JSON canónicos describirán endpoints, autenticación, `Idempotency-Key`, campos, estados, fechas, errores y paginación. No se requiere crear un SDK generado si dos adaptadores pequeños resultan más rápidos; ambos deben pasar los mismos fixtures de decodificación/serialización.

Propuesta de organización, aún sin crear proyectos:

```text
apps/
  mobile-expo/          # iOS y Android
  mobile-ios/           # SwiftUI
  landing/              # Web estática
supabase/
  migrations/
  functions/
    tappy-api/
    pey-webhook/
    payment-jobs/
    _shared/
contracts/
  openapi.yaml
  fixtures/
design-tokens/
docs/
```

No añadir herramientas complejas de monorepo solo para agrupar proyectos; el workspace TS puede cubrir Expo, funciones y web, mientras Xcode/Swift Package Manager administran el cliente nativo. La configuración exacta se fijará al iniciar desarrollo.

## 5. Diseño del cliente SwiftUI

Separar vistas, estado observable de pantalla y acceso a servidor. La UI recibe estados explícitos de carga, pendiente, verificación, confirmación e incertidumbre; no colecciones de booleanos contradictorios. La versión mínima de iOS depende de los dispositivos disponibles, antes de elegir APIs de observación concretas.

Propuesta: Swift concurrency (`async`/`await`) para red, modelos de interfaz con aislamiento adecuado al hilo principal y tareas vinculadas al ciclo de vida de pantalla. Cancelar consultas al salir o pasar a background; consultar al regresar. La cancelación local no cancela una solicitud bancaria y no permite repetir un POST ambiguo.

El SDK Swift de Supabase documenta autenticación e invocación de Edge Functions con respuestas decodificables. La elección entre SDK y un adaptador HTTP pequeño se decide por el contrato de rutas y manejo de sesión, manteniendo un único punto de acceso a datos. [Referencia del SDK Swift](https://supabase.com/docs/reference/swift/introduction), [invocación de funciones](https://supabase.com/docs/reference/swift/functions-invoke).

Persistir tokens en Keychain/almacenamiento seguro configurado explícitamente, sin asumir el comportamiento por defecto del SDK. Usar centavos enteros en el modelo y formato MXN para presentación. Las identidades de bundle deben permitir instalar Expo iOS y SwiftUI simultáneamente; los tokens se mantienen aislados salvo un diseño de sesión compartida posterior explícito.

## 6. Diseño del cliente Expo

Pantallas React Native, navegación Expo Router y consultas remotas centralizadas. Restaurar sesión y recuperar cobros desde servidor al volver de banco/background. La validación local sirve para ayudar al operador; el backend vuelve a validarlo todo.

Usar almacenamiento seguro nativo para la sesión. Generar QR desde el payload inmutable devuelto por servidor. Compartir enlaces mediante la funcionalidad del sistema y no interpretar el retorno de esa hoja como pago. No introducir un módulo nativo solo para duplicar funciones que el sistema ya ofrece.

## 7. Plan y responsables

Con cuatro personas, la distribución recomendada cambia respecto al plan de una sola app:

- A: Expo iOS/Android y revisión de contrato con backend.
- B: SwiftUI iOS y revisión de flujos iOS/accesibilidad.
- C: Supabase, pagos, RPC, webhooks y conciliación.
- D: landing, adaptación de tokens, CI/builds y coordinación de QA; respaldo de C en permisos/SQL/operación.

Los dos responsables móviles avanzan sobre el mismo contrato y fixtures desde el inicio. C y D revisan conjuntamente cambios de dinero y acceso. Todos implementan y prueban su parte; QA no queda concentrado en una persona.

Mantener el objetivo del 5-dic exige confirmar experiencia/disponibilidad de SwiftUI, Mac/Xcode, firma y mecanismo de instalación tempranos. Tener cuatro integrantes no acredita capacidad para dos apps completas si esas dependencias no están resueltas. No hay todavía estimación de horas validada.

## 8. Hitos adicionales y comparación

- Antes del 14-nov: cerrar comportamientos y contrato propuesto; registrar diseño previo y dependencias.
- Al 17-nov: ambos clientes arrancan, inician sesión y consultan el mismo entorno; builds instalables en las tres combinaciones objetivo.
- Al 21-nov: ambos recorren QR completo, con backend único y evidencia auténtica cuando se habilite acceso.
- Al 25-nov: paridad del alcance acordado de canales y reportes; resolver diferencias funcionales.
- Al 29-nov: congelar funcionalidad en ambas implementaciones.
- Del 30-nov al 2-dic: regresión por implementación/plataforma, no solo por sistema operativo.
- Al 5-dic: dos clientes identificados por versión, evidencia de paridad y materiales de evaluación.

Comparación propuesta: tiempo de implementación por flujo, defectos y mantenimiento de paridad, claridad/accesibilidad, tiempo de arranque/actualización en el mismo iPhone y condiciones de red, y esfuerzo de instalación. Compartir backend reduce variaciones, pero no vuelve idénticas todas las condiciones; registrar dispositivo, versión y conjunto de datos. No se garantiza de antemano mejor rendimiento nativo.

La comparación es una evidencia adicional del proyecto, no una función que el comerciante deba entender o elegir al cobrar. Las dos apps usan el mismo mensaje de producto.
