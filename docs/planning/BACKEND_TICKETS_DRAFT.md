# Backend Tappy — historias y tickets aprobados para publicación

Fecha: 20 de noviembre de 2026. Revisión: contrato de aceptación, calidad y evidencia antes/después por ticket. **Aprobado para publicar en GitHub por el usuario. No implementado; todas las pruebas y evidencias permanecen NOT_RUN.**

Fuente: [base de producto](../../PRODUCT_BASE.md) y [vocabulario](../../CONTEXT.md). Esta dirección sustituye las propuestas anteriores de backend administrado para el trabajo nuevo. Los documentos anteriores se conservan como antecedentes.

## Decisiones y propuesta técnica

Confirmado por el usuario: FastAPI, PostgreSQL en Docker Compose, SQLAlchemy, Pydantic, entorno virtual dentro del proyecto, routers de FastAPI, organización modular y TDD. El backend es el primer frente; mobile y landing no se implementan en estos tickets.

**Administrador identificado: Starlette Admin.** Privada Reforma usa `BaseAdmin`, `AuthProvider`, `BaseModelView`, `CustomView` y registro con `add_view`. Sus vistas invocan operaciones autorizadas; no dan CRUD libre al registro financiero. Tappy seguirá esa idea, con permisos y reglas propios. Starlette Admin presenta el login del panel y se conecta a nuestra autenticación: no reemplaza el backend de identidad ni resuelve por sí solo autenticación móvil.

Dirección de implementación del backlog aprobado: monolito modular; Alembic para migraciones; pytest con Postgres real aislado; admin interno global y operador limitado por membresía; sesiones revocables mediante token opaco inicialmente, con renovación acotada; sin registro público, recuperación por correo ni proveedor de identidad externo en esta etapa. Las políticas de duración, credencial inicial y acceso admin deben acordarse antes de B04–B08. No habrá contraseñas predeterminadas en el repo.

### Organización modular, similar en intención a Next.js

Cada dominio agrupa router, esquemas de entrada/salida, casos de uso, reglas y modelos/persistencia cuando los necesite. La estructura es explícita: FastAPI no descubre rutas automáticamente por carpetas. Una raíz ensambla los APIRouter y dependencias comunes. No habrá una carpeta global gigantesca de todos los routers, otra de todos los esquemas y otra de todos los servicios.

Organización orientativa para discutir, no scaffold creado:

```text
apps/backend/
  .venv/
  src/tappy/
    main.py
    platform/
    identity/
    merchants/
    collections/
    provider/
    evidence/
    reconciliation/
    reporting/
    backoffice/
  migrations/
  tests/
compose.yaml
contracts/
```

La ubicación final se decide al implementar B01. No se generan capas vacías por convención ni un repositorio genérico por tabla. SQLAlchemy gestiona persistencia; Pydantic valida fronteras y contratos, sin exponer automáticamente modelos ORM. Dinero en centavos enteros; fechas UTC con periodos de Ciudad de México. Secretos fuera del repo, requests y logs.

## Método de trabajo y pruebas propuestos

**Regla común:** [Protocolo de calidad por ticket](TICKET_QUALITY_PROTOCOL.md). Incluye código sin comentarios explicativos, checks Python, trazabilidad, evidencia inicial o comparativa según aplique VC01, umbral ≥97%, commit candidato, review Standards/Spec y PR para revisión humana. Todos los casos siguientes están NOT_RUN; las casillas no representan pruebas ejecutadas.

Aplicación de las skills de Matt Pocock `setup-matt-pocock-skills`, `to-tickets` y `tdd`: vocabulario común, dependencias reales y cortes verticales pequeños. Cada ticket debe poder verificarse por una operación observable. B01–B03 son habilitadores mínimos; después no se divide por «todas las tablas», «todos los servicios» o «todos los endpoints».

Fronteras de prueba del backlog aprobado:

- API HTTP pública: identidad, permisos, operaciones, errores y contratos; consultar resultado mediante API.
- Formularios y rutas del panel: login/logout, CSRF, permisos y acciones manipuladas.
- Recepción HTTP de webhooks y comandos públicos del ejecutor/conciliación, observando efectos por consultas del sistema.
- Contrato externo de pey con fixtures oficiales y simulador; pruebas reales autorizadas fuera de CI.
- Comandos operativos, migración/readiness y restauración con base desechable.

Postgres real de tests para restricciones, transacciones, concurrencia y recuperación. No sustituirlo con SQLite ni mocks de SQLAlchemy. Simular solo fronteras externas como pey y reloj; no clases/servicios propios. Nombres y resultados esperados provienen del dominio y ejemplos independientes, no del cálculo implementado.

Cada ticket lista varios escenarios pero se ejecutan **uno por uno**: escribir un test, observar Red por el comportamiento ausente, implementar el mínimo Green y repetir. El usuario solicita Red/Green/Refactor en todos los tickets: Refactor se registra como revisión posterior con suite verde, respetando la distinción de la skill TDD entre el ciclo Red/Green y la revisión. No se escriben ahora tests ni código.

Terminado exige aceptación demostrada, regresión pertinente, formato/lint/tipado, migración cuando aplique y documentación del contrato. Una prueba simulada no cierra una validación real. Sin acceso externo, ticket bloqueado; no aprobado ficticiamente.

## Historias padre

Las historias agrupan subtareas y describen un resultado; no añaden implementación extra. En GitHub se publica una issue padre por historia y sub-issues por ticket, con bloqueos nativos. El usuario autorizó esta publicación; implementar es trabajo posterior.

- **H1 — Base local verificable**: B01, B02, B03.
- **H2 — Identidad y acceso operativo**: B04, B05, B06, B07, B08.
- **H3 — Comercio y receptor autorizado**: B09, B10.
- **H4 — Solicitar y recuperar un cobro QR**: B11, B12, B13, B14, B15, B16.
- **H5 — Comprobar recepción sin duplicar dinero**: B17, B18, B19, B20, B21, B22, B23, B24, B25, B26.
- **H6 — Consultar y operar el negocio**: B27, B28, B29, B30, B31, B32.
- **H7 — Operación e integración comprobable**: B33, B34, B35.
- **H8 — Canales adicionales y contrato para clientes**: B36, B37, B38, B39, B40.

## Lista de tickets en orden de dependencias

Los IDs son locales y estables para la revisión. «Bloqueado por» indica tickets indispensables, no toda su cadena transitiva. Un contrato externo confirmado y accesos son dependencias adicionales de los canales reales.

### H1 — Base local verificable

#### B01 — Arrancar API modular y health

**Bloqueado por:** —.

**Objetivo y entrega:** Una instalación limpia arranca FastAPI desde la .venv del backend y responde health; configuración inválida falla con explicación.

- **Red:** HTTP health ausente y configuración obligatoria inválida.
- **Green:** Crear app factory, configuración tipada y primer APIRouter; preparar configuración central de herramientas Python sin comentarios/docstrings de relleno.
- **Refactor:** Separar ensamblado de app y configuración sin cambiar respuestas.

**Contrato de verificación:** [Protocolo común](TICKET_QUALITY_PROTOCOL.md). Actor: Desarrollador. Frontera: Arranque y HTTP. Dependencias anteriores completadas; datos aislados ficticios y actor autorizado salvo casos negativos. Sin ampliaciones al alcance indicado en el objetivo.

**Casos de uso**

- **B01-UC01:** Desarrollador: instalar en .venv, arrancar y consultar health cuando se cumple «Entorno limpio con variables válidas», para obtener «API inicia y health responde 200 con estado saludable».
- **B01-UC02:** Desarrollador: arrancar la API cuando se cumple «Falta una variable obligatoria», para obtener «Arranque falla con mensaje de configuración sin exponer secretos».
- **B01-UC03:** Desarrollador: consultar health de ambas cuando se cumple «Dos instancias de app en tests», para obtener «Ambas responden sin compartir estado mutable entre tests».

**Criterios de aceptación — obligatorios**

- [ ] **B01-AC01:** API inicia y health responde 200 con estado saludable. Verificación: B01-TC01.
- [ ] **B01-AC02:** Arranque falla con mensaje de configuración sin exponer secretos. Verificación: B01-TC02.
- [ ] **B01-AC03:** Ambas responden sin compartir estado mutable entre tests. Verificación: B01-TC03.

**Casos de prueba — todos NOT_RUN**

| ID / trazabilidad | Preparación y datos | Acción | Resultado esperado | Ejecución |
| --- | --- | --- | --- | --- |
| B01-TC01 → B01-UC01, B01-AC01 | Entorno limpio con variables válidas | Instalar en .venv, arrancar y consultar health | API inicia y health responde 200 con estado saludable | Automatizada |
| B01-TC02 → B01-UC02, B01-AC02 | Falta una variable obligatoria | Arrancar la API | Arranque falla con mensaje de configuración sin exponer secretos | Automatizada |
| B01-TC03 → B01-UC03, B01-AC03 | Dos instancias de app en tests | Consultar health de ambas | Ambas responden sin compartir estado mutable entre tests | Automatizada |

**Comprobación visible según aplique — B01-VC01 (obligatoria, NOT_RUN)**

- **Superficie y alcance:** API y arranque. Comparar health y error de configuración; si es el primer servicio, registrar solo resultado inicial y validarlo contra contrato, sin exigir un health anterior.
- **Escenarios:** comparar los tres TC anteriores en su interfaz observable; si un escenario no afecta UI, conservar la respuesta/salida en lugar de inventar capturas. Capturar las vistas afectadas por los TC de panel.
- **Modalidad y aplicabilidad:** nuevo → resultado inicial validado contra contrato/AC/TC, sin antes ni diff; modificación → última evidencia aprobada y resultado actual con revisiones y escenario equivalente; sin superficie relevante → No aplica justificado. Una vista sin UI no exige capturas.
- **Artefactos según modalidad:** API nueva: petición/status/JSON/contrato; panel nuevo: capturas del resultado inicial; cambio existente: antes + después + diff o capturas equivalentes; comandos: salida/código inicial o comparado. Completar la [plantilla comparativa](EVIDENCE_COMPARISON_TEMPLATE.md), vinculada a B01-UC01–UC03 y AC01–AC03.
- **Aprobación:** resultado inicial conforme al contrato o diferencias esperadas justificadas y probadas; sin regresiones pendientes. VC01 exige declarar aplicabilidad; No aplica requiere justificación revisada. Es una condición de proceso independiente del porcentaje de AC, sin inflar su denominador. No sustituye tests ni autoriza actualizar la base automáticamente.

**Verificación y salida:** registrar evidencia real UC → AC → TC para la revisión exacta; ejecutar checks y regresión del protocolo; exigir VC01 según su modalidad/aplicabilidad, los tres AC y tests aplicables aprobados y completitud ≥97% sin redondeo. Con 3 AC obligatorios se requiere 3/3. Después: commit candidato → review Standards/Spec → corrección y nueva verificación hasta aprobación → PR para human review. Código simple, tipado y sin comentarios explicativos. No abrir PR ni cerrar B01 solo por tener casillas marcadas.

#### B02 — Levantar Postgres y aplicar primera migración

**Bloqueado por:** B01.

**Objetivo y entrega:** Compose levanta Postgres con volumen y healthcheck; migraciones funcionan desde base vacía y readiness detecta caída de DB.

- **Red:** Readiness con DB caída y migración sobre base vacía fallan.
- **Green:** Conectar SQLAlchemy, migraciones Alembic y DB de test aislada.
- **Refactor:** Centralizar ciclo de sesión/transacción sin compartir sesiones entre peticiones.

**Contrato de verificación:** [Protocolo común](TICKET_QUALITY_PROTOCOL.md). Actor: Desarrollador. Frontera: Migraciones y HTTP readiness. Dependencias anteriores completadas; datos aislados ficticios y actor autorizado salvo casos negativos. Sin ampliaciones al alcance indicado en el objetivo.

**Casos de uso**

- **B02-UC01:** Desarrollador: aplicar migraciones y consultar readiness cuando se cumple «Postgres vacío desechable en Compose», para obtener «Migraciones terminan y readiness responde 200».
- **B02-UC02:** Desarrollador: consultar readiness cuando se cumple «Postgres detenido», para obtener «Respuesta 503 sin credenciales ni excepción interna».
- **B02-UC03:** Desarrollador: reiniciar servicio y consultar por interfaz operativa cuando se cumple «Dato ficticio persistido en volumen local», para obtener «Dato permanece; DB de tests sigue aislada de DB local».

**Criterios de aceptación — obligatorios**

- [ ] **B02-AC01:** Migraciones terminan y readiness responde 200. Verificación: B02-TC01.
- [ ] **B02-AC02:** Respuesta 503 sin credenciales ni excepción interna. Verificación: B02-TC02.
- [ ] **B02-AC03:** Dato permanece; DB de tests sigue aislada de DB local. Verificación: B02-TC03.

**Casos de prueba — todos NOT_RUN**

| ID / trazabilidad | Preparación y datos | Acción | Resultado esperado | Ejecución |
| --- | --- | --- | --- | --- |
| B02-TC01 → B02-UC01, B02-AC01 | Postgres vacío desechable en Compose | Aplicar migraciones y consultar readiness | Migraciones terminan y readiness responde 200 | Automatizada |
| B02-TC02 → B02-UC02, B02-AC02 | Postgres detenido | Consultar readiness | Respuesta 503 sin credenciales ni excepción interna | Automatizada |
| B02-TC03 → B02-UC03, B02-AC03 | Dato ficticio persistido en volumen local | Reiniciar servicio y consultar por interfaz operativa | Dato permanece; DB de tests sigue aislada de DB local | Automatizada |

**Comprobación visible según aplique — B02-VC01 (obligatoria, NOT_RUN)**

- **Superficie y alcance:** Comandos y API. Comparar migración/readiness con DB disponible y caída, más salida de reinicio y comprobación de persistencia; conservar códigos de salida.
- **Escenarios:** comparar los tres TC anteriores en su interfaz observable; si un escenario no afecta UI, conservar la respuesta/salida en lugar de inventar capturas. Capturar las vistas afectadas por los TC de panel.
- **Modalidad y aplicabilidad:** nuevo → resultado inicial validado contra contrato/AC/TC, sin antes ni diff; modificación → última evidencia aprobada y resultado actual con revisiones y escenario equivalente; sin superficie relevante → No aplica justificado. Una vista sin UI no exige capturas.
- **Artefactos según modalidad:** API nueva: petición/status/JSON/contrato; panel nuevo: capturas del resultado inicial; cambio existente: antes + después + diff o capturas equivalentes; comandos: salida/código inicial o comparado. Completar la [plantilla comparativa](EVIDENCE_COMPARISON_TEMPLATE.md), vinculada a B02-UC01–UC03 y AC01–AC03.
- **Aprobación:** resultado inicial conforme al contrato o diferencias esperadas justificadas y probadas; sin regresiones pendientes. VC01 exige declarar aplicabilidad; No aplica requiere justificación revisada. Es una condición de proceso independiente del porcentaje de AC, sin inflar su denominador. No sustituye tests ni autoriza actualizar la base automáticamente.

**Verificación y salida:** registrar evidencia real UC → AC → TC para la revisión exacta; ejecutar checks y regresión del protocolo; exigir VC01 según su modalidad/aplicabilidad, los tres AC y tests aplicables aprobados y completitud ≥97% sin redondeo. Con 3 AC obligatorios se requiere 3/3. Después: commit candidato → review Standards/Spec → corrección y nueva verificación hasta aprobación → PR para human review. Código simple, tipado y sin comentarios explicativos. No abrir PR ni cerrar B02 solo por tener casillas marcadas.

#### B03 — Ejecutar checks y pruebas en CI

**Bloqueado por:** B02.

**Objetivo y entrega:** CI reproduce instalación, migraciones y pruebas con Postgres; no usa credenciales ni banco real.

- **Red:** Un test deliberadamente fallido hace fallar el job; después se retira esa modificación temporal.
- **Green:** Automatizar comando único local/CI con Ruff format/check, mypy estricto, pytest/Postgres, migraciones, higiene sin comentarios y reportes reproducibles; ejecutar el protocolo común por ticket.
- **Refactor:** Simplificar comandos compartidos local/CI manteniendo los controles.

Al implementar B03, incorporar al runner el registro de evidencia UC/AC/TC, la fórmula de completitud y las condiciones obligatorias del protocolo; impedir una salida satisfactoria si faltan criterios obligatorios o evidencia requerida. Preparar artefactos API antes/después/diff con base aprobada, normalización explícita y sin sobrescritura automática; las capturas del panel se incorporan al implementar sus vistas.

**Contrato de verificación:** [Protocolo común](TICKET_QUALITY_PROTOCOL.md). Actor: Contribuidor. Frontera: Comando de checks y CI. Dependencias anteriores completadas; datos aislados ficticios y actor autorizado salvo casos negativos. Sin ampliaciones al alcance indicado en el objetivo.

**Casos de uso**

- **B03-UC01:** Contribuidor: ejecutar batería local y CI cuando se cumple «Checkout limpio con Postgres de tests», para obtener «Formato, lint, tipado, migraciones y tests terminan con salida cero».
- **B03-UC02:** Contribuidor: ejecutar batería cuando se cumple «Cambio temporal que rompe test, tipo o lint, uno por vez», para obtener «Cada infracción provoca salida no cero; ningún fallo se ignora».
- **B03-UC03:** Contribuidor: ejecutar control de higiene por separado cuando se cumple «Archivo propio con comentario explicativo y cadena que contiene #», para obtener «Comentario se señala; cadena válida no se confunde con comentario».

**Criterios de aceptación — obligatorios**

- [ ] **B03-AC01:** Formato, lint, tipado, migraciones y tests terminan con salida cero. Verificación: B03-TC01.
- [ ] **B03-AC02:** Cada infracción provoca salida no cero; ningún fallo se ignora. Verificación: B03-TC02.
- [ ] **B03-AC03:** Comentario se señala; cadena válida no se confunde con comentario. Verificación: B03-TC03.

**Casos de prueba — todos NOT_RUN**

| ID / trazabilidad | Preparación y datos | Acción | Resultado esperado | Ejecución |
| --- | --- | --- | --- | --- |
| B03-TC01 → B03-UC01, B03-AC01 | Checkout limpio con Postgres de tests | Ejecutar batería local y CI | Formato, lint, tipado, migraciones y tests terminan con salida cero | Comando local/CI con modificación temporal controlada |
| B03-TC02 → B03-UC02, B03-AC02 | Cambio temporal que rompe test, tipo o lint, uno por vez | Ejecutar batería | Cada infracción provoca salida no cero; ningún fallo se ignora | Comando local/CI con modificación temporal controlada |
| B03-TC03 → B03-UC03, B03-AC03 | Archivo propio con comentario explicativo y cadena que contiene # | Ejecutar control de higiene por separado | Comentario se señala; cadena válida no se confunde con comentario | Comando local/CI con modificación temporal controlada |

**Comprobación visible según aplique — B03-VC01 (obligatoria, NOT_RUN)**

- **Superficie y alcance:** CI y reportes. Comparar ejecución anterior/actual del comando de calidad, fallos deliberados controlados y reportes de diferencias; demostrar que un cambio inesperado se señala sin actualizar la base automáticamente.
- **Escenarios:** comparar los tres TC anteriores en su interfaz observable; si un escenario no afecta UI, conservar la respuesta/salida en lugar de inventar capturas. Capturar las vistas afectadas por los TC de panel.
- **Modalidad y aplicabilidad:** nuevo → resultado inicial validado contra contrato/AC/TC, sin antes ni diff; modificación → última evidencia aprobada y resultado actual con revisiones y escenario equivalente; sin superficie relevante → No aplica justificado. Una vista sin UI no exige capturas.
- **Artefactos según modalidad:** API nueva: petición/status/JSON/contrato; panel nuevo: capturas del resultado inicial; cambio existente: antes + después + diff o capturas equivalentes; comandos: salida/código inicial o comparado. Completar la [plantilla comparativa](EVIDENCE_COMPARISON_TEMPLATE.md), vinculada a B03-UC01–UC03 y AC01–AC03.
- **Aprobación:** resultado inicial conforme al contrato o diferencias esperadas justificadas y probadas; sin regresiones pendientes. VC01 exige declarar aplicabilidad; No aplica requiere justificación revisada. Es una condición de proceso independiente del porcentaje de AC, sin inflar su denominador. No sustituye tests ni autoriza actualizar la base automáticamente.

**Verificación y salida:** registrar evidencia real UC → AC → TC para la revisión exacta; ejecutar checks y regresión del protocolo; exigir VC01 según su modalidad/aplicabilidad, los tres AC y tests aplicables aprobados y completitud ≥97% sin redondeo. Con 3 AC obligatorios se requiere 3/3. Después: commit candidato → review Standards/Spec → corrección y nueva verificación hasta aprobación → PR para human review. Código simple, tipado y sin comentarios explicativos. No abrir PR ni cerrar B03 solo por tener casillas marcadas.

### H2 — Identidad y acceso operativo

#### B04 — Provisionar el primer administrador

**Bloqueado por:** B02.

**Objetivo y entrega:** Comando operativo crea admin sin contraseña fija ni registro público y permite verificar referencia/rol/estado; repetir no duplica identidad. El login se implementa en B05.

- **Red:** Credenciales inválidas y ejecución repetida no crean cuentas extra.
- **Green:** Persistir usuario activo y hash de contraseña; bootstrap idempotente.
- **Refactor:** Encapsular provisionamiento y hashing fuera de routers.

**Contrato de verificación:** [Protocolo común](TICKET_QUALITY_PROTOCOL.md). Actor: Responsable operativo. Frontera: Comando de bootstrap. Dependencias anteriores completadas; datos aislados ficticios y actor autorizado salvo casos negativos. Sin ampliaciones al alcance indicado en el objetivo.

**Casos de uso**

- **B04-UC01:** Responsable operativo: provisionar admin y autenticarlo cuando se cumple «Correo ficticio y secreto recibido por canal operativo», para obtener «Comando permite recuperar referencia/rol/estado del admin activo; salida no expone secreto».
- **B04-UC02:** Responsable operativo: ejecutar bootstrap cuando se cumple «Entrada vacía o inválida», para obtener «Falla sin crear identidad utilizable ni imprimir contraseña».
- **B04-UC03:** Responsable operativo: repetir comando y consultar identidad cuando se cumple «Mismo correo ya provisionado», para obtener «No duplica ni cambia contraseña/rol silenciosamente».

**Criterios de aceptación — obligatorios**

- [ ] **B04-AC01:** Comando permite recuperar referencia/rol/estado del admin activo; salida no expone secreto. Verificación: B04-TC01.
- [ ] **B04-AC02:** Falla sin crear identidad utilizable ni imprimir contraseña. Verificación: B04-TC02.
- [ ] **B04-AC03:** No duplica ni cambia contraseña/rol silenciosamente. Verificación: B04-TC03.

**Casos de prueba — todos NOT_RUN**

| ID / trazabilidad | Preparación y datos | Acción | Resultado esperado | Ejecución |
| --- | --- | --- | --- | --- |
| B04-TC01 → B04-UC01, B04-AC01 | Correo ficticio y secreto recibido por canal operativo | Provisionar admin y consultar resultado del comando | Comando permite recuperar referencia/rol/estado del admin activo; salida no expone secreto | Automatizada |
| B04-TC02 → B04-UC02, B04-AC02 | Entrada vacía o inválida | Ejecutar bootstrap | Falla sin crear identidad utilizable ni imprimir contraseña | Automatizada |
| B04-TC03 → B04-UC03, B04-AC03 | Mismo correo ya provisionado | Repetir comando y consultar identidad | No duplica ni cambia contraseña/rol silenciosamente | Automatizada |

**Comprobación visible según aplique — B04-VC01 (obligatoria, NOT_RUN)**

- **Superficie y alcance:** Comando operativo. Comparar alta inicial, entrada inválida y repetición del bootstrap mediante salida sanitizada, código de salida y referencia/rol/estado recuperables; nunca mostrar contraseña.
- **Escenarios:** comparar los tres TC anteriores en su interfaz observable; si un escenario no afecta UI, conservar la respuesta/salida en lugar de inventar capturas. Capturar las vistas afectadas por los TC de panel.
- **Modalidad y aplicabilidad:** nuevo → resultado inicial validado contra contrato/AC/TC, sin antes ni diff; modificación → última evidencia aprobada y resultado actual con revisiones y escenario equivalente; sin superficie relevante → No aplica justificado. Una vista sin UI no exige capturas.
- **Artefactos según modalidad:** API nueva: petición/status/JSON/contrato; panel nuevo: capturas del resultado inicial; cambio existente: antes + después + diff o capturas equivalentes; comandos: salida/código inicial o comparado. Completar la [plantilla comparativa](EVIDENCE_COMPARISON_TEMPLATE.md), vinculada a B04-UC01–UC03 y AC01–AC03.
- **Aprobación:** resultado inicial conforme al contrato o diferencias esperadas justificadas y probadas; sin regresiones pendientes. VC01 exige declarar aplicabilidad; No aplica requiere justificación revisada. Es una condición de proceso independiente del porcentaje de AC, sin inflar su denominador. No sustituye tests ni autoriza actualizar la base automáticamente.

**Verificación y salida:** registrar evidencia real UC → AC → TC para la revisión exacta; ejecutar checks y regresión del protocolo; exigir VC01 según su modalidad/aplicabilidad, los tres AC y tests aplicables aprobados y completitud ≥97% sin redondeo. Con 3 AC obligatorios se requiere 3/3. Después: commit candidato → review Standards/Spec → corrección y nueva verificación hasta aprobación → PR para human review. Código simple, tipado y sin comentarios explicativos. No abrir PR ni cerrar B04 solo por tener casillas marcadas.

#### B05 — Iniciar sesión y consultar identidad

**Bloqueado por:** B04.

**Objetivo y entrega:** Admin u operador activo inicia sesión y consulta su identidad; credenciales inválidas devuelven error genérico.

- **Red:** Login inválido/inactivo y consulta sin sesión son rechazados.
- **Green:** Autenticación propia y credencial de sesión revocable, propuesta inicial de token opaco; DTOs Pydantic sin secretos.
- **Refactor:** Unificar dependencia de identidad sin acoplarla al panel.

**Contrato de verificación:** [Protocolo común](TICKET_QUALITY_PROTOCOL.md). Actor: Operador activo. Frontera: HTTP identidad. Dependencias anteriores completadas; datos aislados ficticios y actor autorizado salvo casos negativos. Sin ampliaciones al alcance indicado en el objetivo.

**Casos de uso**

- **B05-UC01:** Operador activo: iniciar sesión y consultar identidad con credencial obtenida cuando se cumple «Cuenta activa de prueba», para obtener «200 con identidad correcta sin hash ni credenciales en DTO».
- **B05-UC02:** Operador activo: intentar login cuando se cumple «Usuario inactivo o contraseña incorrecta», para obtener «Error genérico equivalente, sin sesión utilizable».
- **B05-UC03:** Operador activo: consultar identidad en cada caso cuando se cumple «Sin token, token alterado y token ajeno», para obtener «Sin token/alterado reciben 401; token válido ajeno solo muestra su propia identidad».

**Criterios de aceptación — obligatorios**

- [ ] **B05-AC01:** 200 con identidad correcta sin hash ni credenciales en DTO. Verificación: B05-TC01.
- [ ] **B05-AC02:** Error genérico equivalente, sin sesión utilizable. Verificación: B05-TC02.
- [ ] **B05-AC03:** Sin token/alterado reciben 401; token válido ajeno solo muestra su propia identidad. Verificación: B05-TC03.

**Casos de prueba — todos NOT_RUN**

| ID / trazabilidad | Preparación y datos | Acción | Resultado esperado | Ejecución |
| --- | --- | --- | --- | --- |
| B05-TC01 → B05-UC01, B05-AC01 | Cuenta activa de prueba | Iniciar sesión y consultar identidad con credencial obtenida | 200 con identidad correcta sin hash ni credenciales en DTO | Automatizada |
| B05-TC02 → B05-UC02, B05-AC02 | Usuario inactivo o contraseña incorrecta | Intentar login | Error genérico equivalente, sin sesión utilizable | Automatizada |
| B05-TC03 → B05-UC03, B05-AC03 | Sin token, token alterado y token ajeno | Consultar identidad en cada caso | Sin token/alterado reciben 401; token válido ajeno solo muestra su propia identidad | Automatizada |

**Comprobación visible según aplique — B05-VC01 (obligatoria, NOT_RUN)**

- **Superficie y alcance:** API identidad. Comparar login y consulta de identidad válida/inválida: status y DTO; redactar credencial en ambos resultados y verificar su uso mediante identidad posterior.
- **Escenarios:** comparar los tres TC anteriores en su interfaz observable; si un escenario no afecta UI, conservar la respuesta/salida en lugar de inventar capturas. Capturar las vistas afectadas por los TC de panel.
- **Modalidad y aplicabilidad:** nuevo → resultado inicial validado contra contrato/AC/TC, sin antes ni diff; modificación → última evidencia aprobada y resultado actual con revisiones y escenario equivalente; sin superficie relevante → No aplica justificado. Una vista sin UI no exige capturas.
- **Artefactos según modalidad:** API nueva: petición/status/JSON/contrato; panel nuevo: capturas del resultado inicial; cambio existente: antes + después + diff o capturas equivalentes; comandos: salida/código inicial o comparado. Completar la [plantilla comparativa](EVIDENCE_COMPARISON_TEMPLATE.md), vinculada a B05-UC01–UC03 y AC01–AC03.
- **Aprobación:** resultado inicial conforme al contrato o diferencias esperadas justificadas y probadas; sin regresiones pendientes. VC01 exige declarar aplicabilidad; No aplica requiere justificación revisada. Es una condición de proceso independiente del porcentaje de AC, sin inflar su denominador. No sustituye tests ni autoriza actualizar la base automáticamente.

**Verificación y salida:** registrar evidencia real UC → AC → TC para la revisión exacta; ejecutar checks y regresión del protocolo; exigir VC01 según su modalidad/aplicabilidad, los tres AC y tests aplicables aprobados y completitud ≥97% sin redondeo. Con 3 AC obligatorios se requiere 3/3. Después: commit candidato → review Standards/Spec → corrección y nueva verificación hasta aprobación → PR para human review. Código simple, tipado y sin comentarios explicativos. No abrir PR ni cerrar B05 solo por tener casillas marcadas.

#### B06 — Expirar, renovar y revocar sesiones

**Bloqueado por:** B05.

**Objetivo y entrega:** Cerrar sesión o desactivar usuario quita acceso; renovación mantiene duración acotada y no revive una sesión revocada.

- **Red:** Token expirado/revocado y renovación repetida fallan; logout impide consultar identidad.
- **Green:** Persistir expiración/revocación y renovar con rotación atómica.
- **Refactor:** Concentrar política de sesión y reloj sustituible en tests.

**Contrato de verificación:** [Protocolo común](TICKET_QUALITY_PROTOCOL.md). Actor: Operador autenticado. Frontera: HTTP sesiones. Dependencias anteriores completadas; datos aislados ficticios y actor autorizado salvo casos negativos. Sin ampliaciones al alcance indicado en el objetivo.

**Casos de uso**

- **B06-UC01:** Operador autenticado: renovar y consultar con nueva credencial cuando se cumple «Sesión válida dentro de duración acordada», para obtener «Nueva sesión funciona y la anterior deja de autorizar».
- **B06-UC02:** Operador autenticado: renovar y consultar identidad cuando se cumple «Sesión expirada o revocada», para obtener «No se revive; acceso rechazado».
- **B06-UC03:** Operador autenticado: cerrar sesión o desactivar y volver a consultar cuando se cumple «Sesión activa y usuario posteriormente desactivado», para obtener «Ninguna credencial afectada conserva acceso».

**Criterios de aceptación — obligatorios**

- [ ] **B06-AC01:** Nueva sesión funciona y la anterior deja de autorizar. Verificación: B06-TC01.
- [ ] **B06-AC02:** No se revive; acceso rechazado. Verificación: B06-TC02.
- [ ] **B06-AC03:** Ninguna credencial afectada conserva acceso. Verificación: B06-TC03.

**Casos de prueba — todos NOT_RUN**

| ID / trazabilidad | Preparación y datos | Acción | Resultado esperado | Ejecución |
| --- | --- | --- | --- | --- |
| B06-TC01 → B06-UC01, B06-AC01 | Sesión válida dentro de duración acordada | Renovar y consultar con nueva credencial | Nueva sesión funciona y la anterior deja de autorizar | Automatizada |
| B06-TC02 → B06-UC02, B06-AC02 | Sesión expirada o revocada | Renovar y consultar identidad | No se revive; acceso rechazado | Automatizada |
| B06-TC03 → B06-UC03, B06-AC03 | Sesión activa y usuario posteriormente desactivado | Cerrar sesión o desactivar y volver a consultar | Ninguna credencial afectada conserva acceso | Automatizada |

**Comprobación visible según aplique — B06-VC01 (obligatoria, NOT_RUN)**

- **Superficie y alcance:** API sesiones. Comparar respuestas de renovación, logout y acceso con sesión expirada/revocada, antes/después; redactar tokens y conservar los cambios de autorización observables.
- **Escenarios:** comparar los tres TC anteriores en su interfaz observable; si un escenario no afecta UI, conservar la respuesta/salida en lugar de inventar capturas. Capturar las vistas afectadas por los TC de panel.
- **Modalidad y aplicabilidad:** nuevo → resultado inicial validado contra contrato/AC/TC, sin antes ni diff; modificación → última evidencia aprobada y resultado actual con revisiones y escenario equivalente; sin superficie relevante → No aplica justificado. Una vista sin UI no exige capturas.
- **Artefactos según modalidad:** API nueva: petición/status/JSON/contrato; panel nuevo: capturas del resultado inicial; cambio existente: antes + después + diff o capturas equivalentes; comandos: salida/código inicial o comparado. Completar la [plantilla comparativa](EVIDENCE_COMPARISON_TEMPLATE.md), vinculada a B06-UC01–UC03 y AC01–AC03.
- **Aprobación:** resultado inicial conforme al contrato o diferencias esperadas justificadas y probadas; sin regresiones pendientes. VC01 exige declarar aplicabilidad; No aplica requiere justificación revisada. Es una condición de proceso independiente del porcentaje de AC, sin inflar su denominador. No sustituye tests ni autoriza actualizar la base automáticamente.

**Verificación y salida:** registrar evidencia real UC → AC → TC para la revisión exacta; ejecutar checks y regresión del protocolo; exigir VC01 según su modalidad/aplicabilidad, los tres AC y tests aplicables aprobados y completitud ≥97% sin redondeo. Con 3 AC obligatorios se requiere 3/3. Después: commit candidato → review Standards/Spec → corrección y nueva verificación hasta aprobación → PR para human review. Código simple, tipado y sin comentarios explicativos. No abrir PR ni cerrar B06 solo por tener casillas marcadas.

#### B07 — Entrar y salir de Starlette Admin

**Bloqueado por:** B06.

**Objetivo y entrega:** Panel exige admin activo, usa identidad real, logout revoca sesión; operador y anónimo no acceden.

- **Red:** Acceso anónimo/operador, sesión revocada y formulario con CSRF inválido son rechazados.
- **Green:** AuthProvider, sesión de navegador protegida, CSRF en mutaciones y configuración de cookies por entorno.
- **Refactor:** Compartir autenticación con API y conservar presentación específica del panel.

**Contrato de verificación:** [Protocolo común](TICKET_QUALITY_PROTOCOL.md). Actor: Administrador interno. Frontera: HTTP/formulario admin. Dependencias anteriores completadas; datos aislados ficticios y actor autorizado salvo casos negativos. Sin ampliaciones al alcance indicado en el objetivo.

**Casos de uso**

- **B07-UC01:** Administrador interno: login, consulta panel y logout cuando se cumple «Admin activo en navegador de prueba», para obtener «Acceso permitido y salida revoca acceso posterior».
- **B07-UC02:** Administrador interno: abrir panel y rutas internas cuando se cumple «Anónimo u operador sin rol admin», para obtener «Sin acceso a datos administrativos».
- **B07-UC03:** Administrador interno: enviar mutación y consultar resultado cuando se cumple «Admin con sesión válida y formulario sin CSRF válido», para obtener «Mutación rechazada sin cambios; cookie protegida según entorno».

**Criterios de aceptación — obligatorios**

- [ ] **B07-AC01:** Acceso permitido y salida revoca acceso posterior. Verificación: B07-TC01.
- [ ] **B07-AC02:** Sin acceso a datos administrativos. Verificación: B07-TC02.
- [ ] **B07-AC03:** Mutación rechazada sin cambios; cookie protegida según entorno. Verificación: B07-TC03.

**Casos de prueba — todos NOT_RUN**

| ID / trazabilidad | Preparación y datos | Acción | Resultado esperado | Ejecución |
| --- | --- | --- | --- | --- |
| B07-TC01 → B07-UC01, B07-AC01 | Admin activo en navegador de prueba | Login, consulta panel y logout | Acceso permitido y salida revoca acceso posterior | Automatizada |
| B07-TC02 → B07-UC02, B07-AC02 | Anónimo u operador sin rol admin | Abrir panel y rutas internas | Sin acceso a datos administrativos | Automatizada |
| B07-TC03 → B07-UC03, B07-AC03 | Admin con sesión válida y formulario sin CSRF válido | Enviar mutación y consultar resultado | Mutación rechazada sin cambios; cookie protegida según entorno | Automatizada |

**Comprobación visible según aplique — B07-VC01 (obligatoria, NOT_RUN)**

- **Superficie y alcance:** API y panel. Comparar login, acceso al panel y logout con capturas equivalentes de admin/operador/anónimo; añadir respuestas de sesión y rechazo CSRF, sin cookies ni credenciales en artefactos.
- **Escenarios:** comparar los tres TC anteriores en su interfaz observable; si un escenario no afecta UI, conservar la respuesta/salida en lugar de inventar capturas. Capturar las vistas afectadas por los TC de panel.
- **Modalidad y aplicabilidad:** nuevo → resultado inicial validado contra contrato/AC/TC, sin antes ni diff; modificación → última evidencia aprobada y resultado actual con revisiones y escenario equivalente; sin superficie relevante → No aplica justificado. Una vista sin UI no exige capturas.
- **Artefactos según modalidad:** API nueva: petición/status/JSON/contrato; panel nuevo: capturas del resultado inicial; cambio existente: antes + después + diff o capturas equivalentes; comandos: salida/código inicial o comparado. Completar la [plantilla comparativa](EVIDENCE_COMPARISON_TEMPLATE.md), vinculada a B07-UC01–UC03 y AC01–AC03.
- **Aprobación:** resultado inicial conforme al contrato o diferencias esperadas justificadas y probadas; sin regresiones pendientes. VC01 exige declarar aplicabilidad; No aplica requiere justificación revisada. Es una condición de proceso independiente del porcentaje de AC, sin inflar su denominador. No sustituye tests ni autoriza actualizar la base automáticamente.

**Verificación y salida:** registrar evidencia real UC → AC → TC para la revisión exacta; ejecutar checks y regresión del protocolo; exigir VC01 según su modalidad/aplicabilidad, los tres AC y tests aplicables aprobados y completitud ≥97% sin redondeo. Con 3 AC obligatorios se requiere 3/3. Después: commit candidato → review Standards/Spec → corrección y nueva verificación hasta aprobación → PR para human review. Código simple, tipado y sin comentarios explicativos. No abrir PR ni cerrar B07 solo por tener casillas marcadas.

#### B08 — Administrar operadores autorizados

**Bloqueado por:** B07.

**Objetivo y entrega:** Admin crea/desactiva operadores desde formulario y consulta resultado; no existe signup público.

- **Red:** Anónimo/operador no crean usuarios; correo repetido y sesión de desactivado se rechazan.
- **Green:** API y vista admin de alta/desactivación con credencial inicial operativa segura, sin email automático.
- **Refactor:** Reusar validación y permisos en API/panel; retirar CRUD genérico.

**Contrato de verificación:** [Protocolo común](TICKET_QUALITY_PROTOCOL.md). Actor: Administrador interno. Frontera: HTTP/formulario operadores. Dependencias anteriores completadas; datos aislados ficticios y actor autorizado salvo casos negativos. Sin ampliaciones al alcance indicado en el objetivo.

**Casos de uso**

- **B08-UC01:** Administrador interno: crear operador y consultar su estado cuando se cumple «Admin autenticado y correo nuevo ficticio», para obtener «Operador activo recuperable; respuesta sin secreto».
- **B08-UC02:** Administrador interno: intentar alta/desactivación cuando se cumple «Operador común o anónimo», para obtener «403 o 401 sin modificación».
- **B08-UC03:** Administrador interno: repetir alta, después desactivar y consultar identidad del operador cuando se cumple «Correo ya registrado y operador con sesión activa», para obtener «Sin duplicado; sesión del desactivado deja de autorizar».

**Criterios de aceptación — obligatorios**

- [ ] **B08-AC01:** Operador activo recuperable; respuesta sin secreto. Verificación: B08-TC01.
- [ ] **B08-AC02:** 403 o 401 sin modificación. Verificación: B08-TC02.
- [ ] **B08-AC03:** Sin duplicado; sesión del desactivado deja de autorizar. Verificación: B08-TC03.

**Casos de prueba — todos NOT_RUN**

| ID / trazabilidad | Preparación y datos | Acción | Resultado esperado | Ejecución |
| --- | --- | --- | --- | --- |
| B08-TC01 → B08-UC01, B08-AC01 | Admin autenticado y correo nuevo ficticio | Crear operador y consultar su estado | Operador activo recuperable; respuesta sin secreto | Automatizada |
| B08-TC02 → B08-UC02, B08-AC02 | Operador común o anónimo | Intentar alta/desactivación | 403 o 401 sin modificación | Automatizada |
| B08-TC03 → B08-UC03, B08-AC03 | Correo ya registrado y operador con sesión activa | Repetir alta, después desactivar y consultar identidad del operador | Sin duplicado; sesión del desactivado deja de autorizar | Automatizada |

**Comprobación visible según aplique — B08-VC01 (obligatoria, NOT_RUN)**

- **Superficie y alcance:** API y panel. Comparar formulario/listado de operadores, error de correo repetido y resultado de desactivación; adjuntar DTO anterior/actual y lectura de sesión revocada.
- **Escenarios:** comparar los tres TC anteriores en su interfaz observable; si un escenario no afecta UI, conservar la respuesta/salida en lugar de inventar capturas. Capturar las vistas afectadas por los TC de panel.
- **Modalidad y aplicabilidad:** nuevo → resultado inicial validado contra contrato/AC/TC, sin antes ni diff; modificación → última evidencia aprobada y resultado actual con revisiones y escenario equivalente; sin superficie relevante → No aplica justificado. Una vista sin UI no exige capturas.
- **Artefactos según modalidad:** API nueva: petición/status/JSON/contrato; panel nuevo: capturas del resultado inicial; cambio existente: antes + después + diff o capturas equivalentes; comandos: salida/código inicial o comparado. Completar la [plantilla comparativa](EVIDENCE_COMPARISON_TEMPLATE.md), vinculada a B08-UC01–UC03 y AC01–AC03.
- **Aprobación:** resultado inicial conforme al contrato o diferencias esperadas justificadas y probadas; sin regresiones pendientes. VC01 exige declarar aplicabilidad; No aplica requiere justificación revisada. Es una condición de proceso independiente del porcentaje de AC, sin inflar su denominador. No sustituye tests ni autoriza actualizar la base automáticamente.

**Verificación y salida:** registrar evidencia real UC → AC → TC para la revisión exacta; ejecutar checks y regresión del protocolo; exigir VC01 según su modalidad/aplicabilidad, los tres AC y tests aplicables aprobados y completitud ≥97% sin redondeo. Con 3 AC obligatorios se requiere 3/3. Después: commit candidato → review Standards/Spec → corrección y nueva verificación hasta aprobación → PR para human review. Código simple, tipado y sin comentarios explicativos. No abrir PR ni cerrar B08 solo por tener casillas marcadas.

### H3 — Comercio y receptor autorizado

#### B09 — Configurar comercio y membresía

**Bloqueado por:** B08.

**Objetivo y entrega:** Admin da de alta comercio demo y asigna operador; este consulta solo su comercio.

- **Red:** Operador A no lee ni modifica B aunque cambie IDs; membresía duplicada no se repite.
- **Green:** API y formulario admin de comercio/membresía, con aislamiento por comercio.
- **Refactor:** Centralizar autorización por pertenencia y consultas acotadas.

**Contrato de verificación:** [Protocolo común](TICKET_QUALITY_PROTOCOL.md). Actor: Administrador y operador. Frontera: HTTP/formulario comercios. Dependencias anteriores completadas; datos aislados ficticios y actor autorizado salvo casos negativos. Sin ampliaciones al alcance indicado en el objetivo.

**Casos de uso**

- **B09-UC01:** Administrador y operador: crear/asignar membresía y consultar como A cuando se cumple «Admin, comercio A y operador A ficticios», para obtener «Solo aparece comercio autorizado y membresía una vez».
- **B09-UC02:** Administrador y operador: manipular IDs para consultar o modificar B cuando se cumple «Operador A y comercio B ajeno», para obtener «No obtiene ni modifica datos de B».
- **B09-UC03:** Administrador y operador: repetir asignación y consultar listado cuando se cumple «Membresía A existente», para obtener «No hay duplicados ni pérdida del vínculo original».

**Criterios de aceptación — obligatorios**

- [ ] **B09-AC01:** Solo aparece comercio autorizado y membresía una vez. Verificación: B09-TC01.
- [ ] **B09-AC02:** No obtiene ni modifica datos de B. Verificación: B09-TC02.
- [ ] **B09-AC03:** No hay duplicados ni pérdida del vínculo original. Verificación: B09-TC03.

**Casos de prueba — todos NOT_RUN**

| ID / trazabilidad | Preparación y datos | Acción | Resultado esperado | Ejecución |
| --- | --- | --- | --- | --- |
| B09-TC01 → B09-UC01, B09-AC01 | Admin, comercio A y operador A ficticios | Crear/asignar membresía y consultar como A | Solo aparece comercio autorizado y membresía una vez | Automatizada |
| B09-TC02 → B09-UC02, B09-AC02 | Operador A y comercio B ajeno | Manipular IDs para consultar o modificar B | No obtiene ni modifica datos de B | Automatizada |
| B09-TC03 → B09-UC03, B09-AC03 | Membresía A existente | Repetir asignación y consultar listado | No hay duplicados ni pérdida del vínculo original | Automatizada |

**Comprobación visible según aplique — B09-VC01 (obligatoria, NOT_RUN)**

- **Superficie y alcance:** API y panel. Comparar comercio, formulario/membresía y consulta como A; mostrar también respuestas de intento de acceso a B sin publicar datos ajenos.
- **Escenarios:** comparar los tres TC anteriores en su interfaz observable; si un escenario no afecta UI, conservar la respuesta/salida en lugar de inventar capturas. Capturar las vistas afectadas por los TC de panel.
- **Modalidad y aplicabilidad:** nuevo → resultado inicial validado contra contrato/AC/TC, sin antes ni diff; modificación → última evidencia aprobada y resultado actual con revisiones y escenario equivalente; sin superficie relevante → No aplica justificado. Una vista sin UI no exige capturas.
- **Artefactos según modalidad:** API nueva: petición/status/JSON/contrato; panel nuevo: capturas del resultado inicial; cambio existente: antes + después + diff o capturas equivalentes; comandos: salida/código inicial o comparado. Completar la [plantilla comparativa](EVIDENCE_COMPARISON_TEMPLATE.md), vinculada a B09-UC01–UC03 y AC01–AC03.
- **Aprobación:** resultado inicial conforme al contrato o diferencias esperadas justificadas y probadas; sin regresiones pendientes. VC01 exige declarar aplicabilidad; No aplica requiere justificación revisada. Es una condición de proceso independiente del porcentaje de AC, sin inflar su denominador. No sustituye tests ni autoriza actualizar la base automáticamente.

**Verificación y salida:** registrar evidencia real UC → AC → TC para la revisión exacta; ejecutar checks y regresión del protocolo; exigir VC01 según su modalidad/aplicabilidad, los tres AC y tests aplicables aprobados y completitud ≥97% sin redondeo. Con 3 AC obligatorios se requiere 3/3. Después: commit candidato → review Standards/Spec → corrección y nueva verificación hasta aprobación → PR para human review. Código simple, tipado y sin comentarios explicativos. No abrir PR ni cerrar B09 solo por tener casillas marcadas.

#### B10 — Configurar y consultar receptor

**Bloqueado por:** B09.

**Objetivo y entrega:** Admin registra referencia de receptor ya autorizado; operador ve beneficiario y cuenta enmascarada; inactivo bloquea emisión.

- **Red:** Cuenta inactiva y destinatario enviado por cliente no habilitan un cobro; listado no filtra datos completos.
- **Green:** Configuración operativa, lectura de receptor y comprobación previa; no alta bancaria pública.
- **Refactor:** Compartir regla receptor habilitado entre todos los canales.

**Contrato de verificación:** [Protocolo común](TICKET_QUALITY_PROTOCOL.md). Actor: Administrador y operador. Frontera: HTTP/formulario receptor. Dependencias anteriores completadas; datos aislados ficticios y actor autorizado salvo casos negativos. Sin ampliaciones al alcance indicado en el objetivo.

**Casos de uso**

- **B10-UC01:** Administrador y operador: configurar como admin y consultar como operador A cuando se cumple «Receptor autorizado ficticio activo de A», para obtener «Beneficiario correcto, cuenta enmascarada y habilitación visible».
- **B10-UC02:** Administrador y operador: intentar emitir solicitud cuando se cumple «Receptor inactivo o ID de receptor ajeno enviado en petición», para obtener «No se emite contra receptor inactivo ni se acepta destinatario arbitrario».
- **B10-UC03:** Administrador y operador: consultar historial y disponibilidad cuando se cumple «Comercio con historial confirmado y receptor deshabilitado», para obtener «Historial permanece; nuevos cobros bloqueados con explicación».

**Criterios de aceptación — obligatorios**

- [ ] **B10-AC01:** Beneficiario correcto, cuenta enmascarada y habilitación visible. Verificación: B10-TC01.
- [ ] **B10-AC02:** No se emite contra receptor inactivo ni se acepta destinatario arbitrario. Verificación: B10-TC02.
- [ ] **B10-AC03:** Historial permanece; nuevos cobros bloqueados con explicación. Verificación: B10-TC03.

**Casos de prueba — todos NOT_RUN**

| ID / trazabilidad | Preparación y datos | Acción | Resultado esperado | Ejecución |
| --- | --- | --- | --- | --- |
| B10-TC01 → B10-UC01, B10-AC01 | Receptor autorizado ficticio activo de A | Configurar como admin y consultar como operador A | Beneficiario correcto, cuenta enmascarada y habilitación visible | Automatizada |
| B10-TC02 → B10-UC02, B10-AC02 | Receptor inactivo o ID de receptor ajeno enviado en petición | Intentar emitir solicitud | No se emite contra receptor inactivo ni se acepta destinatario arbitrario | Automatizada |
| B10-TC03 → B10-UC03, B10-AC03 | Comercio con historial confirmado y receptor deshabilitado | Consultar historial y disponibilidad | Historial permanece; nuevos cobros bloqueados con explicación | Automatizada |

**Comprobación visible según aplique — B10-VC01 (obligatoria, NOT_RUN)**

- **Superficie y alcance:** API y panel. Comparar vista/configuración del receptor y DTO enmascarado con estados activo/inactivo; verificar visualmente beneficiario, habilitación y explicación de bloqueo.
- **Escenarios:** comparar los tres TC anteriores en su interfaz observable; si un escenario no afecta UI, conservar la respuesta/salida en lugar de inventar capturas. Capturar las vistas afectadas por los TC de panel.
- **Modalidad y aplicabilidad:** nuevo → resultado inicial validado contra contrato/AC/TC, sin antes ni diff; modificación → última evidencia aprobada y resultado actual con revisiones y escenario equivalente; sin superficie relevante → No aplica justificado. Una vista sin UI no exige capturas.
- **Artefactos según modalidad:** API nueva: petición/status/JSON/contrato; panel nuevo: capturas del resultado inicial; cambio existente: antes + después + diff o capturas equivalentes; comandos: salida/código inicial o comparado. Completar la [plantilla comparativa](EVIDENCE_COMPARISON_TEMPLATE.md), vinculada a B10-UC01–UC03 y AC01–AC03.
- **Aprobación:** resultado inicial conforme al contrato o diferencias esperadas justificadas y probadas; sin regresiones pendientes. VC01 exige declarar aplicabilidad; No aplica requiere justificación revisada. Es una condición de proceso independiente del porcentaje de AC, sin inflar su denominador. No sustituye tests ni autoriza actualizar la base automáticamente.

**Verificación y salida:** registrar evidencia real UC → AC → TC para la revisión exacta; ejecutar checks y regresión del protocolo; exigir VC01 según su modalidad/aplicabilidad, los tres AC y tests aplicables aprobados y completitud ≥97% sin redondeo. Con 3 AC obligatorios se requiere 3/3. Después: commit candidato → review Standards/Spec → corrección y nueva verificación hasta aprobación → PR para human review. Código simple, tipado y sin comentarios explicativos. No abrir PR ni cerrar B10 solo por tener casillas marcadas.

### H4 — Solicitar y recuperar un cobro QR

#### B11 — Crear y consultar un cobro

**Bloqueado por:** B10.

**Objetivo y entrega:** Operador crea venta con MXN positivo en centavos y concepto opcional, luego la recupera; aún no emite solicitud bancaria.

- **Red:** Importes cero/negativos/fraccionarios en centavos/fuera de rango y consulta ajena fallan.
- **Green:** Modelo de cobro, creación/detalle y DTOs estrictos; importe emitido será inmutable.
- **Refactor:** Aislar reglas monetarias del transporte sin cálculos float.

**Contrato de verificación:** [Protocolo común](TICKET_QUALITY_PROTOCOL.md). Actor: Operador autorizado. Frontera: HTTP cobros. Dependencias anteriores completadas; datos aislados ficticios y actor autorizado salvo casos negativos. Sin ampliaciones al alcance indicado en el objetivo.

**Casos de uso**

- **B11-UC01:** Operador autorizado: crear y consultar cobro cuando se cumple «Comercio A habilitado, 30000 centavos MXN», para obtener «Importe exacto 30000, referencia y concepto recuperables; no implica pago».
- **B11-UC02:** Operador autorizado: crear un cobro por cada caso cuando se cumple «Importes 0, -1, 1.5 centavos y valor fuera del máximo», para obtener «Entrada rechazada sin redondeo ni cobro nuevo».
- **B11-UC03:** Operador autorizado: consultar o alterar su importe con identidad B cuando se cumple «Cobro de A y operador B», para obtener «Sin lectura ni cambio; propiedad e importe se conservan».

**Criterios de aceptación — obligatorios**

- [ ] **B11-AC01:** Importe exacto 30000, referencia y concepto recuperables; no implica pago. Verificación: B11-TC01.
- [ ] **B11-AC02:** Entrada rechazada sin redondeo ni cobro nuevo. Verificación: B11-TC02.
- [ ] **B11-AC03:** Sin lectura ni cambio; propiedad e importe se conservan. Verificación: B11-TC03.

**Casos de prueba — todos NOT_RUN**

| ID / trazabilidad | Preparación y datos | Acción | Resultado esperado | Ejecución |
| --- | --- | --- | --- | --- |
| B11-TC01 → B11-UC01, B11-AC01 | Comercio A habilitado, 30000 centavos MXN | Crear y consultar cobro | Importe exacto 30000, referencia y concepto recuperables; no implica pago | Automatizada |
| B11-TC02 → B11-UC02, B11-AC02 | Importes 0, -1, 1.5 centavos y valor fuera del máximo | Crear un cobro por cada caso | Entrada rechazada sin redondeo ni cobro nuevo | Automatizada |
| B11-TC03 → B11-UC03, B11-AC03 | Cobro de A y operador B | Consultar o alterar su importe con identidad B | Sin lectura ni cambio; propiedad e importe se conservan | Automatizada |

**Comprobación visible según aplique — B11-VC01 (obligatoria, NOT_RUN)**

- **Superficie y alcance:** API cobros. Comparar creación/detalle y errores de importe/propiedad; destacar tipo de centavos, moneda, referencia, concepto y ausencia de recepción al crear.
- **Escenarios:** comparar los tres TC anteriores en su interfaz observable; si un escenario no afecta UI, conservar la respuesta/salida en lugar de inventar capturas. Capturar las vistas afectadas por los TC de panel.
- **Modalidad y aplicabilidad:** nuevo → resultado inicial validado contra contrato/AC/TC, sin antes ni diff; modificación → última evidencia aprobada y resultado actual con revisiones y escenario equivalente; sin superficie relevante → No aplica justificado. Una vista sin UI no exige capturas.
- **Artefactos según modalidad:** API nueva: petición/status/JSON/contrato; panel nuevo: capturas del resultado inicial; cambio existente: antes + después + diff o capturas equivalentes; comandos: salida/código inicial o comparado. Completar la [plantilla comparativa](EVIDENCE_COMPARISON_TEMPLATE.md), vinculada a B11-UC01–UC03 y AC01–AC03.
- **Aprobación:** resultado inicial conforme al contrato o diferencias esperadas justificadas y probadas; sin regresiones pendientes. VC01 exige declarar aplicabilidad; No aplica requiere justificación revisada. Es una condición de proceso independiente del porcentaje de AC, sin inflar su denominador. No sustituye tests ni autoriza actualizar la base automáticamente.

**Verificación y salida:** registrar evidencia real UC → AC → TC para la revisión exacta; ejecutar checks y regresión del protocolo; exigir VC01 según su modalidad/aplicabilidad, los tres AC y tests aplicables aprobados y completitud ≥97% sin redondeo. Con 3 AC obligatorios se requiere 3/3. Después: commit candidato → review Standards/Spec → corrección y nueva verificación hasta aprobación → PR para human review. Código simple, tipado y sin comentarios explicativos. No abrir PR ni cerrar B11 solo por tener casillas marcadas.

#### B12 — Repetir creación sin duplicar venta

**Bloqueado por:** B11.

**Objetivo y entrega:** Misma clave y contenido recuperan venta; misma clave con otro contenido produce conflicto incluso en concurrencia.

- **Red:** Dos peticiones simultáneas crean una sola venta; clave reutilizada con distinto importe falla.
- **Green:** Idempotencia persistente con restricciones y resultado recuperable.
- **Refactor:** Unificar resolución de conflictos sin depender de memoria del proceso.

**Contrato de verificación:** [Protocolo común](TICKET_QUALITY_PROTOCOL.md). Actor: Operador autorizado. Frontera: HTTP creación idempotente. Dependencias anteriores completadas; datos aislados ficticios y actor autorizado salvo casos negativos. Sin ampliaciones al alcance indicado en el objetivo.

**Casos de uso**

- **B12-UC01:** Operador autorizado: crear y repetir mismo contenido cuando se cumple «Clave K e importe 30000 de A», para obtener «Mismo cobro e identificador, sin segunda venta».
- **B12-UC02:** Operador autorizado: reutilizar K con importe 45000 cuando se cumple «Clave K ya usada para 30000», para obtener «409 sin alterar cobro original».
- **B12-UC03:** Operador autorizado: crear y después listar cobros cuando se cumple «Dos peticiones concurrentes con K y mismo contenido», para obtener «Una venta recuperable, sin duplicados por carrera».

**Criterios de aceptación — obligatorios**

- [ ] **B12-AC01:** Mismo cobro e identificador, sin segunda venta. Verificación: B12-TC01.
- [ ] **B12-AC02:** 409 sin alterar cobro original. Verificación: B12-TC02.
- [ ] **B12-AC03:** Una venta recuperable, sin duplicados por carrera. Verificación: B12-TC03.

**Casos de prueba — todos NOT_RUN**

| ID / trazabilidad | Preparación y datos | Acción | Resultado esperado | Ejecución |
| --- | --- | --- | --- | --- |
| B12-TC01 → B12-UC01, B12-AC01 | Clave K e importe 30000 de A | Crear y repetir mismo contenido | Mismo cobro e identificador, sin segunda venta | Automatizada |
| B12-TC02 → B12-UC02, B12-AC02 | Clave K ya usada para 30000 | Reutilizar K con importe 45000 | 409 sin alterar cobro original | Automatizada |
| B12-TC03 → B12-UC03, B12-AC03 | Dos peticiones concurrentes con K y mismo contenido | Crear y después listar cobros | Una venta recuperable, sin duplicados por carrera | Automatizada |

**Comprobación visible según aplique — B12-VC01 (obligatoria, NOT_RUN)**

- **Superficie y alcance:** API idempotencia. Comparar respuestas de petición inicial, repetida, conflictiva y concurrente con mapeo estable de IDs; demostrar misma venta y diferencia explícita del conflicto.
- **Escenarios:** comparar los tres TC anteriores en su interfaz observable; si un escenario no afecta UI, conservar la respuesta/salida en lugar de inventar capturas. Capturar las vistas afectadas por los TC de panel.
- **Modalidad y aplicabilidad:** nuevo → resultado inicial validado contra contrato/AC/TC, sin antes ni diff; modificación → última evidencia aprobada y resultado actual con revisiones y escenario equivalente; sin superficie relevante → No aplica justificado. Una vista sin UI no exige capturas.
- **Artefactos según modalidad:** API nueva: petición/status/JSON/contrato; panel nuevo: capturas del resultado inicial; cambio existente: antes + después + diff o capturas equivalentes; comandos: salida/código inicial o comparado. Completar la [plantilla comparativa](EVIDENCE_COMPARISON_TEMPLATE.md), vinculada a B12-UC01–UC03 y AC01–AC03.
- **Aprobación:** resultado inicial conforme al contrato o diferencias esperadas justificadas y probadas; sin regresiones pendientes. VC01 exige declarar aplicabilidad; No aplica requiere justificación revisada. Es una condición de proceso independiente del porcentaje de AC, sin inflar su denominador. No sustituye tests ni autoriza actualizar la base automáticamente.

**Verificación y salida:** registrar evidencia real UC → AC → TC para la revisión exacta; ejecutar checks y regresión del protocolo; exigir VC01 según su modalidad/aplicabilidad, los tres AC y tests aplicables aprobados y completitud ≥97% sin redondeo. Con 3 AC obligatorios se requiere 3/3. Después: commit candidato → review Standards/Spec → corrección y nueva verificación hasta aprobación → PR para human review. Código simple, tipado y sin comentarios explicativos. No abrir PR ni cerrar B12 solo por tener casillas marcadas.

#### B13 — Reservar un único intento activo

**Bloqueado por:** B12.

**Objetivo y entrega:** Dos peticiones sobre la misma venta no abren dos intentos; reserva queda trazable si se interrumpe el proceso.

- **Red:** Creaciones simultáneas por diferentes claves/canales no reservan dos intentos activos.
- **Green:** Reserva transaccional con versión/estado y límites en Postgres; simulación sin llamadas externas.
- **Refactor:** Reducir duración de bloqueos y separar reserva de red externa.

**Contrato de verificación:** [Protocolo común](TICKET_QUALITY_PROTOCOL.md). Actor: Operador autorizado. Frontera: HTTP intentos. Dependencias anteriores completadas; datos aislados ficticios y actor autorizado salvo casos negativos. Sin ampliaciones al alcance indicado en el objetivo.

**Casos de uso**

- **B13-UC01:** Operador autorizado: reservar intento y consultar venta cuando se cumple «Venta abierta sin intentos», para obtener «Un intento activo recuperable en estado de creación».
- **B13-UC02:** Operador autorizado: solicitar segundo intento con otra clave/canal cuando se cumple «Venta con intento activo», para obtener «Conflicto sin segunda reserva activa».
- **B13-UC03:** Operador autorizado: reservar intentos y consultar estado cuando se cumple «Dos clientes concurrentes sobre una venta», para obtener «Solo uno queda activo; interrupción conserva referencia recuperable».

**Criterios de aceptación — obligatorios**

- [ ] **B13-AC01:** Un intento activo recuperable en estado de creación. Verificación: B13-TC01.
- [ ] **B13-AC02:** Conflicto sin segunda reserva activa. Verificación: B13-TC02.
- [ ] **B13-AC03:** Solo uno queda activo; interrupción conserva referencia recuperable. Verificación: B13-TC03.

**Casos de prueba — todos NOT_RUN**

| ID / trazabilidad | Preparación y datos | Acción | Resultado esperado | Ejecución |
| --- | --- | --- | --- | --- |
| B13-TC01 → B13-UC01, B13-AC01 | Venta abierta sin intentos | Reservar intento y consultar venta | Un intento activo recuperable en estado de creación | Automatizada |
| B13-TC02 → B13-UC02, B13-AC02 | Venta con intento activo | Solicitar segundo intento con otra clave/canal | Conflicto sin segunda reserva activa | Automatizada |
| B13-TC03 → B13-UC03, B13-AC03 | Dos clientes concurrentes sobre una venta | Reservar intentos y consultar estado | Solo uno queda activo; interrupción conserva referencia recuperable | Automatizada |

**Comprobación visible según aplique — B13-VC01 (obligatoria, NOT_RUN)**

- **Superficie y alcance:** API intentos. Comparar reserva única, conflicto y recuperación de intento; preservar relaciones venta/intento y estados al normalizar IDs.
- **Escenarios:** comparar los tres TC anteriores en su interfaz observable; si un escenario no afecta UI, conservar la respuesta/salida en lugar de inventar capturas. Capturar las vistas afectadas por los TC de panel.
- **Modalidad y aplicabilidad:** nuevo → resultado inicial validado contra contrato/AC/TC, sin antes ni diff; modificación → última evidencia aprobada y resultado actual con revisiones y escenario equivalente; sin superficie relevante → No aplica justificado. Una vista sin UI no exige capturas.
- **Artefactos según modalidad:** API nueva: petición/status/JSON/contrato; panel nuevo: capturas del resultado inicial; cambio existente: antes + después + diff o capturas equivalentes; comandos: salida/código inicial o comparado. Completar la [plantilla comparativa](EVIDENCE_COMPARISON_TEMPLATE.md), vinculada a B13-UC01–UC03 y AC01–AC03.
- **Aprobación:** resultado inicial conforme al contrato o diferencias esperadas justificadas y probadas; sin regresiones pendientes. VC01 exige declarar aplicabilidad; No aplica requiere justificación revisada. Es una condición de proceso independiente del porcentaje de AC, sin inflar su denominador. No sustituye tests ni autoriza actualizar la base automáticamente.

**Verificación y salida:** registrar evidencia real UC → AC → TC para la revisión exacta; ejecutar checks y regresión del protocolo; exigir VC01 según su modalidad/aplicabilidad, los tres AC y tests aplicables aprobados y completitud ≥97% sin redondeo. Con 3 AC obligatorios se requiere 3/3. Después: commit candidato → review Standards/Spec → corrección y nueva verificación hasta aprobación → PR para human review. Código simple, tipado y sin comentarios explicativos. No abrir PR ni cerrar B13 solo por tener casillas marcadas.

#### B14 — Mostrar QR pendiente con proveedor simulado

**Bloqueado por:** B13.

**Objetivo y entrega:** Crear intento QR produce payload y estado pendiente consultables; está rotulado como simulación.

- **Red:** Respuesta del simulador no confirma pago; QR consultado conserva payload exacto y referencia.
- **Green:** Adaptador simulado en entorno aislado y flujo crear/consultar QR completo.
- **Refactor:** Definir frontera de proveedor por capacidades, sin simular módulos internos.

**Contrato de verificación:** [Protocolo común](TICKET_QUALITY_PROTOCOL.md). Actor: Operador en demo. Frontera: HTTP QR y simulador externo. Dependencias anteriores completadas; datos aislados ficticios y actor autorizado salvo casos negativos. Sin ampliaciones al alcance indicado en el objetivo.

**Casos de uso**

- **B14-UC01:** Operador en demo: crear QR y recuperar intento cuando se cumple «Proveedor simulado devuelve ID Q1 y payload QR conocido», para obtener «Payload exacto, ID Q1 y etiqueta simulación; estado pendiente».
- **B14-UC02:** Operador en demo: consultar detalle cuando se cumple «Simulador devuelve aceptación sin recepción», para obtener «No aparece Pago recibido ni transferencia confirmada».
- **B14-UC03:** Operador en demo: repetir consulta y recuperar tras reabrir sesión cuando se cumple «Intento pendiente Q1 existente», para obtener «Mismo QR/intento; no se crea solicitud adicional».

**Criterios de aceptación — obligatorios**

- [ ] **B14-AC01:** Payload exacto, ID Q1 y etiqueta simulación; estado pendiente. Verificación: B14-TC01.
- [ ] **B14-AC02:** No aparece Pago recibido ni transferencia confirmada. Verificación: B14-TC02.
- [ ] **B14-AC03:** Mismo QR/intento; no se crea solicitud adicional. Verificación: B14-TC03.

**Casos de prueba — todos NOT_RUN**

| ID / trazabilidad | Preparación y datos | Acción | Resultado esperado | Ejecución |
| --- | --- | --- | --- | --- |
| B14-TC01 → B14-UC01, B14-AC01 | Proveedor simulado devuelve ID Q1 y payload QR conocido | Crear QR y recuperar intento | Payload exacto, ID Q1 y etiqueta simulación; estado pendiente | Automatizada |
| B14-TC02 → B14-UC02, B14-AC02 | Simulador devuelve aceptación sin recepción | Consultar detalle | No aparece Pago recibido ni transferencia confirmada | Automatizada |
| B14-TC03 → B14-UC03, B14-AC03 | Intento pendiente Q1 existente | Repetir consulta y recuperar tras reabrir sesión | Mismo QR/intento; no se crea solicitud adicional | Automatizada |

**Comprobación visible según aplique — B14-VC01 (obligatoria, NOT_RUN)**

- **Superficie y alcance:** API QR simulado. Comparar payload, ID, referencia, estado y marca de simulación en creación/consulta; el diff no debe esconder cambios en el contenido QR.
- **Escenarios:** comparar los tres TC anteriores en su interfaz observable; si un escenario no afecta UI, conservar la respuesta/salida en lugar de inventar capturas. Capturar las vistas afectadas por los TC de panel.
- **Modalidad y aplicabilidad:** nuevo → resultado inicial validado contra contrato/AC/TC, sin antes ni diff; modificación → última evidencia aprobada y resultado actual con revisiones y escenario equivalente; sin superficie relevante → No aplica justificado. Una vista sin UI no exige capturas.
- **Artefactos según modalidad:** API nueva: petición/status/JSON/contrato; panel nuevo: capturas del resultado inicial; cambio existente: antes + después + diff o capturas equivalentes; comandos: salida/código inicial o comparado. Completar la [plantilla comparativa](EVIDENCE_COMPARISON_TEMPLATE.md), vinculada a B14-UC01–UC03 y AC01–AC03.
- **Aprobación:** resultado inicial conforme al contrato o diferencias esperadas justificadas y probadas; sin regresiones pendientes. VC01 exige declarar aplicabilidad; No aplica requiere justificación revisada. Es una condición de proceso independiente del porcentaje de AC, sin inflar su denominador. No sustituye tests ni autoriza actualizar la base automáticamente.

**Verificación y salida:** registrar evidencia real UC → AC → TC para la revisión exacta; ejecutar checks y regresión del protocolo; exigir VC01 según su modalidad/aplicabilidad, los tres AC y tests aplicables aprobados y completitud ≥97% sin redondeo. Con 3 AC obligatorios se requiere 3/3. Después: commit candidato → review Standards/Spec → corrección y nueva verificación hasta aprobación → PR para human review. Código simple, tipado y sin comentarios explicativos. No abrir PR ni cerrar B14 solo por tener casillas marcadas.

#### B15 — Crear QR auténtico mediante pey

**Bloqueado por:** B14.

**Objetivo y entrega:** Adaptador interpreta contrato oficial, preserva QR/ID y asocia receptor; convertir centavos a pesos no pierde precisión.

- **Red:** Fixtures oficiales con 0.01/300.10, error y respuesta inválida no producen confirmación ni IDs inventados.
- **Green:** Adaptador real con timeout, validación y configuración secreta solo servidor; contrato versionado.
- **Refactor:** Mantener traducción del proveedor fuera de cobros y routers.

**Contrato de verificación:** [Protocolo común](TICKET_QUALITY_PROTOCOL.md). Actor: Operador con receptor habilitado. Frontera: Contrato HTTP pey y API. Dependencias anteriores completadas; datos aislados ficticios y actor autorizado salvo casos negativos. Sin ampliaciones al alcance indicado en el objetivo.

**Casos de uso**

- **B15-UC01:** Operador con receptor habilitado: solicitar QR a través del adaptador cuando se cumple «Fixture oficial válido con importes 1 y 30010 centavos», para obtener «Envía equivalentes exactos 0.01 y 300.10 MXN; conserva ID/payload».
- **B15-UC02:** Operador con receptor habilitado: crear QR y consultar estado cuando se cumple «Respuesta proveedor sin payload/ID válido o error definitivo», para obtener «No inventa ID ni confirma pago; error clasificado».
- **B15-UC03:** Operador con receptor habilitado: crear QR e inspeccionar respuesta pública/log sanitizado cuando se cumple «Fixture con bankAccountId autorizado y secreto de test», para obtener «Usa receptor previsto; respuesta y log no contienen credencial».

**Criterios de aceptación — obligatorios**

- [ ] **B15-AC01:** Envía equivalentes exactos 0.01 y 300.10 MXN; conserva ID/payload. Verificación: B15-TC01.
- [ ] **B15-AC02:** No inventa ID ni confirma pago; error clasificado. Verificación: B15-TC02.
- [ ] **B15-AC03:** Usa receptor previsto; respuesta y log no contienen credencial. Verificación: B15-TC03.

**Casos de prueba — todos NOT_RUN**

| ID / trazabilidad | Preparación y datos | Acción | Resultado esperado | Ejecución |
| --- | --- | --- | --- | --- |
| B15-TC01 → B15-UC01, B15-AC01 | Fixture oficial válido con importes 1 y 30010 centavos | Solicitar QR a través del adaptador | Envía equivalentes exactos 0.01 y 300.10 MXN; conserva ID/payload | Automatizada |
| B15-TC02 → B15-UC02, B15-AC02 | Respuesta proveedor sin payload/ID válido o error definitivo | Crear QR y consultar estado | No inventa ID ni confirma pago; error clasificado | Automatizada |
| B15-TC03 → B15-UC03, B15-AC03 | Fixture con bankAccountId autorizado y secreto de test | Crear QR e inspeccionar respuesta pública/log sanitizado | Usa receptor previsto; respuesta y log no contienen credencial | Automatizada |

**Comprobación visible según aplique — B15-VC01 (obligatoria, NOT_RUN)**

- **Superficie y alcance:** API y frontera pey. Comparar respuesta pública anterior/actual y fixtures sanitizados del proveedor; hacer visibles cambios de QR/ID y conversión exacta de centavos, sin secreto de autenticación.
- **Escenarios:** comparar los tres TC anteriores en su interfaz observable; si un escenario no afecta UI, conservar la respuesta/salida en lugar de inventar capturas. Capturar las vistas afectadas por los TC de panel.
- **Modalidad y aplicabilidad:** nuevo → resultado inicial validado contra contrato/AC/TC, sin antes ni diff; modificación → última evidencia aprobada y resultado actual con revisiones y escenario equivalente; sin superficie relevante → No aplica justificado. Una vista sin UI no exige capturas.
- **Artefactos según modalidad:** API nueva: petición/status/JSON/contrato; panel nuevo: capturas del resultado inicial; cambio existente: antes + después + diff o capturas equivalentes; comandos: salida/código inicial o comparado. Completar la [plantilla comparativa](EVIDENCE_COMPARISON_TEMPLATE.md), vinculada a B15-UC01–UC03 y AC01–AC03.
- **Aprobación:** resultado inicial conforme al contrato o diferencias esperadas justificadas y probadas; sin regresiones pendientes. VC01 exige declarar aplicabilidad; No aplica requiere justificación revisada. Es una condición de proceso independiente del porcentaje de AC, sin inflar su denominador. No sustituye tests ni autoriza actualizar la base automáticamente.

**Verificación y salida:** registrar evidencia real UC → AC → TC para la revisión exacta; ejecutar checks y regresión del protocolo; exigir VC01 según su modalidad/aplicabilidad, los tres AC y tests aplicables aprobados y completitud ≥97% sin redondeo. Con 3 AC obligatorios se requiere 3/3. Después: commit candidato → review Standards/Spec → corrección y nueva verificación hasta aprobación → PR para human review. Código simple, tipado y sin comentarios explicativos. No abrir PR ni cerrar B15 solo por tener casillas marcadas.

#### B16 — Recuperar creación QR incierta

**Bloqueado por:** B15.

**Objetivo y entrega:** Timeout conserva intento verificando; reintento de cliente recupera mismo recurso y no vuelve a emitir ciegamente.

- **Red:** Timeout después de aceptación y reenvío no producen un nuevo intento bancario.
- **Green:** Registrar resultado ambiguo y trabajo de conciliación durable junto al intento.
- **Refactor:** Unificar errores definitivos e inciertos sin perder evidencia.

**Contrato de verificación:** [Protocolo común](TICKET_QUALITY_PROTOCOL.md). Actor: Operador con red incierta. Frontera: HTTP y simulador pey. Dependencias anteriores completadas; datos aislados ficticios y actor autorizado salvo casos negativos. Sin ampliaciones al alcance indicado en el objetivo.

**Casos de uso**

- **B16-UC01:** Operador con red incierta: crear y consultar intento local cuando se cumple «Proveedor acepta solicitud pero respuesta se pierde», para obtener «Intento queda verificando con referencia persistida».
- **B16-UC02:** Operador con red incierta: repetir petición de creación cuando se cumple «Misma clave tras timeout», para obtener «Recupera mismo recurso; no emite segundo cobro bancario».
- **B16-UC03:** Operador con red incierta: recuperar intento y trabajo por interfaz operativa cuando se cumple «Reinicio después del timeout», para obtener «Incertidumbre y tarea se conservan; no se declara fallido por ausencia de respuesta».

**Criterios de aceptación — obligatorios**

- [ ] **B16-AC01:** Intento queda verificando con referencia persistida. Verificación: B16-TC01.
- [ ] **B16-AC02:** Recupera mismo recurso; no emite segundo cobro bancario. Verificación: B16-TC02.
- [ ] **B16-AC03:** Incertidumbre y tarea se conservan; no se declara fallido por ausencia de respuesta. Verificación: B16-TC03.

**Casos de prueba — todos NOT_RUN**

| ID / trazabilidad | Preparación y datos | Acción | Resultado esperado | Ejecución |
| --- | --- | --- | --- | --- |
| B16-TC01 → B16-UC01, B16-AC01 | Proveedor acepta solicitud pero respuesta se pierde | Crear y consultar intento local | Intento queda verificando con referencia persistida | Automatizada |
| B16-TC02 → B16-UC02, B16-AC02 | Misma clave tras timeout | Repetir petición de creación | Recupera mismo recurso; no emite segundo cobro bancario | Automatizada |
| B16-TC03 → B16-UC03, B16-AC03 | Reinicio después del timeout | Recuperar intento y trabajo por interfaz operativa | Incertidumbre y tarea se conservan; no se declara fallido por ausencia de respuesta | Automatizada |

**Comprobación visible según aplique — B16-VC01 (obligatoria, NOT_RUN)**

- **Superficie y alcance:** API recuperación. Comparar timeout, reintento y recuperación tras reinicio: mismo ID local, estado verificando y ausencia de segunda emisión en evidencia del simulador.
- **Escenarios:** comparar los tres TC anteriores en su interfaz observable; si un escenario no afecta UI, conservar la respuesta/salida en lugar de inventar capturas. Capturar las vistas afectadas por los TC de panel.
- **Modalidad y aplicabilidad:** nuevo → resultado inicial validado contra contrato/AC/TC, sin antes ni diff; modificación → última evidencia aprobada y resultado actual con revisiones y escenario equivalente; sin superficie relevante → No aplica justificado. Una vista sin UI no exige capturas.
- **Artefactos según modalidad:** API nueva: petición/status/JSON/contrato; panel nuevo: capturas del resultado inicial; cambio existente: antes + después + diff o capturas equivalentes; comandos: salida/código inicial o comparado. Completar la [plantilla comparativa](EVIDENCE_COMPARISON_TEMPLATE.md), vinculada a B16-UC01–UC03 y AC01–AC03.
- **Aprobación:** resultado inicial conforme al contrato o diferencias esperadas justificadas y probadas; sin regresiones pendientes. VC01 exige declarar aplicabilidad; No aplica requiere justificación revisada. Es una condición de proceso independiente del porcentaje de AC, sin inflar su denominador. No sustituye tests ni autoriza actualizar la base automáticamente.

**Verificación y salida:** registrar evidencia real UC → AC → TC para la revisión exacta; ejecutar checks y regresión del protocolo; exigir VC01 según su modalidad/aplicabilidad, los tres AC y tests aplicables aprobados y completitud ≥97% sin redondeo. Con 3 AC obligatorios se requiere 3/3. Después: commit candidato → review Standards/Spec → corrección y nueva verificación hasta aprobación → PR para human review. Código simple, tipado y sin comentarios explicativos. No abrir PR ni cerrar B16 solo por tener casillas marcadas.

### H5 — Comprobar recepción sin duplicar dinero

#### B17 — Recibir y conservar webhook válido

**Bloqueado por:** B14.

**Objetivo y entrega:** Firma y antigüedad válidas permiten guardar evento antes de responder; firma inválida no modifica cobro.

- **Red:** Cuerpo alterado, timestamp viejo y fallo de persistencia no reciben éxito indebido.
- **Green:** Verificación sobre bytes originales, límites de cuerpo, esquema y recepción durable.
- **Refactor:** Separar verificación externa de aplicación de evidencia al dominio.

**Contrato de verificación:** [Protocolo común](TICKET_QUALITY_PROTOCOL.md). Actor: Proveedor y operación. Frontera: HTTP webhook. Dependencias anteriores completadas; datos aislados ficticios y actor autorizado salvo casos negativos. Sin ampliaciones al alcance indicado en el objetivo.

**Casos de uso**

- **B17-UC01:** Proveedor y operación: entregar webhook cuando se cumple «Evento válido firmado con secreto de test y timestamp permitido», para obtener «Solo responde 2xx después de conservación durable».
- **B17-UC02:** Proveedor y operación: entregar cada variante cuando se cumple «Cuerpo alterado, firma inválida o timestamp fuera de tolerancia», para obtener «Sin confirmación ni aceptación indebida».
- **B17-UC03:** Proveedor y operación: entregar evento y después reintentar con DB disponible cuando se cumple «Persistencia indisponible durante recepción», para obtener «Primero error temporal; luego conserva evento sin pérdida por ACK anticipado».

**Criterios de aceptación — obligatorios**

- [ ] **B17-AC01:** Solo responde 2xx después de conservación durable. Verificación: B17-TC01.
- [ ] **B17-AC02:** Sin confirmación ni aceptación indebida. Verificación: B17-TC02.
- [ ] **B17-AC03:** Primero error temporal; luego conserva evento sin pérdida por ACK anticipado. Verificación: B17-TC03.

**Casos de prueba — todos NOT_RUN**

| ID / trazabilidad | Preparación y datos | Acción | Resultado esperado | Ejecución |
| --- | --- | --- | --- | --- |
| B17-TC01 → B17-UC01, B17-AC01 | Evento válido firmado con secreto de test y timestamp permitido | Entregar webhook | Solo responde 2xx después de conservación durable | Automatizada |
| B17-TC02 → B17-UC02, B17-AC02 | Cuerpo alterado, firma inválida o timestamp fuera de tolerancia | Entregar cada variante | Sin confirmación ni aceptación indebida | Automatizada |
| B17-TC03 → B17-UC03, B17-AC03 | Persistencia indisponible durante recepción | Entregar evento y después reintentar con DB disponible | Primero error temporal; luego conserva evento sin pérdida por ACK anticipado | Automatizada |

**Comprobación visible según aplique — B17-VC01 (obligatoria, NOT_RUN)**

- **Superficie y alcance:** API webhook. Comparar status de recepción válida/inválida y efecto durable consultable; mostrar estructura sanitizada del evento, omitiendo firmas y secretos.
- **Escenarios:** comparar los tres TC anteriores en su interfaz observable; si un escenario no afecta UI, conservar la respuesta/salida en lugar de inventar capturas. Capturar las vistas afectadas por los TC de panel.
- **Modalidad y aplicabilidad:** nuevo → resultado inicial validado contra contrato/AC/TC, sin antes ni diff; modificación → última evidencia aprobada y resultado actual con revisiones y escenario equivalente; sin superficie relevante → No aplica justificado. Una vista sin UI no exige capturas.
- **Artefactos según modalidad:** API nueva: petición/status/JSON/contrato; panel nuevo: capturas del resultado inicial; cambio existente: antes + después + diff o capturas equivalentes; comandos: salida/código inicial o comparado. Completar la [plantilla comparativa](EVIDENCE_COMPARISON_TEMPLATE.md), vinculada a B17-UC01–UC03 y AC01–AC03.
- **Aprobación:** resultado inicial conforme al contrato o diferencias esperadas justificadas y probadas; sin regresiones pendientes. VC01 exige declarar aplicabilidad; No aplica requiere justificación revisada. Es una condición de proceso independiente del porcentaje de AC, sin inflar su denominador. No sustituye tests ni autoriza actualizar la base automáticamente.

**Verificación y salida:** registrar evidencia real UC → AC → TC para la revisión exacta; ejecutar checks y regresión del protocolo; exigir VC01 según su modalidad/aplicabilidad, los tres AC y tests aplicables aprobados y completitud ≥97% sin redondeo. Con 3 AC obligatorios se requiere 3/3. Después: commit candidato → review Standards/Spec → corrección y nueva verificación hasta aprobación → PR para human review. Código simple, tipado y sin comentarios explicativos. No abrir PR ni cerrar B17 solo por tener casillas marcadas.

#### B18 — Confirmar una recepción exacta

**Bloqueado por:** B17.

**Objetivo y entrega:** Evento o evidencia de consulta válidos para cuenta, importe y referencia confirman transferencia y venta de forma atómica.

- **Red:** Evidencia exacta cambia detalle a recibido; fallo a mitad de aplicación no deja recepción parcial.
- **Green:** Aplicar transferencia e importe/estado en una transacción recuperable; API muestra fecha y referencia verificadas.
- **Refactor:** Una única operación de aplicación para eventos y conciliación.

**Contrato de verificación:** [Protocolo común](TICKET_QUALITY_PROTOCOL.md). Actor: Operador y proveedor. Frontera: Webhook/comando evidencia y HTTP consulta. Dependencias anteriores completadas; datos aislados ficticios y actor autorizado salvo casos negativos. Sin ampliaciones al alcance indicado en el objetivo.

**Casos de uso**

- **B18-UC01:** Operador y proveedor: aplicar evidencia y consultar detalle cuando se cumple «Venta 30000, cuenta A y evidencia exacta correlacionada», para obtener «Transferencia propia confirmada y venta cubierta por 30000».
- **B18-UC02:** Operador y proveedor: aplicar y consultar cuando se cumple «Evidencia sin cuenta, importe o referencia suficientes», para obtener «No marca venta recibida sin validación suficiente».
- **B18-UC03:** Operador y proveedor: aplicar, recuperar y volver a consultar cuando se cumple «Fallo inducido dentro de operación antes de completar commit», para obtener «No queda estado parcial; reproceso completa una recepción coherente».

**Criterios de aceptación — obligatorios**

- [ ] **B18-AC01:** Transferencia propia confirmada y venta cubierta por 30000. Verificación: B18-TC01.
- [ ] **B18-AC02:** No marca venta recibida sin validación suficiente. Verificación: B18-TC02.
- [ ] **B18-AC03:** No queda estado parcial; reproceso completa una recepción coherente. Verificación: B18-TC03.

**Casos de prueba — todos NOT_RUN**

| ID / trazabilidad | Preparación y datos | Acción | Resultado esperado | Ejecución |
| --- | --- | --- | --- | --- |
| B18-TC01 → B18-UC01, B18-AC01 | Venta 30000, cuenta A y evidencia exacta correlacionada | Aplicar evidencia y consultar detalle | Transferencia propia confirmada y venta cubierta por 30000 | Automatizada |
| B18-TC02 → B18-UC02, B18-AC02 | Evidencia sin cuenta, importe o referencia suficientes | Aplicar y consultar | No marca venta recibida sin validación suficiente | Automatizada |
| B18-TC03 → B18-UC03, B18-AC03 | Fallo inducido dentro de operación antes de completar commit | Aplicar, recuperar y volver a consultar | No queda estado parcial; reproceso completa una recepción coherente | Automatizada |

**Comprobación visible según aplique — B18-VC01 (obligatoria, NOT_RUN)**

- **Superficie y alcance:** API recepción. Comparar detalle antes pendiente/después recibido y lectura tras fallo transaccional; mostrar importe, receptor verificado y referencias sin ocultar diferencias semánticas.
- **Escenarios:** comparar los tres TC anteriores en su interfaz observable; si un escenario no afecta UI, conservar la respuesta/salida en lugar de inventar capturas. Capturar las vistas afectadas por los TC de panel.
- **Modalidad y aplicabilidad:** nuevo → resultado inicial validado contra contrato/AC/TC, sin antes ni diff; modificación → última evidencia aprobada y resultado actual con revisiones y escenario equivalente; sin superficie relevante → No aplica justificado. Una vista sin UI no exige capturas.
- **Artefactos según modalidad:** API nueva: petición/status/JSON/contrato; panel nuevo: capturas del resultado inicial; cambio existente: antes + después + diff o capturas equivalentes; comandos: salida/código inicial o comparado. Completar la [plantilla comparativa](EVIDENCE_COMPARISON_TEMPLATE.md), vinculada a B18-UC01–UC03 y AC01–AC03.
- **Aprobación:** resultado inicial conforme al contrato o diferencias esperadas justificadas y probadas; sin regresiones pendientes. VC01 exige declarar aplicabilidad; No aplica requiere justificación revisada. Es una condición de proceso independiente del porcentaje de AC, sin inflar su denominador. No sustituye tests ni autoriza actualizar la base automáticamente.

**Verificación y salida:** registrar evidencia real UC → AC → TC para la revisión exacta; ejecutar checks y regresión del protocolo; exigir VC01 según su modalidad/aplicabilidad, los tres AC y tests aplicables aprobados y completitud ≥97% sin redondeo. Con 3 AC obligatorios se requiere 3/3. Después: commit candidato → review Standards/Spec → corrección y nueva verificación hasta aprobación → PR para human review. Código simple, tipado y sin comentarios explicativos. No abrir PR ni cerrar B18 solo por tener casillas marcadas.

#### B19 — Deduplicar eventos y transferencias

**Bloqueado por:** B18.

**Objetivo y entrega:** Repetir evento o recibir varios eventos de una transferencia no cambia el total; mismo ID con otro contenido se señala.

- **Red:** Duplicados concurrentes y evento/consulta de la misma transferencia suman una vez; hash conflictivo no sobrescribe.
- **Green:** Unicidad por proveedor/entorno e IDs, manejo de conflictos y reprocesado seguro.
- **Refactor:** Concentrar claves y política de duplicación en persistencia/dominio.

**Contrato de verificación:** [Protocolo común](TICKET_QUALITY_PROTOCOL.md). Actor: Proveedor y conciliador. Frontera: Webhook/comando y consultas. Dependencias anteriores completadas; datos aislados ficticios y actor autorizado salvo casos negativos. Sin ampliaciones al alcance indicado en el objetivo.

**Casos de uso**

- **B19-UC01:** Proveedor y conciliador: reentregar evento E1 cuando se cumple «Transferencia T1 ya validada para A», para obtener «Misma transferencia; importe recibido no aumenta».
- **B19-UC02:** Proveedor y conciliador: entregar variante cuando se cumple «Mismo eventId E1 con contenido diferente», para obtener «Conflicto señalado, original conservado y sin efecto monetario extra».
- **B19-UC03:** Proveedor y conciliador: procesar y consultar detalle/totales cuando se cumple «Eventos E1/E2 y consulta concurrente para T1», para obtener «Una transferencia y un único efecto en totales».

**Criterios de aceptación — obligatorios**

- [ ] **B19-AC01:** Misma transferencia; importe recibido no aumenta. Verificación: B19-TC01.
- [ ] **B19-AC02:** Conflicto señalado, original conservado y sin efecto monetario extra. Verificación: B19-TC02.
- [ ] **B19-AC03:** Una transferencia y un único efecto en totales. Verificación: B19-TC03.

**Casos de prueba — todos NOT_RUN**

| ID / trazabilidad | Preparación y datos | Acción | Resultado esperado | Ejecución |
| --- | --- | --- | --- | --- |
| B19-TC01 → B19-UC01, B19-AC01 | Transferencia T1 ya validada para A | Reentregar evento E1 | Misma transferencia; importe recibido no aumenta | Automatizada |
| B19-TC02 → B19-UC02, B19-AC02 | Mismo eventId E1 con contenido diferente | Entregar variante | Conflicto señalado, original conservado y sin efecto monetario extra | Automatizada |
| B19-TC03 → B19-UC03, B19-AC03 | Eventos E1/E2 y consulta concurrente para T1 | Procesar y consultar detalle/totales | Una transferencia y un único efecto en totales | Automatizada |

**Comprobación visible según aplique — B19-VC01 (obligatoria, NOT_RUN)**

- **Superficie y alcance:** API y evidencia. Comparar detalle/totales antes/después de duplicados y conflicto de contenido; debe verse que repetir T1 no incrementa importe y que el conflicto queda señalado.
- **Escenarios:** comparar los tres TC anteriores en su interfaz observable; si un escenario no afecta UI, conservar la respuesta/salida en lugar de inventar capturas. Capturar las vistas afectadas por los TC de panel.
- **Modalidad y aplicabilidad:** nuevo → resultado inicial validado contra contrato/AC/TC, sin antes ni diff; modificación → última evidencia aprobada y resultado actual con revisiones y escenario equivalente; sin superficie relevante → No aplica justificado. Una vista sin UI no exige capturas.
- **Artefactos según modalidad:** API nueva: petición/status/JSON/contrato; panel nuevo: capturas del resultado inicial; cambio existente: antes + después + diff o capturas equivalentes; comandos: salida/código inicial o comparado. Completar la [plantilla comparativa](EVIDENCE_COMPARISON_TEMPLATE.md), vinculada a B19-UC01–UC03 y AC01–AC03.
- **Aprobación:** resultado inicial conforme al contrato o diferencias esperadas justificadas y probadas; sin regresiones pendientes. VC01 exige declarar aplicabilidad; No aplica requiere justificación revisada. Es una condición de proceso independiente del porcentaje de AC, sin inflar su denominador. No sustituye tests ni autoriza actualizar la base automáticamente.

**Verificación y salida:** registrar evidencia real UC → AC → TC para la revisión exacta; ejecutar checks y regresión del protocolo; exigir VC01 según su modalidad/aplicabilidad, los tres AC y tests aplicables aprobados y completitud ≥97% sin redondeo. Con 3 AC obligatorios se requiere 3/3. Después: commit candidato → review Standards/Spec → corrección y nueva verificación hasta aprobación → PR para human review. Código simple, tipado y sin comentarios explicativos. No abrir PR ni cerrar B19 solo por tener casillas marcadas.

#### B20 — Conservar discrepancias como incidencia

**Bloqueado por:** B18.

**Objetivo y entrega:** Importe, moneda, receptor o asociación dudosos no cubren automáticamente una venta; dinero verificado propio se conserva.

- **Red:** Importe distinto no marca venta pagada; receptor ajeno no suma al comercio.
- **Green:** Registro de incidencias y transferencias propias verificadas, sin asociación aproximada.
- **Refactor:** Separar recepción comprobada de cobertura de la venta.

**Contrato de verificación:** [Protocolo común](TICKET_QUALITY_PROTOCOL.md). Actor: Operador y revisor. Frontera: Aplicación evidencia y consultas. Dependencias anteriores completadas; datos aislados ficticios y actor autorizado salvo casos negativos. Sin ampliaciones al alcance indicado en el objetivo.

**Casos de uso**

- **B20-UC01:** Operador y revisor: aplicar y consultar incidencia cuando se cumple «Cuenta A verificada, venta 30000 y transferencia propia 25000», para obtener «Recepción propia conservada e incidencia; venta no cubierta automáticamente».
- **B20-UC02:** Operador y revisor: aplicar contra venta A cuando se cumple «Transferencia hacia cuenta B ajena», para obtener «No confirma ni suma dinero al comercio A».
- **B20-UC03:** Operador y revisor: aplicar y volver a procesar cuando se cumple «Referencia no asociable con certeza», para obtener «Evidencia permanece en revisión sin asociación aproximada ni duplicado».

**Criterios de aceptación — obligatorios**

- [ ] **B20-AC01:** Recepción propia conservada e incidencia; venta no cubierta automáticamente. Verificación: B20-TC01.
- [ ] **B20-AC02:** No confirma ni suma dinero al comercio A. Verificación: B20-TC02.
- [ ] **B20-AC03:** Evidencia permanece en revisión sin asociación aproximada ni duplicado. Verificación: B20-TC03.

**Casos de prueba — todos NOT_RUN**

| ID / trazabilidad | Preparación y datos | Acción | Resultado esperado | Ejecución |
| --- | --- | --- | --- | --- |
| B20-TC01 → B20-UC01, B20-AC01 | Cuenta A verificada, venta 30000 y transferencia propia 25000 | Aplicar y consultar incidencia | Recepción propia conservada e incidencia; venta no cubierta automáticamente | Automatizada |
| B20-TC02 → B20-UC02, B20-AC02 | Transferencia hacia cuenta B ajena | Aplicar contra venta A | No confirma ni suma dinero al comercio A | Automatizada |
| B20-TC03 → B20-UC03, B20-AC03 | Referencia no asociable con certeza | Aplicar y volver a procesar | Evidencia permanece en revisión sin asociación aproximada ni duplicado | Automatizada |

**Comprobación visible según aplique — B20-VC01 (obligatoria, NOT_RUN)**

- **Superficie y alcance:** API incidencias. Comparar venta, recepción e incidencia ante importe distinto, receptor ajeno y referencia incierta; mostrar qué suma, qué no suma y por qué no se cubre la venta.
- **Escenarios:** comparar los tres TC anteriores en su interfaz observable; si un escenario no afecta UI, conservar la respuesta/salida en lugar de inventar capturas. Capturar las vistas afectadas por los TC de panel.
- **Modalidad y aplicabilidad:** nuevo → resultado inicial validado contra contrato/AC/TC, sin antes ni diff; modificación → última evidencia aprobada y resultado actual con revisiones y escenario equivalente; sin superficie relevante → No aplica justificado. Una vista sin UI no exige capturas.
- **Artefactos según modalidad:** API nueva: petición/status/JSON/contrato; panel nuevo: capturas del resultado inicial; cambio existente: antes + después + diff o capturas equivalentes; comandos: salida/código inicial o comparado. Completar la [plantilla comparativa](EVIDENCE_COMPARISON_TEMPLATE.md), vinculada a B20-UC01–UC03 y AC01–AC03.
- **Aprobación:** resultado inicial conforme al contrato o diferencias esperadas justificadas y probadas; sin regresiones pendientes. VC01 exige declarar aplicabilidad; No aplica requiere justificación revisada. Es una condición de proceso independiente del porcentaje de AC, sin inflar su denominador. No sustituye tests ni autoriza actualizar la base automáticamente.

**Verificación y salida:** registrar evidencia real UC → AC → TC para la revisión exacta; ejecutar checks y regresión del protocolo; exigir VC01 según su modalidad/aplicabilidad, los tres AC y tests aplicables aprobados y completitud ≥97% sin redondeo. Con 3 AC obligatorios se requiere 3/3. Después: commit candidato → review Standards/Spec → corrección y nueva verificación hasta aprobación → PR para human review. Código simple, tipado y sin comentarios explicativos. No abrir PR ni cerrar B20 solo por tener casillas marcadas.

#### B21 — Procesar eventos anticipados y desordenados

**Bloqueado por:** B19.

**Objetivo y entrega:** Webhook temprano se recupera después; respuesta pendiente tardía no degrada pago recibido.

- **Red:** Pago antes de respuesta de creación y posterior evento pendiente conservan PAID.
- **Green:** Asociación diferida y transiciones con control de versión.
- **Refactor:** Consolidar transiciones permitidas y retirar condicionales duplicados.

**Contrato de verificación:** [Protocolo común](TICKET_QUALITY_PROTOCOL.md). Actor: Proveedor y conciliador. Frontera: Webhook/creación y consulta. Dependencias anteriores completadas; datos aislados ficticios y actor autorizado salvo casos negativos. Sin ampliaciones al alcance indicado en el objetivo.

**Casos de uso**

- **B21-UC01:** Proveedor y conciliador: entregar evento, persistir respuesta y recuperar cuando se cumple «Evento de pago llega antes que respuesta de creación», para obtener «Evento se asocia/reprocesa y recepción termina confirmada».
- **B21-UC02:** Proveedor y conciliador: entregar respuesta PENDING tardía cuando se cumple «Intento ya confirmado», para obtener «Estado recibido no se degrada».
- **B21-UC03:** Proveedor y conciliador: completar referencias y reprocesar cuando se cumple «Evento inicialmente no asociable», para obtener «Una transferencia asociada, sin perder evento temprano».

**Criterios de aceptación — obligatorios**

- [ ] **B21-AC01:** Evento se asocia/reprocesa y recepción termina confirmada. Verificación: B21-TC01.
- [ ] **B21-AC02:** Estado recibido no se degrada. Verificación: B21-TC02.
- [ ] **B21-AC03:** Una transferencia asociada, sin perder evento temprano. Verificación: B21-TC03.

**Casos de prueba — todos NOT_RUN**

| ID / trazabilidad | Preparación y datos | Acción | Resultado esperado | Ejecución |
| --- | --- | --- | --- | --- |
| B21-TC01 → B21-UC01, B21-AC01 | Evento de pago llega antes que respuesta de creación | Entregar evento, persistir respuesta y recuperar | Evento se asocia/reprocesa y recepción termina confirmada | Automatizada |
| B21-TC02 → B21-UC02, B21-AC02 | Intento ya confirmado | Entregar respuesta PENDING tardía | Estado recibido no se degrada | Automatizada |
| B21-TC03 → B21-UC03, B21-AC03 | Evento inicialmente no asociable | Completar referencias y reprocesar | Una transferencia asociada, sin perder evento temprano | Automatizada |

**Comprobación visible según aplique — B21-VC01 (obligatoria, NOT_RUN)**

- **Superficie y alcance:** API estados. Comparar secuencia observable con pago anticipado y respuesta pendiente tardía; reportar cada transición y la conservación de la confirmación final.
- **Escenarios:** comparar los tres TC anteriores en su interfaz observable; si un escenario no afecta UI, conservar la respuesta/salida en lugar de inventar capturas. Capturar las vistas afectadas por los TC de panel.
- **Modalidad y aplicabilidad:** nuevo → resultado inicial validado contra contrato/AC/TC, sin antes ni diff; modificación → última evidencia aprobada y resultado actual con revisiones y escenario equivalente; sin superficie relevante → No aplica justificado. Una vista sin UI no exige capturas.
- **Artefactos según modalidad:** API nueva: petición/status/JSON/contrato; panel nuevo: capturas del resultado inicial; cambio existente: antes + después + diff o capturas equivalentes; comandos: salida/código inicial o comparado. Completar la [plantilla comparativa](EVIDENCE_COMPARISON_TEMPLATE.md), vinculada a B21-UC01–UC03 y AC01–AC03.
- **Aprobación:** resultado inicial conforme al contrato o diferencias esperadas justificadas y probadas; sin regresiones pendientes. VC01 exige declarar aplicabilidad; No aplica requiere justificación revisada. Es una condición de proceso independiente del porcentaje de AC, sin inflar su denominador. No sustituye tests ni autoriza actualizar la base automáticamente.

**Verificación y salida:** registrar evidencia real UC → AC → TC para la revisión exacta; ejecutar checks y regresión del protocolo; exigir VC01 según su modalidad/aplicabilidad, los tres AC y tests aplicables aprobados y completitud ≥97% sin redondeo. Con 3 AC obligatorios se requiere 3/3. Después: commit candidato → review Standards/Spec → corrección y nueva verificación hasta aprobación → PR para human review. Código simple, tipado y sin comentarios explicativos. No abrir PR ni cerrar B21 solo por tener casillas marcadas.

#### B22 — Conciliar QR cuando falta notificación

**Bloqueado por:** B16, B18.

**Objetivo y entrega:** Consulta por ID de QR encuentra evidencia incluyendo paginación y aplica la misma confirmación; ausencia no significa rechazo.

- **Red:** Sin webhook, evidencia en segunda página confirma; respuesta vacía mantiene incertidumbre.
- **Green:** Consulta acotada del proveedor y comando operativo de conciliación por intento.
- **Refactor:** Reusar normalización de evidencia y política de errores.

**Contrato de verificación:** [Protocolo común](TICKET_QUALITY_PROTOCOL.md). Actor: Responsable operativo. Frontera: Comando conciliación y HTTP consulta. Dependencias anteriores completadas; datos aislados ficticios y actor autorizado salvo casos negativos. Sin ampliaciones al alcance indicado en el objetivo.

**Casos de uso**

- **B22-UC01:** Responsable operativo: conciliar Q1 y consultar detalle cuando se cumple «QR Q1 pendiente, evidencia propia aparece en segunda página», para obtener «Encuentra transferencia y confirma una vez».
- **B22-UC02:** Responsable operativo: conciliar y consultar cuando se cumple «Consulta sin evidencia o con respuesta temporal incierta», para obtener «Permanece sin confirmar; ausencia no implica rechazo».
- **B22-UC03:** Responsable operativo: procesar ambos y consultar cuando se cumple «Webhook y consulta devuelven la misma transferencia», para obtener «No duplica importe ni venta».

**Criterios de aceptación — obligatorios**

- [ ] **B22-AC01:** Encuentra transferencia y confirma una vez. Verificación: B22-TC01.
- [ ] **B22-AC02:** Permanece sin confirmar; ausencia no implica rechazo. Verificación: B22-TC02.
- [ ] **B22-AC03:** No duplica importe ni venta. Verificación: B22-TC03.

**Casos de prueba — todos NOT_RUN**

| ID / trazabilidad | Preparación y datos | Acción | Resultado esperado | Ejecución |
| --- | --- | --- | --- | --- |
| B22-TC01 → B22-UC01, B22-AC01 | QR Q1 pendiente, evidencia propia aparece en segunda página | Conciliar Q1 y consultar detalle | Encuentra transferencia y confirma una vez | Automatizada |
| B22-TC02 → B22-UC02, B22-AC02 | Consulta sin evidencia o con respuesta temporal incierta | Conciliar y consultar | Permanece sin confirmar; ausencia no implica rechazo | Automatizada |
| B22-TC03 → B22-UC03, B22-AC03 | Webhook y consulta devuelven la misma transferencia | Procesar ambos y consultar | No duplica importe ni venta | Automatizada |

**Comprobación visible según aplique — B22-VC01 (obligatoria, NOT_RUN)**

- **Superficie y alcance:** Comando y API. Comparar salida de conciliación y detalle antes/después con evidencia en página posterior, ausencia de evidencia y duplicado por webhook.
- **Escenarios:** comparar los tres TC anteriores en su interfaz observable; si un escenario no afecta UI, conservar la respuesta/salida en lugar de inventar capturas. Capturar las vistas afectadas por los TC de panel.
- **Modalidad y aplicabilidad:** nuevo → resultado inicial validado contra contrato/AC/TC, sin antes ni diff; modificación → última evidencia aprobada y resultado actual con revisiones y escenario equivalente; sin superficie relevante → No aplica justificado. Una vista sin UI no exige capturas.
- **Artefactos según modalidad:** API nueva: petición/status/JSON/contrato; panel nuevo: capturas del resultado inicial; cambio existente: antes + después + diff o capturas equivalentes; comandos: salida/código inicial o comparado. Completar la [plantilla comparativa](EVIDENCE_COMPARISON_TEMPLATE.md), vinculada a B22-UC01–UC03 y AC01–AC03.
- **Aprobación:** resultado inicial conforme al contrato o diferencias esperadas justificadas y probadas; sin regresiones pendientes. VC01 exige declarar aplicabilidad; No aplica requiere justificación revisada. Es una condición de proceso independiente del porcentaje de AC, sin inflar su denominador. No sustituye tests ni autoriza actualizar la base automáticamente.

**Verificación y salida:** registrar evidencia real UC → AC → TC para la revisión exacta; ejecutar checks y regresión del protocolo; exigir VC01 según su modalidad/aplicabilidad, los tres AC y tests aplicables aprobados y completitud ≥97% sin redondeo. Con 3 AC obligatorios se requiere 3/3. Después: commit candidato → review Standards/Spec → corrección y nueva verificación hasta aprobación → PR para human review. Código simple, tipado y sin comentarios explicativos. No abrir PR ni cerrar B22 solo por tener casillas marcadas.

#### B23 — Recuperar trabajos tras reinicio

**Bloqueado por:** B22, B19.

**Objetivo y entrega:** Trabajo persistido se reclama con lease; caída y dos ejecutores no pierden tareas ni duplican dinero.

- **Red:** Interrupción tras guardar evento y lease vencido recuperan trabajo; 429 respeta espera.
- **Green:** Ejecutor de lotes, reintentos acotados y comando programable con backoff; sin cola externa inicial.
- **Refactor:** Compartir reclamación/reprogramación y aislar reloj/planificador.

**Contrato de verificación:** [Protocolo común](TICKET_QUALITY_PROTOCOL.md). Actor: Responsable operativo. Frontera: Comando de ejecutor y consultas. Dependencias anteriores completadas; datos aislados ficticios y actor autorizado salvo casos negativos. Sin ampliaciones al alcance indicado en el objetivo.

**Casos de uso**

- **B23-UC01:** Responsable operativo: ejecutar lote cuando se cumple «Evento/trabajo persistido sin completar», para obtener «Trabajo finaliza y resultado es consultable».
- **B23-UC02:** Responsable operativo: reclamar trabajo simultáneamente cuando se cumple «Dos ejecutores y un lease vigente», para obtener «Un reclamante activo por lease; no duplica efecto».
- **B23-UC03:** Responsable operativo: reanudar con reloj controlado cuando se cumple «Proceso cae, lease vence y proveedor devuelve 429 al reintentar», para obtener «Trabajo se recupera y espera según backoff; no se pierde ni reintenta sin límite».

**Criterios de aceptación — obligatorios**

- [ ] **B23-AC01:** Trabajo finaliza y resultado es consultable. Verificación: B23-TC01.
- [ ] **B23-AC02:** Un reclamante activo por lease; no duplica efecto. Verificación: B23-TC02.
- [ ] **B23-AC03:** Trabajo se recupera y espera según backoff; no se pierde ni reintenta sin límite. Verificación: B23-TC03.

**Casos de prueba — todos NOT_RUN**

| ID / trazabilidad | Preparación y datos | Acción | Resultado esperado | Ejecución |
| --- | --- | --- | --- | --- |
| B23-TC01 → B23-UC01, B23-AC01 | Evento/trabajo persistido sin completar | Ejecutar lote | Trabajo finaliza y resultado es consultable | Automatizada |
| B23-TC02 → B23-UC02, B23-AC02 | Dos ejecutores y un lease vigente | Reclamar trabajo simultáneamente | Un reclamante activo por lease; no duplica efecto | Automatizada |
| B23-TC03 → B23-UC03, B23-AC03 | Proceso cae, lease vence y proveedor devuelve 429 al reintentar | Reanudar con reloj controlado | Trabajo se recupera y espera según backoff; no se pierde ni reintenta sin límite | Automatizada |

**Comprobación visible según aplique — B23-VC01 (obligatoria, NOT_RUN)**

- **Superficie y alcance:** Comando y API. Comparar salida de lotes/reclamación y resultado consultable antes/después de caída, lease vencido y 429; conservar esperas y estado recuperable.
- **Escenarios:** comparar los tres TC anteriores en su interfaz observable; si un escenario no afecta UI, conservar la respuesta/salida en lugar de inventar capturas. Capturar las vistas afectadas por los TC de panel.
- **Modalidad y aplicabilidad:** nuevo → resultado inicial validado contra contrato/AC/TC, sin antes ni diff; modificación → última evidencia aprobada y resultado actual con revisiones y escenario equivalente; sin superficie relevante → No aplica justificado. Una vista sin UI no exige capturas.
- **Artefactos según modalidad:** API nueva: petición/status/JSON/contrato; panel nuevo: capturas del resultado inicial; cambio existente: antes + después + diff o capturas equivalentes; comandos: salida/código inicial o comparado. Completar la [plantilla comparativa](EVIDENCE_COMPARISON_TEMPLATE.md), vinculada a B23-UC01–UC03 y AC01–AC03.
- **Aprobación:** resultado inicial conforme al contrato o diferencias esperadas justificadas y probadas; sin regresiones pendientes. VC01 exige declarar aplicabilidad; No aplica requiere justificación revisada. Es una condición de proceso independiente del porcentaje de AC, sin inflar su denominador. No sustituye tests ni autoriza actualizar la base automáticamente.

**Verificación y salida:** registrar evidencia real UC → AC → TC para la revisión exacta; ejecutar checks y regresión del protocolo; exigir VC01 según su modalidad/aplicabilidad, los tres AC y tests aplicables aprobados y completitud ≥97% sin redondeo. Con 3 AC obligatorios se requiere 3/3. Después: commit candidato → review Standards/Spec → corrección y nueva verificación hasta aprobación → PR para human review. Código simple, tipado y sin comentarios explicativos. No abrir PR ni cerrar B23 solo por tener casillas marcadas.

#### B24 — Vencer QR sin inventar cancelación

**Bloqueado por:** B21.

**Objetivo y entrega:** Vencimiento usa autoridad del servidor; ocultar QR no afirma revocación bancaria ni rechazo.

- **Red:** Reloj móvil distinto y evidencia de pago al vencer no degradan confirmado.
- **Green:** Estado/fecha de expiración QR y respuesta con siguiente acción segura.
- **Refactor:** Separar vencimiento de presentación y recepción bancaria.

**Contrato de verificación:** [Protocolo común](TICKET_QUALITY_PROTOCOL.md). Actor: Operador autorizado. Frontera: HTTP seguimiento y reloj. Dependencias anteriores completadas; datos aislados ficticios y actor autorizado salvo casos negativos. Sin ampliaciones al alcance indicado en el objetivo.

**Casos de uso**

- **B24-UC01:** Operador autorizado: consultar seguimiento cuando se cumple «QR pendiente con expiración del servidor alcanzada», para obtener «Presenta vencimiento y siguiente acción sin afirmar revocación bancaria».
- **B24-UC02:** Operador autorizado: consultar antes del vencimiento del servidor cuando se cumple «Reloj del cliente adelantado/atrasado», para obtener «No cambia estado por reloj móvil».
- **B24-UC03:** Operador autorizado: procesar y consultar cuando se cumple «Intento pagado y evento de vencimiento posterior», para obtener «Sigue confirmado; vencimiento no borra recepción».

**Criterios de aceptación — obligatorios**

- [ ] **B24-AC01:** Presenta vencimiento y siguiente acción sin afirmar revocación bancaria. Verificación: B24-TC01.
- [ ] **B24-AC02:** No cambia estado por reloj móvil. Verificación: B24-TC02.
- [ ] **B24-AC03:** Sigue confirmado; vencimiento no borra recepción. Verificación: B24-TC03.

**Casos de prueba — todos NOT_RUN**

| ID / trazabilidad | Preparación y datos | Acción | Resultado esperado | Ejecución |
| --- | --- | --- | --- | --- |
| B24-TC01 → B24-UC01, B24-AC01 | QR pendiente con expiración del servidor alcanzada | Consultar seguimiento | Presenta vencimiento y siguiente acción sin afirmar revocación bancaria | Automatizada |
| B24-TC02 → B24-UC02, B24-AC02 | Reloj del cliente adelantado/atrasado | Consultar antes del vencimiento del servidor | No cambia estado por reloj móvil | Automatizada |
| B24-TC03 → B24-UC03, B24-AC03 | Intento pagado y evento de vencimiento posterior | Procesar y consultar | Sigue confirmado; vencimiento no borra recepción | Automatizada |

**Comprobación visible según aplique — B24-VC01 (obligatoria, NOT_RUN)**

- **Superficie y alcance:** API vencimiento. Comparar seguimiento antes/después del vencimiento y con reloj móvil distinto; mostrar texto/estado sin afirmar cancelación bancaria ni degradar pagado.
- **Escenarios:** comparar los tres TC anteriores en su interfaz observable; si un escenario no afecta UI, conservar la respuesta/salida en lugar de inventar capturas. Capturar las vistas afectadas por los TC de panel.
- **Modalidad y aplicabilidad:** nuevo → resultado inicial validado contra contrato/AC/TC, sin antes ni diff; modificación → última evidencia aprobada y resultado actual con revisiones y escenario equivalente; sin superficie relevante → No aplica justificado. Una vista sin UI no exige capturas.
- **Artefactos según modalidad:** API nueva: petición/status/JSON/contrato; panel nuevo: capturas del resultado inicial; cambio existente: antes + después + diff o capturas equivalentes; comandos: salida/código inicial o comparado. Completar la [plantilla comparativa](EVIDENCE_COMPARISON_TEMPLATE.md), vinculada a B24-UC01–UC03 y AC01–AC03.
- **Aprobación:** resultado inicial conforme al contrato o diferencias esperadas justificadas y probadas; sin regresiones pendientes. VC01 exige declarar aplicabilidad; No aplica requiere justificación revisada. Es una condición de proceso independiente del porcentaje de AC, sin inflar su denominador. No sustituye tests ni autoriza actualizar la base automáticamente.

**Verificación y salida:** registrar evidencia real UC → AC → TC para la revisión exacta; ejecutar checks y regresión del protocolo; exigir VC01 según su modalidad/aplicabilidad, los tres AC y tests aplicables aprobados y completitud ≥97% sin redondeo. Con 3 AC obligatorios se requiere 3/3. Después: commit candidato → review Standards/Spec → corrección y nueva verificación hasta aprobación → PR para human review. Código simple, tipado y sin comentarios explicativos. No abrir PR ni cerrar B24 solo por tener casillas marcadas.

#### B25 — Reintentar la misma venta con control

**Bloqueado por:** B24, B23.

**Objetivo y entrega:** Tras verificación se permite nuevo intento cuando corresponda, conservando venta/monto y advertencia de pago tardío.

- **Red:** Intento incierto/activo bloquea otro; intento vencido comprobado puede generar uno nuevo sin crear otra venta.
- **Green:** Comando de reintento y vínculos de intentos con validaciones transaccionales.
- **Refactor:** Reusar reserva e idempotencia del primer intento.

**Contrato de verificación:** [Protocolo común](TICKET_QUALITY_PROTOCOL.md). Actor: Operador autorizado. Frontera: HTTP reintentos. Dependencias anteriores completadas; datos aislados ficticios y actor autorizado salvo casos negativos. Sin ampliaciones al alcance indicado en el objetivo.

**Casos de uso**

- **B25-UC01:** Operador autorizado: solicitar reintento y consultar venta cuando se cumple «Venta 30000 con intento vencido comprobado», para obtener «Nuevo intento ligado a misma venta/monto con advertencia de pago tardío».
- **B25-UC02:** Operador autorizado: solicitar nuevo intento cuando se cumple «Intento previo activo o incierto», para obtener «Conflicto; requiere recuperación/verificación previa».
- **B25-UC03:** Operador autorizado: solicitar y consultar cuando se cumple «Dos reintentos concurrentes sobre misma venta», para obtener «Un nuevo intento activo, sin venta adicional».

**Criterios de aceptación — obligatorios**

- [ ] **B25-AC01:** Nuevo intento ligado a misma venta/monto con advertencia de pago tardío. Verificación: B25-TC01.
- [ ] **B25-AC02:** Conflicto; requiere recuperación/verificación previa. Verificación: B25-TC02.
- [ ] **B25-AC03:** Un nuevo intento activo, sin venta adicional. Verificación: B25-TC03.

**Casos de prueba — todos NOT_RUN**

| ID / trazabilidad | Preparación y datos | Acción | Resultado esperado | Ejecución |
| --- | --- | --- | --- | --- |
| B25-TC01 → B25-UC01, B25-AC01 | Venta 30000 con intento vencido comprobado | Solicitar reintento y consultar venta | Nuevo intento ligado a misma venta/monto con advertencia de pago tardío | Automatizada |
| B25-TC02 → B25-UC02, B25-AC02 | Intento previo activo o incierto | Solicitar nuevo intento | Conflicto; requiere recuperación/verificación previa | Automatizada |
| B25-TC03 → B25-UC03, B25-AC03 | Dos reintentos concurrentes sobre misma venta | Solicitar y consultar | Un nuevo intento activo, sin venta adicional | Automatizada |

**Comprobación visible según aplique — B25-VC01 (obligatoria, NOT_RUN)**

- **Superficie y alcance:** API reintentos. Comparar venta e intentos antes/después de reintentar y respuestas de conflicto; destacar mismo importe/venta, nueva referencia de intento y advertencia de pago tardío.
- **Escenarios:** comparar los tres TC anteriores en su interfaz observable; si un escenario no afecta UI, conservar la respuesta/salida en lugar de inventar capturas. Capturar las vistas afectadas por los TC de panel.
- **Modalidad y aplicabilidad:** nuevo → resultado inicial validado contra contrato/AC/TC, sin antes ni diff; modificación → última evidencia aprobada y resultado actual con revisiones y escenario equivalente; sin superficie relevante → No aplica justificado. Una vista sin UI no exige capturas.
- **Artefactos según modalidad:** API nueva: petición/status/JSON/contrato; panel nuevo: capturas del resultado inicial; cambio existente: antes + después + diff o capturas equivalentes; comandos: salida/código inicial o comparado. Completar la [plantilla comparativa](EVIDENCE_COMPARISON_TEMPLATE.md), vinculada a B25-UC01–UC03 y AC01–AC03.
- **Aprobación:** resultado inicial conforme al contrato o diferencias esperadas justificadas y probadas; sin regresiones pendientes. VC01 exige declarar aplicabilidad; No aplica requiere justificación revisada. Es una condición de proceso independiente del porcentaje de AC, sin inflar su denominador. No sustituye tests ni autoriza actualizar la base automáticamente.

**Verificación y salida:** registrar evidencia real UC → AC → TC para la revisión exacta; ejecutar checks y regresión del protocolo; exigir VC01 según su modalidad/aplicabilidad, los tres AC y tests aplicables aprobados y completitud ≥97% sin redondeo. Con 3 AC obligatorios se requiere 3/3. Después: commit candidato → review Standards/Spec → corrección y nueva verificación hasta aprobación → PR para human review. Código simple, tipado y sin comentarios explicativos. No abrir PR ni cerrar B25 solo por tener casillas marcadas.

#### B26 — Registrar pago tardío y doble recepción

**Bloqueado por:** B25, B20.

**Objetivo y entrega:** Pago auténtico de intento anterior se registra; dos transferencias distintas se conservan y abren incidencia.

- **Red:** Venta 300 con dos transferencias de 300 muestra 600 recibidos, una venta cubierta y revisión.
- **Green:** Reglas de pagos tardíos, segunda recepción y retirada de nueva presentación sin prometer revocación.
- **Refactor:** Reusar aplicación de evidencia sin excepciones especiales por canal.

**Contrato de verificación:** [Protocolo común](TICKET_QUALITY_PROTOCOL.md). Actor: Operador y revisor. Frontera: Evidencia y consultas. Dependencias anteriores completadas; datos aislados ficticios y actor autorizado salvo casos negativos. Sin ampliaciones al alcance indicado en el objetivo.

**Casos de uso**

- **B26-UC01:** Operador y revisor: entregar pago auténtico al intento viejo cuando se cumple «Venta 30000 con intento viejo vencido», para obtener «Recepción conservada y venta cubierta pese al vencimiento».
- **B26-UC02:** Operador y revisor: aplicar y consultar detalle/resumen cuando se cumple «Dos transferencias distintas de 30000 para una venta», para obtener «60000 recibidos, una venta cubierta e incidencia visible».
- **B26-UC03:** Operador y revisor: consultar presentación y repetir evidencia cuando se cumple «Nuevo intento visible cuando se confirma el anterior», para obtener «Nueva presentación se retira sin prometer cancelación; dinero no se duplica».

**Criterios de aceptación — obligatorios**

- [ ] **B26-AC01:** Recepción conservada y venta cubierta pese al vencimiento. Verificación: B26-TC01.
- [ ] **B26-AC02:** 60000 recibidos, una venta cubierta e incidencia visible. Verificación: B26-TC02.
- [ ] **B26-AC03:** Nueva presentación se retira sin prometer cancelación; dinero no se duplica. Verificación: B26-TC03.

**Casos de prueba — todos NOT_RUN**

| ID / trazabilidad | Preparación y datos | Acción | Resultado esperado | Ejecución |
| --- | --- | --- | --- | --- |
| B26-TC01 → B26-UC01, B26-AC01 | Venta 30000 con intento viejo vencido | Entregar pago auténtico al intento viejo | Recepción conservada y venta cubierta pese al vencimiento | Automatizada |
| B26-TC02 → B26-UC02, B26-AC02 | Dos transferencias distintas de 30000 para una venta | Aplicar y consultar detalle/resumen | 60000 recibidos, una venta cubierta e incidencia visible | Automatizada |
| B26-TC03 → B26-UC03, B26-AC03 | Nuevo intento visible cuando se confirma el anterior | Consultar presentación y repetir evidencia | Nueva presentación se retira sin prometer cancelación; dinero no se duplica | Automatizada |

**Comprobación visible según aplique — B26-VC01 (obligatoria, NOT_RUN)**

- **Superficie y alcance:** API pago tardío. Comparar detalle y resumen antes/después de pago viejo y doble recepción: 60000 recibidos, una venta cubierta e incidencia, con retirada de nueva presentación.
- **Escenarios:** comparar los tres TC anteriores en su interfaz observable; si un escenario no afecta UI, conservar la respuesta/salida en lugar de inventar capturas. Capturar las vistas afectadas por los TC de panel.
- **Modalidad y aplicabilidad:** nuevo → resultado inicial validado contra contrato/AC/TC, sin antes ni diff; modificación → última evidencia aprobada y resultado actual con revisiones y escenario equivalente; sin superficie relevante → No aplica justificado. Una vista sin UI no exige capturas.
- **Artefactos según modalidad:** API nueva: petición/status/JSON/contrato; panel nuevo: capturas del resultado inicial; cambio existente: antes + después + diff o capturas equivalentes; comandos: salida/código inicial o comparado. Completar la [plantilla comparativa](EVIDENCE_COMPARISON_TEMPLATE.md), vinculada a B26-UC01–UC03 y AC01–AC03.
- **Aprobación:** resultado inicial conforme al contrato o diferencias esperadas justificadas y probadas; sin regresiones pendientes. VC01 exige declarar aplicabilidad; No aplica requiere justificación revisada. Es una condición de proceso independiente del porcentaje de AC, sin inflar su denominador. No sustituye tests ni autoriza actualizar la base automáticamente.

**Verificación y salida:** registrar evidencia real UC → AC → TC para la revisión exacta; ejecutar checks y regresión del protocolo; exigir VC01 según su modalidad/aplicabilidad, los tres AC y tests aplicables aprobados y completitud ≥97% sin redondeo. Con 3 AC obligatorios se requiere 3/3. Después: commit candidato → review Standards/Spec → corrección y nueva verificación hasta aprobación → PR para human review. Código simple, tipado y sin comentarios explicativos. No abrir PR ni cerrar B26 solo por tener casillas marcadas.

### H6 — Consultar y operar el negocio

#### B27 — Consultar historial paginado

**Bloqueado por:** B18.

**Objetivo y entrega:** Operador recorre cobros con estados, fecha e importe; filtros de estado no mezclan comercios ni duplican filas por intentos.

- **Red:** Página siguiente estable, pendientes separados y filtros/IDs manipulados no exponen otro negocio.
- **Green:** Listado con orden estable, límites de página y filtros de estado/fecha.
- **Refactor:** Compartir lectura autorizada con detalle y futuras tablas admin.

**Contrato de verificación:** [Protocolo común](TICKET_QUALITY_PROTOCOL.md). Actor: Operador autorizado. Frontera: HTTP historial. Dependencias anteriores completadas; datos aislados ficticios y actor autorizado salvo casos negativos. Sin ampliaciones al alcance indicado en el objetivo.

**Casos de uso**

- **B27-UC01:** Operador autorizado: consultar páginas consecutivas cuando se cumple «Operaciones con fechas distintas y límite de página 2», para obtener «Orden estable, sin repetir/omitir filas por intentos».
- **B27-UC02:** Operador autorizado: solicitar historial cuando se cumple «Filtro inválido, límite excesivo o comercio ajeno», para obtener «Entrada rechazada/acotada según contrato; no expone otro comercio».
- **B27-UC03:** Operador autorizado: filtrar por estado y recorrer páginas cuando se cumple «Venta con dos intentos y un pendiente adicional», para obtener «Una fila por cobro y estados correctos; pendientes separados de confirmados».

**Criterios de aceptación — obligatorios**

- [ ] **B27-AC01:** Orden estable, sin repetir/omitir filas por intentos. Verificación: B27-TC01.
- [ ] **B27-AC02:** Entrada rechazada/acotada según contrato; no expone otro comercio. Verificación: B27-TC02.
- [ ] **B27-AC03:** Una fila por cobro y estados correctos; pendientes separados de confirmados. Verificación: B27-TC03.

**Casos de prueba — todos NOT_RUN**

| ID / trazabilidad | Preparación y datos | Acción | Resultado esperado | Ejecución |
| --- | --- | --- | --- | --- |
| B27-TC01 → B27-UC01, B27-AC01 | Operaciones con fechas distintas y límite de página 2 | Consultar páginas consecutivas | Orden estable, sin repetir/omitir filas por intentos | Automatizada |
| B27-TC02 → B27-UC02, B27-AC02 | Filtro inválido, límite excesivo o comercio ajeno | Solicitar historial | Entrada rechazada/acotada según contrato; no expone otro comercio | Automatizada |
| B27-TC03 → B27-UC03, B27-AC03 | Venta con dos intentos y un pendiente adicional | Filtrar por estado y recorrer páginas | Una fila por cobro y estados correctos; pendientes separados de confirmados | Automatizada |

**Comprobación visible según aplique — B27-VC01 (obligatoria, NOT_RUN)**

- **Superficie y alcance:** API historial. Comparar páginas y filtros equivalentes con orden y fixtures estables; no ordenar listas al normalizar ni esconder duplicación de filas o exposición entre comercios.
- **Escenarios:** comparar los tres TC anteriores en su interfaz observable; si un escenario no afecta UI, conservar la respuesta/salida en lugar de inventar capturas. Capturar las vistas afectadas por los TC de panel.
- **Modalidad y aplicabilidad:** nuevo → resultado inicial validado contra contrato/AC/TC, sin antes ni diff; modificación → última evidencia aprobada y resultado actual con revisiones y escenario equivalente; sin superficie relevante → No aplica justificado. Una vista sin UI no exige capturas.
- **Artefactos según modalidad:** API nueva: petición/status/JSON/contrato; panel nuevo: capturas del resultado inicial; cambio existente: antes + después + diff o capturas equivalentes; comandos: salida/código inicial o comparado. Completar la [plantilla comparativa](EVIDENCE_COMPARISON_TEMPLATE.md), vinculada a B27-UC01–UC03 y AC01–AC03.
- **Aprobación:** resultado inicial conforme al contrato o diferencias esperadas justificadas y probadas; sin regresiones pendientes. VC01 exige declarar aplicabilidad; No aplica requiere justificación revisada. Es una condición de proceso independiente del porcentaje de AC, sin inflar su denominador. No sustituye tests ni autoriza actualizar la base automáticamente.

**Verificación y salida:** registrar evidencia real UC → AC → TC para la revisión exacta; ejecutar checks y regresión del protocolo; exigir VC01 según su modalidad/aplicabilidad, los tres AC y tests aplicables aprobados y completitud ≥97% sin redondeo. Con 3 AC obligatorios se requiere 3/3. Después: commit candidato → review Standards/Spec → corrección y nueva verificación hasta aprobación → PR para human review. Código simple, tipado y sin comentarios explicativos. No abrir PR ni cerrar B27 solo por tener casillas marcadas.

#### B28 — Compartir datos de comprobante verificado

**Bloqueado por:** B18.

**Objetivo y entrega:** API entrega datos del comprobante solo a autorizado y para recepción validada; no requiere generar PDF.

- **Red:** Pendiente/ajeno no produce comprobante confirmado; datos de pagador y secretos quedan fuera.
- **Green:** DTO de comprobante con monto, comercio, fecha y referencias permitidas.
- **Refactor:** Reusar proyección de recepción sin duplicar reglas de confirmación.

**Contrato de verificación:** [Protocolo común](TICKET_QUALITY_PROTOCOL.md). Actor: Operador autorizado. Frontera: HTTP comprobante. Dependencias anteriores completadas; datos aislados ficticios y actor autorizado salvo casos negativos. Sin ampliaciones al alcance indicado en el objetivo.

**Casos de uso**

- **B28-UC01:** Operador autorizado: obtener datos de comprobante cuando se cumple «Transferencia propia validada de 45000», para obtener «Monto, comercio, fecha y referencias permitidas correctos».
- **B28-UC02:** Operador autorizado: solicitar comprobante confirmado cuando se cumple «Cobro pendiente o identificador ajeno», para obtener «No entrega comprobante de recepción inexistente ni datos ajenos».
- **B28-UC03:** Operador autorizado: obtener DTO público autenticado cuando se cumple «Recepción con datos sensibles del proveedor», para obtener «No incluye credenciales ni datos completos del pagador; conserva evidencia útil».

**Criterios de aceptación — obligatorios**

- [ ] **B28-AC01:** Monto, comercio, fecha y referencias permitidas correctos. Verificación: B28-TC01.
- [ ] **B28-AC02:** No entrega comprobante de recepción inexistente ni datos ajenos. Verificación: B28-TC02.
- [ ] **B28-AC03:** No incluye credenciales ni datos completos del pagador; conserva evidencia útil. Verificación: B28-TC03.

**Casos de prueba — todos NOT_RUN**

| ID / trazabilidad | Preparación y datos | Acción | Resultado esperado | Ejecución |
| --- | --- | --- | --- | --- |
| B28-TC01 → B28-UC01, B28-AC01 | Transferencia propia validada de 45000 | Obtener datos de comprobante | Monto, comercio, fecha y referencias permitidas correctos | Automatizada |
| B28-TC02 → B28-UC02, B28-AC02 | Cobro pendiente o identificador ajeno | Solicitar comprobante confirmado | No entrega comprobante de recepción inexistente ni datos ajenos | Automatizada |
| B28-TC03 → B28-UC03, B28-AC03 | Recepción con datos sensibles del proveedor | Obtener DTO público autenticado | No incluye credenciales ni datos completos del pagador; conserva evidencia útil | Automatizada |

**Comprobación visible según aplique — B28-VC01 (obligatoria, NOT_RUN)**

- **Superficie y alcance:** API comprobante. Comparar DTO permitido para confirmado y respuestas para pendiente/ajeno; destacar monto, fecha, referencias y campos sensibles ausentes.
- **Escenarios:** comparar los tres TC anteriores en su interfaz observable; si un escenario no afecta UI, conservar la respuesta/salida en lugar de inventar capturas. Capturar las vistas afectadas por los TC de panel.
- **Modalidad y aplicabilidad:** nuevo → resultado inicial validado contra contrato/AC/TC, sin antes ni diff; modificación → última evidencia aprobada y resultado actual con revisiones y escenario equivalente; sin superficie relevante → No aplica justificado. Una vista sin UI no exige capturas.
- **Artefactos según modalidad:** API nueva: petición/status/JSON/contrato; panel nuevo: capturas del resultado inicial; cambio existente: antes + después + diff o capturas equivalentes; comandos: salida/código inicial o comparado. Completar la [plantilla comparativa](EVIDENCE_COMPARISON_TEMPLATE.md), vinculada a B28-UC01–UC03 y AC01–AC03.
- **Aprobación:** resultado inicial conforme al contrato o diferencias esperadas justificadas y probadas; sin regresiones pendientes. VC01 exige declarar aplicabilidad; No aplica requiere justificación revisada. Es una condición de proceso independiente del porcentaje de AC, sin inflar su denominador. No sustituye tests ni autoriza actualizar la base automáticamente.

**Verificación y salida:** registrar evidencia real UC → AC → TC para la revisión exacta; ejecutar checks y regresión del protocolo; exigir VC01 según su modalidad/aplicabilidad, los tres AC y tests aplicables aprobados y completitud ≥97% sin redondeo. Con 3 AC obligatorios se requiere 3/3. Después: commit candidato → review Standards/Spec → corrección y nueva verificación hasta aprobación → PR para human review. Código simple, tipado y sin comentarios explicativos. No abrir PR ni cerrar B28 solo por tener casillas marcadas.

#### B29 — Consultar resumen diario

**Bloqueado por:** B27, B26.

**Objetivo y entrega:** Total recibido y cantidad de transferencias/ventas se distinguen; pendientes excluidos e incidencias propias visibles.

- **Red:** 300 + 150 y pendiente 200 producen 450, dos transferencias y dos ventas; segunda transferencia no crea otra venta.
- **Green:** Consulta diaria por comercio y datos mínimos del resumen.
- **Refactor:** Centralizar criterio de dinero recibido y fechas.

**Contrato de verificación:** [Protocolo común](TICKET_QUALITY_PROTOCOL.md). Actor: Operador autorizado. Frontera: HTTP resumen diario. Dependencias anteriores completadas; datos aislados ficticios y actor autorizado salvo casos negativos. Sin ampliaciones al alcance indicado en el objetivo.

**Casos de uso**

- **B29-UC01:** Operador autorizado: consultar día cuando se cumple «Recibidos 30000 y 15000; pendiente 20000», para obtener «45000 recibidos, dos transferencias y dos ventas cubiertas».
- **B29-UC02:** Operador autorizado: consultar resumen cuando se cumple «Un día sin transferencias confirmadas», para obtener «Cero recibido y cero transferencias; sin inventar actividad».
- **B29-UC03:** Operador autorizado: consultar resumen e incidencias cuando se cumple «Una venta 30000 con dos transferencias distintas de 30000», para obtener «60000 recibidos, dos transferencias y una venta cubierta con revisión visible».

**Criterios de aceptación — obligatorios**

- [ ] **B29-AC01:** 45000 recibidos, dos transferencias y dos ventas cubiertas. Verificación: B29-TC01.
- [ ] **B29-AC02:** Cero recibido y cero transferencias; sin inventar actividad. Verificación: B29-TC02.
- [ ] **B29-AC03:** 60000 recibidos, dos transferencias y una venta cubierta con revisión visible. Verificación: B29-TC03.

**Casos de prueba — todos NOT_RUN**

| ID / trazabilidad | Preparación y datos | Acción | Resultado esperado | Ejecución |
| --- | --- | --- | --- | --- |
| B29-TC01 → B29-UC01, B29-AC01 | Recibidos 30000 y 15000; pendiente 20000 | Consultar día | 45000 recibidos, dos transferencias y dos ventas cubiertas | Automatizada |
| B29-TC02 → B29-UC02, B29-AC02 | Un día sin transferencias confirmadas | Consultar resumen | Cero recibido y cero transferencias; sin inventar actividad | Automatizada |
| B29-TC03 → B29-UC03, B29-AC03 | Una venta 30000 con dos transferencias distintas de 30000 | Consultar resumen e incidencias | 60000 recibidos, dos transferencias y una venta cubierta con revisión visible | Automatizada |

**Comprobación visible según aplique — B29-VC01 (obligatoria, NOT_RUN)**

- **Superficie y alcance:** API resumen. Comparar total, transferencias, ventas e incidencias usando los mismos movimientos; mostrar explícitamente el efecto de pendientes y segunda transferencia.
- **Escenarios:** comparar los tres TC anteriores en su interfaz observable; si un escenario no afecta UI, conservar la respuesta/salida en lugar de inventar capturas. Capturar las vistas afectadas por los TC de panel.
- **Modalidad y aplicabilidad:** nuevo → resultado inicial validado contra contrato/AC/TC, sin antes ni diff; modificación → última evidencia aprobada y resultado actual con revisiones y escenario equivalente; sin superficie relevante → No aplica justificado. Una vista sin UI no exige capturas.
- **Artefactos según modalidad:** API nueva: petición/status/JSON/contrato; panel nuevo: capturas del resultado inicial; cambio existente: antes + después + diff o capturas equivalentes; comandos: salida/código inicial o comparado. Completar la [plantilla comparativa](EVIDENCE_COMPARISON_TEMPLATE.md), vinculada a B29-UC01–UC03 y AC01–AC03.
- **Aprobación:** resultado inicial conforme al contrato o diferencias esperadas justificadas y probadas; sin regresiones pendientes. VC01 exige declarar aplicabilidad; No aplica requiere justificación revisada. Es una condición de proceso independiente del porcentaje de AC, sin inflar su denominador. No sustituye tests ni autoriza actualizar la base automáticamente.

**Verificación y salida:** registrar evidencia real UC → AC → TC para la revisión exacta; ejecutar checks y regresión del protocolo; exigir VC01 según su modalidad/aplicabilidad, los tres AC y tests aplicables aprobados y completitud ≥97% sin redondeo. Con 3 AC obligatorios se requiere 3/3. Después: commit candidato → review Standards/Spec → corrección y nueva verificación hasta aprobación → PR para human review. Código simple, tipado y sin comentarios explicativos. No abrir PR ni cerrar B29 solo por tener casillas marcadas.

#### B30 — Consultar semana y mes con fechas locales

**Bloqueado por:** B29.

**Objetivo y entrega:** Semana lunes-domingo y mes calendario agrupan en Ciudad de México; evidencia tardía corrige periodo apropiado.

- **Red:** Casos de medianoche, lunes, cambio de mes y fecha bancaria ausente producen periodos esperados.
- **Green:** Rangos explícitos y desglose diario; fallback de fecha documentado.
- **Refactor:** Unificar rangos y semántica temporal sin convertir consultas UI en llamadas bancarias.

**Contrato de verificación:** [Protocolo común](TICKET_QUALITY_PROTOCOL.md). Actor: Operador autorizado. Frontera: HTTP reportes por periodo. Dependencias anteriores completadas; datos aislados ficticios y actor autorizado salvo casos negativos. Sin ampliaciones al alcance indicado en el objetivo.

**Casos de uso**

- **B30-UC01:** Operador autorizado: consultar día/semana/mes cuando se cumple «Movimientos a ambos lados de medianoche de Ciudad de México y lunes», para obtener «Asignación al calendario local y semana lunes-domingo».
- **B30-UC02:** Operador autorizado: consultar periodo y metadatos cuando se cumple «Timestamp bancario ausente en evidencia válida», para obtener «Usa recepción con semántica explícita, sin fecha bancaria inventada».
- **B30-UC03:** Operador autorizado: conciliar y volver a consultar ambos meses cuando se cumple «Pago de fin de mes notificado al mes siguiente», para obtener «Corrige periodo bancario validado una vez sin duplicar en el siguiente».

**Criterios de aceptación — obligatorios**

- [ ] **B30-AC01:** Asignación al calendario local y semana lunes-domingo. Verificación: B30-TC01.
- [ ] **B30-AC02:** Usa recepción con semántica explícita, sin fecha bancaria inventada. Verificación: B30-TC02.
- [ ] **B30-AC03:** Corrige periodo bancario validado una vez sin duplicar en el siguiente. Verificación: B30-TC03.

**Casos de prueba — todos NOT_RUN**

| ID / trazabilidad | Preparación y datos | Acción | Resultado esperado | Ejecución |
| --- | --- | --- | --- | --- |
| B30-TC01 → B30-UC01, B30-AC01 | Movimientos a ambos lados de medianoche de Ciudad de México y lunes | Consultar día/semana/mes | Asignación al calendario local y semana lunes-domingo | Automatizada |
| B30-TC02 → B30-UC02, B30-AC02 | Timestamp bancario ausente en evidencia válida | Consultar periodo y metadatos | Usa recepción con semántica explícita, sin fecha bancaria inventada | Automatizada |
| B30-TC03 → B30-UC03, B30-AC03 | Pago de fin de mes notificado al mes siguiente | Conciliar y volver a consultar ambos meses | Corrige periodo bancario validado una vez sin duplicar en el siguiente | Automatizada |

**Comprobación visible según aplique — B30-VC01 (obligatoria, NOT_RUN)**

- **Superficie y alcance:** API periodos. Comparar día/semana/mes y desglose con fixtures de medianoche/pago tardío; no normalizar fechas que cambien de periodo ni ocultar semántica del fallback.
- **Escenarios:** comparar los tres TC anteriores en su interfaz observable; si un escenario no afecta UI, conservar la respuesta/salida en lugar de inventar capturas. Capturar las vistas afectadas por los TC de panel.
- **Modalidad y aplicabilidad:** nuevo → resultado inicial validado contra contrato/AC/TC, sin antes ni diff; modificación → última evidencia aprobada y resultado actual con revisiones y escenario equivalente; sin superficie relevante → No aplica justificado. Una vista sin UI no exige capturas.
- **Artefactos según modalidad:** API nueva: petición/status/JSON/contrato; panel nuevo: capturas del resultado inicial; cambio existente: antes + después + diff o capturas equivalentes; comandos: salida/código inicial o comparado. Completar la [plantilla comparativa](EVIDENCE_COMPARISON_TEMPLATE.md), vinculada a B30-UC01–UC03 y AC01–AC03.
- **Aprobación:** resultado inicial conforme al contrato o diferencias esperadas justificadas y probadas; sin regresiones pendientes. VC01 exige declarar aplicabilidad; No aplica requiere justificación revisada. Es una condición de proceso independiente del porcentaje de AC, sin inflar su denominador. No sustituye tests ni autoriza actualizar la base automáticamente.

**Verificación y salida:** registrar evidencia real UC → AC → TC para la revisión exacta; ejecutar checks y regresión del protocolo; exigir VC01 según su modalidad/aplicabilidad, los tres AC y tests aplicables aprobados y completitud ≥97% sin redondeo. Con 3 AC obligatorios se requiere 3/3. Después: commit candidato → review Standards/Spec → corrección y nueva verificación hasta aprobación → PR para human review. Código simple, tipado y sin comentarios explicativos. No abrir PR ni cerrar B30 solo por tener casillas marcadas.

#### B31 — Inspeccionar cobros desde back office

**Bloqueado por:** B07, B27, B28.

**Objetivo y entrega:** Admin consulta cobro, intentos, recepción y trazabilidad en tablas; no puede editar/borrar dinero ni forzar recibido.

- **Red:** Operador no entra; endpoints admin manipulados no habilitan CRUD financiero; filtros inválidos son 4xx.
- **Green:** Vistas Starlette Admin de consulta apoyadas en servicios autorizados y paginados.
- **Refactor:** Reusar consultas comunes y mantener adaptación de presentación en admin.

**Contrato de verificación:** [Protocolo común](TICKET_QUALITY_PROTOCOL.md). Actor: Administrador interno. Frontera: HTTP/listados admin. Dependencias anteriores completadas; datos aislados ficticios y actor autorizado salvo casos negativos. Sin ampliaciones al alcance indicado en el objetivo.

**Casos de uso**

- **B31-UC01:** Administrador interno: abrir lista y detalle paginados cuando se cumple «Admin y cobro con intentos/transferencia», para obtener «Trazabilidad visible con importes y estados correctos».
- **B31-UC02:** Administrador interno: intentar entrar/editar/eliminar cuando se cumple «Operador o petición directa de CRUD financiero», para obtener «Acceso o mutación denegados; no se fuerza recibido».
- **B31-UC03:** Administrador interno: consultar listados cuando se cumple «Filtros malformados y página posterior», para obtener «Inválidos producen 4xx y paginación válida recupera resto sin truncamiento oculto».

**Criterios de aceptación — obligatorios**

- [ ] **B31-AC01:** Trazabilidad visible con importes y estados correctos. Verificación: B31-TC01.
- [ ] **B31-AC02:** Acceso o mutación denegados; no se fuerza recibido. Verificación: B31-TC02.
- [ ] **B31-AC03:** Inválidos producen 4xx y paginación válida recupera resto sin truncamiento oculto. Verificación: B31-TC03.

**Casos de prueba — todos NOT_RUN**

| ID / trazabilidad | Preparación y datos | Acción | Resultado esperado | Ejecución |
| --- | --- | --- | --- | --- |
| B31-TC01 → B31-UC01, B31-AC01 | Admin y cobro con intentos/transferencia | Abrir lista y detalle paginados | Trazabilidad visible con importes y estados correctos | Automatizada |
| B31-TC02 → B31-UC02, B31-AC02 | Operador o petición directa de CRUD financiero | Intentar entrar/editar/eliminar | Acceso o mutación denegados; no se fuerza recibido | Automatizada |
| B31-TC03 → B31-UC03, B31-AC03 | Filtros malformados y página posterior | Consultar listados | Inválidos producen 4xx y paginación válida recupera resto sin truncamiento oculto | Automatizada |

**Comprobación visible según aplique — B31-VC01 (obligatoria, NOT_RUN)**

- **Superficie y alcance:** API y panel. Comparar capturas de listado/detalle/página siguiente y filtros inválidos como admin; adjuntar respuestas que rechazan acceso de operador y CRUD financiero manipulado.
- **Escenarios:** comparar los tres TC anteriores en su interfaz observable; si un escenario no afecta UI, conservar la respuesta/salida en lugar de inventar capturas. Capturar las vistas afectadas por los TC de panel.
- **Modalidad y aplicabilidad:** nuevo → resultado inicial validado contra contrato/AC/TC, sin antes ni diff; modificación → última evidencia aprobada y resultado actual con revisiones y escenario equivalente; sin superficie relevante → No aplica justificado. Una vista sin UI no exige capturas.
- **Artefactos según modalidad:** API nueva: petición/status/JSON/contrato; panel nuevo: capturas del resultado inicial; cambio existente: antes + después + diff o capturas equivalentes; comandos: salida/código inicial o comparado. Completar la [plantilla comparativa](EVIDENCE_COMPARISON_TEMPLATE.md), vinculada a B31-UC01–UC03 y AC01–AC03.
- **Aprobación:** resultado inicial conforme al contrato o diferencias esperadas justificadas y probadas; sin regresiones pendientes. VC01 exige declarar aplicabilidad; No aplica requiere justificación revisada. Es una condición de proceso independiente del porcentaje de AC, sin inflar su denominador. No sustituye tests ni autoriza actualizar la base automáticamente.

**Verificación y salida:** registrar evidencia real UC → AC → TC para la revisión exacta; ejecutar checks y regresión del protocolo; exigir VC01 según su modalidad/aplicabilidad, los tres AC y tests aplicables aprobados y completitud ≥97% sin redondeo. Con 3 AC obligatorios se requiere 3/3. Después: commit candidato → review Standards/Spec → corrección y nueva verificación hasta aprobación → PR para human review. Código simple, tipado y sin comentarios explicativos. No abrir PR ni cerrar B31 solo por tener casillas marcadas.

#### B32 — Revisar incidencias desde back office

**Bloqueado por:** B31, B20, B23.

**Objetivo y entrega:** Admin inspecciona incidencia y solicita conciliación; puede anotar seguimiento sin alterar evidencia financiera.

- **Red:** Repetir acción no duplica trabajo; anotación no marca cobro pagado ni elimina transferencia.
- **Green:** Vista/acción admin con permisos, CSRF y auditoría de seguimiento; resolución monetaria manual fuera de alcance.
- **Refactor:** Compartir casos de uso con API sin acceso CRUD directo al registro financiero.

**Contrato de verificación:** [Protocolo común](TICKET_QUALITY_PROTOCOL.md). Actor: Administrador revisor. Frontera: Formulario/acción admin y consulta. Dependencias anteriores completadas; datos aislados ficticios y actor autorizado salvo casos negativos. Sin ampliaciones al alcance indicado en el objetivo.

**Casos de uso**

- **B32-UC01:** Administrador revisor: anotar seguimiento y solicitar conciliación cuando se cumple «Incidencia propia y admin válido con CSRF», para obtener «Nota auditada y trabajo recuperable sin cambiar dinero manualmente».
- **B32-UC02:** Administrador revisor: enviar acción cuando se cumple «Operador o admin con CSRF inválido», para obtener «Sin nota/trabajo ni cambio monetario».
- **B32-UC03:** Administrador revisor: ejecutar acción dos veces y consultar seguimiento cuando se cumple «Doble envío de solicitar conciliación», para obtener «Un trabajo lógico sin duplicado; evidencia original intacta».

**Criterios de aceptación — obligatorios**

- [ ] **B32-AC01:** Nota auditada y trabajo recuperable sin cambiar dinero manualmente. Verificación: B32-TC01.
- [ ] **B32-AC02:** Sin nota/trabajo ni cambio monetario. Verificación: B32-TC02.
- [ ] **B32-AC03:** Un trabajo lógico sin duplicado; evidencia original intacta. Verificación: B32-TC03.

**Casos de prueba — todos NOT_RUN**

| ID / trazabilidad | Preparación y datos | Acción | Resultado esperado | Ejecución |
| --- | --- | --- | --- | --- |
| B32-TC01 → B32-UC01, B32-AC01 | Incidencia propia y admin válido con CSRF | Anotar seguimiento y solicitar conciliación | Nota auditada y trabajo recuperable sin cambiar dinero manualmente | Automatizada |
| B32-TC02 → B32-UC02, B32-AC02 | Operador o admin con CSRF inválido | Enviar acción | Sin nota/trabajo ni cambio monetario | Automatizada |
| B32-TC03 → B32-UC03, B32-AC03 | Doble envío de solicitar conciliación | Ejecutar acción dos veces y consultar seguimiento | Un trabajo lógico sin duplicado; evidencia original intacta | Automatizada |

**Comprobación visible según aplique — B32-VC01 (obligatoria, NOT_RUN)**

- **Superficie y alcance:** API y panel. Comparar incidencia, nota y resultado de solicitar conciliación antes/después y con doble envío; mostrar rechazo CSRF y que ninguna acción manual acredita dinero.
- **Escenarios:** comparar los tres TC anteriores en su interfaz observable; si un escenario no afecta UI, conservar la respuesta/salida en lugar de inventar capturas. Capturar las vistas afectadas por los TC de panel.
- **Modalidad y aplicabilidad:** nuevo → resultado inicial validado contra contrato/AC/TC, sin antes ni diff; modificación → última evidencia aprobada y resultado actual con revisiones y escenario equivalente; sin superficie relevante → No aplica justificado. Una vista sin UI no exige capturas.
- **Artefactos según modalidad:** API nueva: petición/status/JSON/contrato; panel nuevo: capturas del resultado inicial; cambio existente: antes + después + diff o capturas equivalentes; comandos: salida/código inicial o comparado. Completar la [plantilla comparativa](EVIDENCE_COMPARISON_TEMPLATE.md), vinculada a B32-UC01–UC03 y AC01–AC03.
- **Aprobación:** resultado inicial conforme al contrato o diferencias esperadas justificadas y probadas; sin regresiones pendientes. VC01 exige declarar aplicabilidad; No aplica requiere justificación revisada. Es una condición de proceso independiente del porcentaje de AC, sin inflar su denominador. No sustituye tests ni autoriza actualizar la base automáticamente.

**Verificación y salida:** registrar evidencia real UC → AC → TC para la revisión exacta; ejecutar checks y regresión del protocolo; exigir VC01 según su modalidad/aplicabilidad, los tres AC y tests aplicables aprobados y completitud ≥97% sin redondeo. Con 3 AC obligatorios se requiere 3/3. Después: commit candidato → review Standards/Spec → corrección y nueva verificación hasta aprobación → PR para human review. Código simple, tipado y sin comentarios explicativos. No abrir PR ni cerrar B32 solo por tener casillas marcadas.

### H7 — Operación e integración comprobable

#### B33 — Limitar creación y consultas externas

**Bloqueado por:** B16, B23.

**Objetivo y entrega:** Cuotas persistentes por actor/comercio/operación limitan abuso; consulta normal de estado no llama al proveedor.

- **Red:** Concurrencia sobre cuota devuelve 429 al exceder; muchas lecturas no multiplican solicitudes bancarias.
- **Green:** Reservas atómicas, límites de paginación/cuerpo y política de espera configurables.
- **Refactor:** Concentrar cuotas evitando contadores locales por proceso.

**Contrato de verificación:** [Protocolo común](TICKET_QUALITY_PROTOCOL.md). Actor: Operador y operación. Frontera: HTTP cuotas y frontera proveedor. Dependencias anteriores completadas; datos aislados ficticios y actor autorizado salvo casos negativos. Sin ampliaciones al alcance indicado en el objetivo.

**Casos de uso**

- **B33-UC01:** Operador y operación: crear hasta límite y solicitar otra cuando se cumple «Cuota de creación definida para comercio A», para obtener «Dentro del límite opera; al exceder 429 con orientación de espera».
- **B33-UC02:** Operador y operación: enviar creación simultánea cuando se cumple «Peticiones concurrentes cruzan límite», para obtener «Reserva persistente impide exceder cuota autorizada».
- **B33-UC03:** Operador y operación: leer estado y observar frontera externa del simulador cuando se cumple «Un intento pendiente consultado muchas veces», para obtener «Lecturas usan estado propio, sin una llamada bancaria por cada consulta».

**Criterios de aceptación — obligatorios**

- [ ] **B33-AC01:** Dentro del límite opera; al exceder 429 con orientación de espera. Verificación: B33-TC01.
- [ ] **B33-AC02:** Reserva persistente impide exceder cuota autorizada. Verificación: B33-TC02.
- [ ] **B33-AC03:** Lecturas usan estado propio, sin una llamada bancaria por cada consulta. Verificación: B33-TC03.

**Casos de prueba — todos NOT_RUN**

| ID / trazabilidad | Preparación y datos | Acción | Resultado esperado | Ejecución |
| --- | --- | --- | --- | --- |
| B33-TC01 → B33-UC01, B33-AC01 | Cuota de creación definida para comercio A | Crear hasta límite y solicitar otra | Dentro del límite opera; al exceder 429 con orientación de espera | Automatizada |
| B33-TC02 → B33-UC02, B33-AC02 | Peticiones concurrentes cruzan límite | Enviar creación simultánea | Reserva persistente impide exceder cuota autorizada | Automatizada |
| B33-TC03 → B33-UC03, B33-AC03 | Un intento pendiente consultado muchas veces | Leer estado y observar frontera externa del simulador | Lecturas usan estado propio, sin una llamada bancaria por cada consulta | Automatizada |

**Comprobación visible según aplique — B33-VC01 (obligatoria, NOT_RUN)**

- **Superficie y alcance:** API cuotas. Comparar respuestas antes del límite y al excederlo, orientación de espera y resultados concurrentes; adjuntar evidencia del simulador de que leer estado no dispara pagos.
- **Escenarios:** comparar los tres TC anteriores en su interfaz observable; si un escenario no afecta UI, conservar la respuesta/salida en lugar de inventar capturas. Capturar las vistas afectadas por los TC de panel.
- **Modalidad y aplicabilidad:** nuevo → resultado inicial validado contra contrato/AC/TC, sin antes ni diff; modificación → última evidencia aprobada y resultado actual con revisiones y escenario equivalente; sin superficie relevante → No aplica justificado. Una vista sin UI no exige capturas.
- **Artefactos según modalidad:** API nueva: petición/status/JSON/contrato; panel nuevo: capturas del resultado inicial; cambio existente: antes + después + diff o capturas equivalentes; comandos: salida/código inicial o comparado. Completar la [plantilla comparativa](EVIDENCE_COMPARISON_TEMPLATE.md), vinculada a B33-UC01–UC03 y AC01–AC03.
- **Aprobación:** resultado inicial conforme al contrato o diferencias esperadas justificadas y probadas; sin regresiones pendientes. VC01 exige declarar aplicabilidad; No aplica requiere justificación revisada. Es una condición de proceso independiente del porcentaje de AC, sin inflar su denominador. No sustituye tests ni autoriza actualizar la base automáticamente.

**Verificación y salida:** registrar evidencia real UC → AC → TC para la revisión exacta; ejecutar checks y regresión del protocolo; exigir VC01 según su modalidad/aplicabilidad, los tres AC y tests aplicables aprobados y completitud ≥97% sin redondeo. Con 3 AC obligatorios se requiere 3/3. Después: commit candidato → review Standards/Spec → corrección y nueva verificación hasta aprobación → PR para human review. Código simple, tipado y sin comentarios explicativos. No abrir PR ni cerrar B33 solo por tener casillas marcadas.

#### B34 — Diagnosticar y restaurar operación

**Bloqueado por:** B23, B31.

**Objetivo y entrega:** Errores tienen referencia correlacionable sin secretos; guía permite respaldo/restauración de datos de prueba y recuperar pendientes.

- **Red:** Error provocado conserva referencia sin token/teléfono completo; restauración recupera consulta y trabajo pendiente.
- **Green:** Logs seguros, errores consistentes, indicadores de atraso y procedimiento probado con base desechable.
- **Refactor:** Unificar redacción de datos sensibles y formato de errores.

**Contrato de verificación:** [Protocolo común](TICKET_QUALITY_PROTOCOL.md). Actor: Responsable operativo. Frontera: Comandos y respuestas/logs. Dependencias anteriores completadas; datos aislados ficticios y actor autorizado salvo casos negativos. Sin ampliaciones al alcance indicado en el objetivo.

**Casos de uso**

- **B34-UC01:** Responsable operativo: consultar respuesta y registro sanitizado cuando se cumple «Error simulado con datos sensibles de test», para obtener «Referencia correlacionable sin token, CLABE ni teléfono completo».
- **B34-UC02:** Responsable operativo: restaurar en DB nueva y consultar cuando se cumple «Respaldo desechable con cobro y trabajo pendiente», para obtener «Datos y pendiente recuperables, sin usar DB productiva».
- **B34-UC03:** Responsable operativo: reanudar y consultar resultado cuando se cumple «Ejecutor interrumpido después de restaurar», para obtener «Trabajo concluye una vez y diagnóstico permite seguir referencia».

**Criterios de aceptación — obligatorios**

- [ ] **B34-AC01:** Referencia correlacionable sin token, CLABE ni teléfono completo. Verificación: B34-TC01.
- [ ] **B34-AC02:** Datos y pendiente recuperables, sin usar DB productiva. Verificación: B34-TC02.
- [ ] **B34-AC03:** Trabajo concluye una vez y diagnóstico permite seguir referencia. Verificación: B34-TC03.

**Casos de prueba — todos NOT_RUN**

| ID / trazabilidad | Preparación y datos | Acción | Resultado esperado | Ejecución |
| --- | --- | --- | --- | --- |
| B34-TC01 → B34-UC01, B34-AC01 | Error simulado con datos sensibles de test | Consultar respuesta y registro sanitizado | Referencia correlacionable sin token, CLABE ni teléfono completo | Automatizada |
| B34-TC02 → B34-UC02, B34-AC02 | Respaldo desechable con cobro y trabajo pendiente | Restaurar en DB nueva y consultar | Datos y pendiente recuperables, sin usar DB productiva | Automatizada |
| B34-TC03 → B34-UC03, B34-AC03 | Ejecutor interrumpido después de restaurar | Reanudar y consultar resultado | Trabajo concluye una vez y diagnóstico permite seguir referencia | Automatizada |

**Comprobación visible según aplique — B34-VC01 (obligatoria, NOT_RUN)**

- **Superficie y alcance:** Comandos y API. Comparar error sanitizado, logs correlacionables y lecturas antes/después de restaurar y reanudar pendientes; no publicar respaldo ni datos bancarios reales.
- **Escenarios:** comparar los tres TC anteriores en su interfaz observable; si un escenario no afecta UI, conservar la respuesta/salida en lugar de inventar capturas. Capturar las vistas afectadas por los TC de panel.
- **Modalidad y aplicabilidad:** nuevo → resultado inicial validado contra contrato/AC/TC, sin antes ni diff; modificación → última evidencia aprobada y resultado actual con revisiones y escenario equivalente; sin superficie relevante → No aplica justificado. Una vista sin UI no exige capturas.
- **Artefactos según modalidad:** API nueva: petición/status/JSON/contrato; panel nuevo: capturas del resultado inicial; cambio existente: antes + después + diff o capturas equivalentes; comandos: salida/código inicial o comparado. Completar la [plantilla comparativa](EVIDENCE_COMPARISON_TEMPLATE.md), vinculada a B34-UC01–UC03 y AC01–AC03.
- **Aprobación:** resultado inicial conforme al contrato o diferencias esperadas justificadas y probadas; sin regresiones pendientes. VC01 exige declarar aplicabilidad; No aplica requiere justificación revisada. Es una condición de proceso independiente del porcentaje de AC, sin inflar su denominador. No sustituye tests ni autoriza actualizar la base automáticamente.

**Verificación y salida:** registrar evidencia real UC → AC → TC para la revisión exacta; ejecutar checks y regresión del protocolo; exigir VC01 según su modalidad/aplicabilidad, los tres AC y tests aplicables aprobados y completitud ≥97% sin redondeo. Con 3 AC obligatorios se requiere 3/3. Después: commit candidato → review Standards/Spec → corrección y nueva verificación hasta aprobación → PR para human review. Código simple, tipado y sin comentarios explicativos. No abrir PR ni cerrar B34 solo por tener casillas marcadas.

#### B35 — Verificar QR real de extremo a extremo

**Bloqueado por:** B15, B26, B30, B33, B34.

**Objetivo y entrega:** Prueba autorizada liga QR real, evidencia, detalle, historial y resumen; si faltan accesos se registra bloqueada.

- **Red:** Ensayar primero el mismo recorrido en simulación con pérdida de red y evidencia repetida.
- **Green:** Ejecutar prueba real pequeña autorizada y documentar resultado sanitizado; no activar desde CI.
- **Refactor:** Ajustar únicamente lo demostrado por hallazgos y repetir regresión afectada.

**Contrato de verificación:** [Protocolo común](TICKET_QUALITY_PROTOCOL.md). Actor: Equipo autorizado. Frontera: Recorrido externo y HTTP. Dependencias anteriores completadas; datos aislados ficticios y actor autorizado salvo casos negativos. Sin ampliaciones al alcance indicado en el objetivo.

**Casos de uso**

- **B35-UC01:** Equipo autorizado: crear QR, pagar importe acordado y consultar detalle/historial/resumen cuando se cumple «Participantes, receptor activo y acceso real autorizados», para obtener «Evidencia bancaria auténtica correlacionada y mismo importe recibido una vez».
- **B35-UC02:** Equipo autorizado: preparar ejecución de prueba real cuando se cumple «Sin acceso o receptor habilitado», para obtener «Resultado BLOCKED; simulación no se presenta como integración aprobada».
- **B35-UC03:** Equipo autorizado: recuperar app/API y volver a consultar cuando se cumple «Ensayo sintético con desconexión y evento repetido antes de prueba real», para obtener «Una recepción conservada; evidencia real posterior queda sanitizada y separada».

**Criterios de aceptación — obligatorios**

- [ ] **B35-AC01:** Evidencia bancaria auténtica correlacionada y mismo importe recibido una vez. Verificación: B35-TC01.
- [ ] **B35-AC02:** Resultado BLOCKED; simulación no se presenta como integración aprobada. Verificación: B35-TC02.
- [ ] **B35-AC03:** Una recepción conservada; evidencia real posterior queda sanitizada y separada. Verificación: B35-TC03.

**Casos de prueba — todos NOT_RUN**

| ID / trazabilidad | Preparación y datos | Acción | Resultado esperado | Ejecución |
| --- | --- | --- | --- | --- |
| B35-TC01 → B35-UC01, B35-AC01 | Participantes, receptor activo y acceso real autorizados | Crear QR, pagar importe acordado y consultar detalle/historial/resumen | Evidencia bancaria auténtica correlacionada y mismo importe recibido una vez | Externa autorizada / manual |
| B35-TC02 → B35-UC02, B35-AC02 | Sin acceso o receptor habilitado | Preparar ejecución de prueba real | Resultado BLOCKED; simulación no se presenta como integración aprobada | Externa autorizada / manual |
| B35-TC03 → B35-UC03, B35-AC03 | Ensayo sintético con desconexión y evento repetido antes de prueba real | Recuperar app/API y volver a consultar | Una recepción conservada; evidencia real posterior queda sanitizada y separada | Automatizada |

**Comprobación visible según aplique — B35-VC01 (obligatoria, NOT_RUN)**

- **Superficie y alcance:** Recorrido externo y API. Comparar QR/pendiente con recepción real, detalle/historial/resumen posteriores mediante evidencia sanitizada y correlacionada; sin acceso, mostrar BLOCKED sin inventar ejecución ni captura bancaria previa.
- **Escenarios:** comparar los tres TC anteriores en su interfaz observable; si un escenario no afecta UI, conservar la respuesta/salida en lugar de inventar capturas. Capturar las vistas afectadas por los TC de panel.
- **Modalidad y aplicabilidad:** nuevo → resultado inicial validado contra contrato/AC/TC, sin antes ni diff; modificación → última evidencia aprobada y resultado actual con revisiones y escenario equivalente; sin superficie relevante → No aplica justificado. Una vista sin UI no exige capturas.
- **Artefactos según modalidad:** API nueva: petición/status/JSON/contrato; panel nuevo: capturas del resultado inicial; cambio existente: antes + después + diff o capturas equivalentes; comandos: salida/código inicial o comparado. Completar la [plantilla comparativa](EVIDENCE_COMPARISON_TEMPLATE.md), vinculada a B35-UC01–UC03 y AC01–AC03.
- **Aprobación:** resultado inicial conforme al contrato o diferencias esperadas justificadas y probadas; sin regresiones pendientes. VC01 exige declarar aplicabilidad; No aplica requiere justificación revisada. Es una condición de proceso independiente del porcentaje de AC, sin inflar su denominador. No sustituye tests ni autoriza actualizar la base automáticamente.

**Verificación y salida:** registrar evidencia real UC → AC → TC para la revisión exacta; ejecutar checks y regresión del protocolo; exigir VC01 según su modalidad/aplicabilidad, los tres AC y tests aplicables aprobados y completitud ≥97% sin redondeo. Con 3 AC obligatorios se requiere 3/3. Después: commit candidato → review Standards/Spec → corrección y nueva verificación hasta aprobación → PR para human review. Código simple, tipado y sin comentarios explicativos. No abrir PR ni cerrar B35 solo por tener casillas marcadas.

### H8 — Canales adicionales y contrato para clientes

#### B36 — Crear solicitud al celular

**Bloqueado por:** B13, B16, B33.

**Objetivo y entrega:** Número válido autorizado genera intento pendiente; proveedor aceptó no significa entregado/leído/pagado.

- **Red:** Número inválido no sale; respuesta aceptada sigue pendiente; timeout conserva incertidumbre.
- **Green:** Adaptador de canal, API tipada y fixtures oficiales; habilitación condicionada a contrato/recuperación verificables.
- **Refactor:** Reusar motor de intentos y aislar formato del número.

**Contrato de verificación:** [Protocolo común](TICKET_QUALITY_PROTOCOL.md). Actor: Operador autorizado. Frontera: HTTP celular y contrato pey. Dependencias anteriores completadas; datos aislados ficticios y actor autorizado salvo casos negativos. Sin ampliaciones al alcance indicado en el objetivo.

**Casos de uso**

- **B36-UC01:** Operador autorizado: crear solicitud al celular cuando se cumple «Número de prueba consentido y receptor activo», para obtener «ID y referencia conservados, estado pendiente sin afirmar lectura/entrega».
- **B36-UC02:** Operador autorizado: crear solicitud cuando se cumple «Número inválido o número no permitido en demo», para obtener «Error sin solicitud al proveedor».
- **B36-UC03:** Operador autorizado: repetir con misma clave y consultar cuando se cumple «Proveedor acepta pero respuesta se pierde», para obtener «Mismo intento verificando, sin nueva emisión a ciegas».

**Criterios de aceptación — obligatorios**

- [ ] **B36-AC01:** ID y referencia conservados, estado pendiente sin afirmar lectura/entrega. Verificación: B36-TC01.
- [ ] **B36-AC02:** Error sin solicitud al proveedor. Verificación: B36-TC02.
- [ ] **B36-AC03:** Mismo intento verificando, sin nueva emisión a ciegas. Verificación: B36-TC03.

**Casos de prueba — todos NOT_RUN**

| ID / trazabilidad | Preparación y datos | Acción | Resultado esperado | Ejecución |
| --- | --- | --- | --- | --- |
| B36-TC01 → B36-UC01, B36-AC01 | Número de prueba consentido y receptor activo | Crear solicitud al celular | ID y referencia conservados, estado pendiente sin afirmar lectura/entrega | Automatizada |
| B36-TC02 → B36-UC02, B36-AC02 | Número inválido o número no permitido en demo | Crear solicitud | Error sin solicitud al proveedor | Automatizada |
| B36-TC03 → B36-UC03, B36-AC03 | Proveedor acepta pero respuesta se pierde | Repetir con misma clave y consultar | Mismo intento verificando, sin nueva emisión a ciegas | Automatizada |

**Comprobación visible según aplique — B36-VC01 (obligatoria, NOT_RUN)**

- **Superficie y alcance:** API celular. Comparar creación, número inválido y timeout/reintento; mostrar referencia y estado pendiente/verificando sin afirmar entrega, y usar números sintéticos en artefactos públicos.
- **Escenarios:** comparar los tres TC anteriores en su interfaz observable; si un escenario no afecta UI, conservar la respuesta/salida en lugar de inventar capturas. Capturar las vistas afectadas por los TC de panel.
- **Modalidad y aplicabilidad:** nuevo → resultado inicial validado contra contrato/AC/TC, sin antes ni diff; modificación → última evidencia aprobada y resultado actual con revisiones y escenario equivalente; sin superficie relevante → No aplica justificado. Una vista sin UI no exige capturas.
- **Artefactos según modalidad:** API nueva: petición/status/JSON/contrato; panel nuevo: capturas del resultado inicial; cambio existente: antes + después + diff o capturas equivalentes; comandos: salida/código inicial o comparado. Completar la [plantilla comparativa](EVIDENCE_COMPARISON_TEMPLATE.md), vinculada a B36-UC01–UC03 y AC01–AC03.
- **Aprobación:** resultado inicial conforme al contrato o diferencias esperadas justificadas y probadas; sin regresiones pendientes. VC01 exige declarar aplicabilidad; No aplica requiere justificación revisada. Es una condición de proceso independiente del porcentaje de AC, sin inflar su denominador. No sustituye tests ni autoriza actualizar la base automáticamente.

**Verificación y salida:** registrar evidencia real UC → AC → TC para la revisión exacta; ejecutar checks y regresión del protocolo; exigir VC01 según su modalidad/aplicabilidad, los tres AC y tests aplicables aprobados y completitud ≥97% sin redondeo. Con 3 AC obligatorios se requiere 3/3. Después: commit candidato → review Standards/Spec → corrección y nueva verificación hasta aprobación → PR para human review. Código simple, tipado y sin comentarios explicativos. No abrir PR ni cerrar B36 solo por tener casillas marcadas.

#### B37 — Conciliar y confirmar pago al celular

**Bloqueado por:** B36, B23, B19.

**Objetivo y entrega:** Pago al celular recorre la misma confirmación y reportes; reenvío conserva cuotas y no duplica dinero.

- **Red:** Ausencia de push no infiere rechazo; evento repetido suma una vez; consulta incierta no reemite.
- **Green:** Mapeo de evidencia/consulta del canal y prueba autorizada; documentar compatibilidad observada.
- **Refactor:** Converger en evidencia común y retirar reglas duplicadas del canal.

**Contrato de verificación:** [Protocolo común](TICKET_QUALITY_PROTOCOL.md). Actor: Operador y pagador autorizado. Frontera: Celular, evidencia y consulta. Dependencias anteriores completadas; datos aislados ficticios y actor autorizado salvo casos negativos. Sin ampliaciones al alcance indicado en el objetivo.

**Casos de uso**

- **B37-UC01:** Operador y pagador autorizado: conciliar/aplicar y consultar reportes cuando se cumple «Solicitud al celular y evidencia exacta de pago», para obtener «Recepción verificada registrada una vez».
- **B37-UC02:** Operador y pagador autorizado: consultar y solicitar recuperación cuando se cumple «No se presenta push y no hay evidencia de rechazo», para obtener «No infiere rechazo ni falta de enrolamiento; conserva incertidumbre».
- **B37-UC03:** Operador y pagador autorizado: procesar y consultar cuando se cumple «Evento repetido y reenvíos por encima de cuota», para obtener «Dinero no se duplica y cuota limita reenvíos; prueba real registra banco/dispositivo observados».

**Criterios de aceptación — obligatorios**

- [ ] **B37-AC01:** Recepción verificada registrada una vez. Verificación: B37-TC01.
- [ ] **B37-AC02:** No infiere rechazo ni falta de enrolamiento; conserva incertidumbre. Verificación: B37-TC02.
- [ ] **B37-AC03:** Dinero no se duplica y cuota limita reenvíos; prueba real registra banco/dispositivo observados. Verificación: B37-TC03.

**Casos de prueba — todos NOT_RUN**

| ID / trazabilidad | Preparación y datos | Acción | Resultado esperado | Ejecución |
| --- | --- | --- | --- | --- |
| B37-TC01 → B37-UC01, B37-AC01 | Solicitud al celular y evidencia exacta de pago | Conciliar/aplicar y consultar reportes | Recepción verificada registrada una vez | Automatizada |
| B37-TC02 → B37-UC02, B37-AC02 | No se presenta push y no hay evidencia de rechazo | Consultar y solicitar recuperación | No infiere rechazo ni falta de enrolamiento; conserva incertidumbre | Automatizada |
| B37-TC03 → B37-UC03, B37-AC03 | Evento repetido y reenvíos por encima de cuota | Procesar y consultar | Dinero no se duplica y cuota limita reenvíos; prueba real registra banco/dispositivo observados | Automatizada + externa autorizada |

**Comprobación visible según aplique — B37-VC01 (obligatoria, NOT_RUN)**

- **Superficie y alcance:** API y recorrido externo. Comparar evidencia y reportes antes/después del pago al celular, ausencia de push y duplicado; registrar banco/dispositivo observados sin capturar datos reales del pagador.
- **Escenarios:** comparar los tres TC anteriores en su interfaz observable; si un escenario no afecta UI, conservar la respuesta/salida en lugar de inventar capturas. Capturar las vistas afectadas por los TC de panel.
- **Modalidad y aplicabilidad:** nuevo → resultado inicial validado contra contrato/AC/TC, sin antes ni diff; modificación → última evidencia aprobada y resultado actual con revisiones y escenario equivalente; sin superficie relevante → No aplica justificado. Una vista sin UI no exige capturas.
- **Artefactos según modalidad:** API nueva: petición/status/JSON/contrato; panel nuevo: capturas del resultado inicial; cambio existente: antes + después + diff o capturas equivalentes; comandos: salida/código inicial o comparado. Completar la [plantilla comparativa](EVIDENCE_COMPARISON_TEMPLATE.md), vinculada a B37-UC01–UC03 y AC01–AC03.
- **Aprobación:** resultado inicial conforme al contrato o diferencias esperadas justificadas y probadas; sin regresiones pendientes. VC01 exige declarar aplicabilidad; No aplica requiere justificación revisada. Es una condición de proceso independiente del porcentaje de AC, sin inflar su denominador. No sustituye tests ni autoriza actualizar la base automáticamente.

**Verificación y salida:** registrar evidencia real UC → AC → TC para la revisión exacta; ejecutar checks y regresión del protocolo; exigir VC01 según su modalidad/aplicabilidad, los tres AC y tests aplicables aprobados y completitud ≥97% sin redondeo. Con 3 AC obligatorios se requiere 3/3. Después: commit candidato → review Standards/Spec → corrección y nueva verificación hasta aprobación → PR para human review. Código simple, tipado y sin comentarios explicativos. No abrir PR ni cerrar B37 solo por tener casillas marcadas.

#### B38 — Crear y compartir enlace oficial

**Bloqueado por:** B13, B16, B33.

**Objetivo y entrega:** Devuelve URL oficial, importe y referencia; comprueba receptor/método configurados antes de habilitar canal.

- **Red:** URL inválida, cuenta/método no verificables y abrir retorno de éxito no acreditan recepción.
- **Green:** Adaptador de enlace y contrato de retorno/consulta; sin propinas ni expiración inventada.
- **Refactor:** Separar presentación/retorno web del motor de estados.

**Contrato de verificación:** [Protocolo común](TICKET_QUALITY_PROTOCOL.md). Actor: Operador y pagador. Frontera: HTTP enlace y retorno web. Dependencias anteriores completadas; datos aislados ficticios y actor autorizado salvo casos negativos. Sin ampliaciones al alcance indicado en el objetivo.

**Casos de uso**

- **B38-UC01:** Operador y pagador: crear y recuperar enlace cuando se cumple «Configuración de receptor/método validada y respuesta oficial con URL», para obtener «URL oficial con importe/referencia preservados, aún pendiente».
- **B38-UC02:** Operador y pagador: crear/activar canal cuando se cumple «URL inválida o receptor/método sin validar», para obtener «No expone canal como funcional ni inventa destinatario».
- **B38-UC03:** Operador y pagador: consultar cobro cuando se cumple «Persona abre directamente URL de retorno de éxito sin pagar», para obtener «No aparece recibido; no impone expiración no garantizada».

**Criterios de aceptación — obligatorios**

- [ ] **B38-AC01:** URL oficial con importe/referencia preservados, aún pendiente. Verificación: B38-TC01.
- [ ] **B38-AC02:** No expone canal como funcional ni inventa destinatario. Verificación: B38-TC02.
- [ ] **B38-AC03:** No aparece recibido; no impone expiración no garantizada. Verificación: B38-TC03.

**Casos de prueba — todos NOT_RUN**

| ID / trazabilidad | Preparación y datos | Acción | Resultado esperado | Ejecución |
| --- | --- | --- | --- | --- |
| B38-TC01 → B38-UC01, B38-AC01 | Configuración de receptor/método validada y respuesta oficial con URL | Crear y recuperar enlace | URL oficial con importe/referencia preservados, aún pendiente | Automatizada |
| B38-TC02 → B38-UC02, B38-AC02 | URL inválida o receptor/método sin validar | Crear/activar canal | No expone canal como funcional ni inventa destinatario | Automatizada |
| B38-TC03 → B38-UC03, B38-AC03 | Persona abre directamente URL de retorno de éxito sin pagar | Consultar cobro | No aparece recibido; no impone expiración no garantizada | Automatizada |

**Comprobación visible según aplique — B38-VC01 (obligatoria, NOT_RUN)**

- **Superficie y alcance:** API y retorno web. Comparar DTO/URL oficial, errores de configuración y consulta antes/después de abrir retorno sin pagar; no capturar checkout alojado ajeno salvo recorrido autorizado necesario.
- **Escenarios:** comparar los tres TC anteriores en su interfaz observable; si un escenario no afecta UI, conservar la respuesta/salida en lugar de inventar capturas. Capturar las vistas afectadas por los TC de panel.
- **Modalidad y aplicabilidad:** nuevo → resultado inicial validado contra contrato/AC/TC, sin antes ni diff; modificación → última evidencia aprobada y resultado actual con revisiones y escenario equivalente; sin superficie relevante → No aplica justificado. Una vista sin UI no exige capturas.
- **Artefactos según modalidad:** API nueva: petición/status/JSON/contrato; panel nuevo: capturas del resultado inicial; cambio existente: antes + después + diff o capturas equivalentes; comandos: salida/código inicial o comparado. Completar la [plantilla comparativa](EVIDENCE_COMPARISON_TEMPLATE.md), vinculada a B38-UC01–UC03 y AC01–AC03.
- **Aprobación:** resultado inicial conforme al contrato o diferencias esperadas justificadas y probadas; sin regresiones pendientes. VC01 exige declarar aplicabilidad; No aplica requiere justificación revisada. Es una condición de proceso independiente del porcentaje de AC, sin inflar su denominador. No sustituye tests ni autoriza actualizar la base automáticamente.

**Verificación y salida:** registrar evidencia real UC → AC → TC para la revisión exacta; ejecutar checks y regresión del protocolo; exigir VC01 según su modalidad/aplicabilidad, los tres AC y tests aplicables aprobados y completitud ≥97% sin redondeo. Con 3 AC obligatorios se requiere 3/3. Después: commit candidato → review Standards/Spec → corrección y nueva verificación hasta aprobación → PR para human review. Código simple, tipado y sin comentarios explicativos. No abrir PR ni cerrar B38 solo por tener casillas marcadas.

#### B39 — Conciliar y confirmar pago por enlace

**Bloqueado por:** B38, B23, B20.

**Objetivo y entrega:** Estado de checkout se contrasta con transferencias; parcial/incompatible abre incidencia; retorno no confirma.

- **Red:** paid sin evidencia suficiente no cubre venta; partial va a revisión; duplicados suman una vez.
- **Green:** Normalización y consulta de enlace con método/cuenta verificados, y prueba autorizada de recorrido mismo teléfono.
- **Refactor:** Reusar aplicación de evidencia y conservar particularidades externas en adaptador.

**Contrato de verificación:** [Protocolo común](TICKET_QUALITY_PROTOCOL.md). Actor: Operador y conciliador. Frontera: Contrato enlace, evidencia y consultas. Dependencias anteriores completadas; datos aislados ficticios y actor autorizado salvo casos negativos. Sin ampliaciones al alcance indicado en el objetivo.

**Casos de uso**

- **B39-UC01:** Operador y conciliador: conciliar y consultar detalle cuando se cumple «Checkout y transferencia verificados para cuenta/método permitidos», para obtener «Venta cubierta por evidencia exacta y reportes coherentes».
- **B39-UC02:** Operador y conciliador: aplicar actualización y consultar cuando se cumple «Estado paid sin evidencia suficiente o partial», para obtener «No confirma por etiqueta; parcial/discrepancia requiere revisión».
- **B39-UC03:** Operador y conciliador: procesar ambos y probar recorrido autorizado en mismo teléfono cuando se cumple «Misma transferencia llega por actualización y consulta», para obtener «Una recepción; compatibilidad se declara solo para recorrido observado».

**Criterios de aceptación — obligatorios**

- [ ] **B39-AC01:** Venta cubierta por evidencia exacta y reportes coherentes. Verificación: B39-TC01.
- [ ] **B39-AC02:** No confirma por etiqueta; parcial/discrepancia requiere revisión. Verificación: B39-TC02.
- [ ] **B39-AC03:** Una recepción; compatibilidad se declara solo para recorrido observado. Verificación: B39-TC03.

**Casos de prueba — todos NOT_RUN**

| ID / trazabilidad | Preparación y datos | Acción | Resultado esperado | Ejecución |
| --- | --- | --- | --- | --- |
| B39-TC01 → B39-UC01, B39-AC01 | Checkout y transferencia verificados para cuenta/método permitidos | Conciliar y consultar detalle | Venta cubierta por evidencia exacta y reportes coherentes | Automatizada |
| B39-TC02 → B39-UC02, B39-AC02 | Estado paid sin evidencia suficiente o partial | Aplicar actualización y consultar | No confirma por etiqueta; parcial/discrepancia requiere revisión | Automatizada |
| B39-TC03 → B39-UC03, B39-AC03 | Misma transferencia llega por actualización y consulta | Procesar ambos y probar recorrido autorizado en mismo teléfono | Una recepción; compatibilidad se declara solo para recorrido observado | Automatizada + externa autorizada |

**Comprobación visible según aplique — B39-VC01 (obligatoria, NOT_RUN)**

- **Superficie y alcance:** API y recorrido externo. Comparar actualización checkout con recepción conciliada, casos paid/partial y duplicados; mostrar cuenta/método permitidos sin inferir recepción por una página de éxito.
- **Escenarios:** comparar los tres TC anteriores en su interfaz observable; si un escenario no afecta UI, conservar la respuesta/salida en lugar de inventar capturas. Capturar las vistas afectadas por los TC de panel.
- **Modalidad y aplicabilidad:** nuevo → resultado inicial validado contra contrato/AC/TC, sin antes ni diff; modificación → última evidencia aprobada y resultado actual con revisiones y escenario equivalente; sin superficie relevante → No aplica justificado. Una vista sin UI no exige capturas.
- **Artefactos según modalidad:** API nueva: petición/status/JSON/contrato; panel nuevo: capturas del resultado inicial; cambio existente: antes + después + diff o capturas equivalentes; comandos: salida/código inicial o comparado. Completar la [plantilla comparativa](EVIDENCE_COMPARISON_TEMPLATE.md), vinculada a B39-UC01–UC03 y AC01–AC03.
- **Aprobación:** resultado inicial conforme al contrato o diferencias esperadas justificadas y probadas; sin regresiones pendientes. VC01 exige declarar aplicabilidad; No aplica requiere justificación revisada. Es una condición de proceso independiente del porcentaje de AC, sin inflar su denominador. No sustituye tests ni autoriza actualizar la base automáticamente.

**Verificación y salida:** registrar evidencia real UC → AC → TC para la revisión exacta; ejecutar checks y regresión del protocolo; exigir VC01 según su modalidad/aplicabilidad, los tres AC y tests aplicables aprobados y completitud ≥97% sin redondeo. Con 3 AC obligatorios se requiere 3/3. Después: commit candidato → review Standards/Spec → corrección y nueva verificación hasta aprobación → PR para human review. Código simple, tipado y sin comentarios explicativos. No abrir PR ni cerrar B39 solo por tener casillas marcadas.

#### B40 — Verificar contrato común para mobile

**Bloqueado por:** B30, B28, B35.

**Objetivo y entrega:** Contrato documenta centavos, fechas, estados, errores e idempotencia con ejemplos canónicos; backend pasa escenarios críticos.

- **Red:** Petición inválida no se convierte silenciosamente; estado desconocido del proveedor nunca produce PAID.
- **Green:** Publicar OpenAPI y fixtures sanitizados; regresión QR, acceso y recuperación. Añadir B37/B39 solo si esos canales se comprometen.
- **Refactor:** Revisar consistencia de DTOs y errores sin agregar versiones móviles ni endpoints especulativos.

**Contrato de verificación:** [Protocolo común](TICKET_QUALITY_PROTOCOL.md). Actor: Consumidor móvil y contribuidor. Frontera: HTTP/OpenAPI y fixtures. Dependencias anteriores completadas; datos aislados ficticios y actor autorizado salvo casos negativos. Sin ampliaciones al alcance indicado en el objetivo.

**Casos de uso**

- **B40-UC01:** Consumidor móvil y contribuidor: validar ejemplos contra contrato y ejecutar regresión QR cuando se cumple «Ejemplos canónicos de centavos, UTC, errores y estados», para obtener «Resultados coinciden con contrato y referencias verificadas del núcleo».
- **B40-UC02:** Consumidor móvil y contribuidor: ejecutar contrato cuando se cumple «Entrada con dinero inválido o estado desconocido del proveedor», para obtener «Rechazo explícito/estado incierto; nunca PAID por valor desconocido».
- **B40-UC03:** Consumidor móvil y contribuidor: ejecutar flujo acceso/QR/recuperación/historial/resumen cuando se cumple «Cliente recupera cobro tras cierre con la misma clave», para obtener «Mismo recurso y recepción; canales extra se exigen solo si están comprometidos».

**Criterios de aceptación — obligatorios**

- [ ] **B40-AC01:** Resultados coinciden con contrato y referencias verificadas del núcleo. Verificación: B40-TC01.
- [ ] **B40-AC02:** Rechazo explícito/estado incierto; nunca PAID por valor desconocido. Verificación: B40-TC02.
- [ ] **B40-AC03:** Mismo recurso y recepción; canales extra se exigen solo si están comprometidos. Verificación: B40-TC03.

**Casos de prueba — todos NOT_RUN**

| ID / trazabilidad | Preparación y datos | Acción | Resultado esperado | Ejecución |
| --- | --- | --- | --- | --- |
| B40-TC01 → B40-UC01, B40-AC01 | Ejemplos canónicos de centavos, UTC, errores y estados | Validar ejemplos contra contrato y ejecutar regresión QR | Resultados coinciden con contrato y referencias verificadas del núcleo | Automatizada |
| B40-TC02 → B40-UC02, B40-AC02 | Entrada con dinero inválido o estado desconocido del proveedor | Ejecutar contrato | Rechazo explícito/estado incierto; nunca PAID por valor desconocido | Automatizada |
| B40-TC03 → B40-UC03, B40-AC03 | Cliente recupera cobro tras cierre con la misma clave | Ejecutar flujo acceso/QR/recuperación/historial/resumen | Mismo recurso y recepción; canales extra se exigen solo si están comprometidos | Automatizada |

**Comprobación visible según aplique — B40-VC01 (obligatoria, NOT_RUN)**

- **Superficie y alcance:** API y contrato. Comparar OpenAPI, ejemplos canónicos y respuestas de acceso/QR/recuperación/historial/resumen contra base aprobada; enumerar campos añadidos, eliminados o con tipo/semántica cambiados y efecto en clientes.
- **Escenarios:** comparar los tres TC anteriores en su interfaz observable; si un escenario no afecta UI, conservar la respuesta/salida en lugar de inventar capturas. Capturar las vistas afectadas por los TC de panel.
- **Modalidad y aplicabilidad:** nuevo → resultado inicial validado contra contrato/AC/TC, sin antes ni diff; modificación → última evidencia aprobada y resultado actual con revisiones y escenario equivalente; sin superficie relevante → No aplica justificado. Una vista sin UI no exige capturas.
- **Artefactos según modalidad:** API nueva: petición/status/JSON/contrato; panel nuevo: capturas del resultado inicial; cambio existente: antes + después + diff o capturas equivalentes; comandos: salida/código inicial o comparado. Completar la [plantilla comparativa](EVIDENCE_COMPARISON_TEMPLATE.md), vinculada a B40-UC01–UC03 y AC01–AC03.
- **Aprobación:** resultado inicial conforme al contrato o diferencias esperadas justificadas y probadas; sin regresiones pendientes. VC01 exige declarar aplicabilidad; No aplica requiere justificación revisada. Es una condición de proceso independiente del porcentaje de AC, sin inflar su denominador. No sustituye tests ni autoriza actualizar la base automáticamente.

**Verificación y salida:** registrar evidencia real UC → AC → TC para la revisión exacta; ejecutar checks y regresión del protocolo; exigir VC01 según su modalidad/aplicabilidad, los tres AC y tests aplicables aprobados y completitud ≥97% sin redondeo. Con 3 AC obligatorios se requiere 3/3. Después: commit candidato → review Standards/Spec → corrección y nueva verificación hasta aprobación → PR para human review. Código simple, tipado y sin comentarios explicativos. No abrir PR ni cerrar B40 solo por tener casillas marcadas.

## Límites y dependencias externas

- B15/B35 y cada canal real necesitan acceso válido, receptor habilitado y contrato vigente; no se envían mensajes ni se ejecutan transferencias como parte de esta planificación.
- B17 puede desarrollarse contra el contrato firmado con fixtures sin esperar producción. B18–B34 se pueden verificar en entorno simulado aislado.
- B35 es la evidencia auténtica del núcleo QR. B36–B39 forman el alcance objetivo celular/enlace: el usuario aún debe confirmar si son obligatorios para la primera entrega. B40 se amplía a esos canales cuando se comprometan; no los declara integrados por defecto.
- Notificaciones push del dispositivo, entrega de emails, signup público, alta bancaria pública, cambio de cuenta desde mobile, pagos parciales intencionales, devoluciones automáticas, NFC y CRUD arbitrario sobre dinero quedan fuera de este backlog.
- B32 permite seguimiento y conciliación, no resolver discrepancias cambiando PAID a mano. Definir una devolución o ajuste financiero exige otro alcance.
- No hay un ticket «implementar todo el backend» ni se incluyen frontend/mobile ocultos dentro de una subtarea.

## Configuración de las skills

GitHub Issues en luisjrez/Tappy es el tracker autorizado. Configuración en AGENTS.md y docs/agents/: etiquetas canónicas, PRs externos sin triage automático y un contexto global. Ver [mapa publicado](GITHUB_BACKLOG.md).

## Pendientes operativos durante implementación

La publicación autoriza organizar el trabajo; no acredita accesos bancarios ni capacidad de producción. Duración de sesiones, credencial inicial, límites monetarios/cuotas y requisitos externos se fijan y documentan en los tickets afectados antes de activar su comportamiento real. Celular/enlace se publican como alcance adicional secuenciado después del núcleo, sin inventar compromiso de fecha.

## Fuentes de investigación

Inspección local de Privada Reforma el 20-nov-2026: `docs/backend/ADMIN.md`, `apps/api/src/reforma/admin.py` y dependencias. Se identificó el paquete y patrón; no se copió código ni datos privados a Tappy.

- [FastAPI: aplicaciones grandes y APIRouter](https://fastapi.tiangolo.com/tutorial/bigger-applications/).
- [Starlette Admin: repositorio oficial](https://github.com/jowilf/starlette-admin).
- [Reglas y pruebas previas de Tappy](../03-historias-y-pruebas.md): requisitos financieros siguen aplicando; detalles del antiguo backend deben adaptarse al stack actual.

Las rutas antiguas de documentación de autenticación/vistas de Starlette Admin devolvieron 404 durante la consulta; no se usan como evidencia. Antes de implementar se fijarán versiones compatibles y se consultarán sus referencias actuales. No se presenta ninguna combinación de dependencias como probada todavía.
