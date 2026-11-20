# Protocolo de implementación y verificación por ticket

Estado: estrategia documentada para los tickets de backend. No hay herramientas instaladas ni checks ejecutados sobre una aplicación todavía. Aplica a B01–B40 y a los tickets posteriores que la referencien.

## Contrato de cada ticket

Cada ticket contiene objetivo, alcance/exclusiones, dependencias, actores y precondiciones, casos de uso UC, criterios de aceptación AC y casos de prueba TC. Los IDs son estables y llevan el prefijo del ticket: `B19-UC01`, `B19-AC01`, `B19-TC01`.

Cada TC identifica UC y AC, preparación/datos, acción por una frontera observable y resultado esperado independiente de la implementación. Se declara automatizado, manual o externo; un test externo simulado no demuestra integración real. Cada AC tiene al menos un TC y cada UC tiene aceptación comprobable. Tests adicionales descubiertos durante TDD se agregan a la trazabilidad sin eliminar casos incómodos.

Antes de implementar: confirmar alcance, fronteras de prueba, datos y resultado esperado. La aprobación del backlog confirma las fronteras propuestas; un cambio material de comportamiento requiere volver a acordarlo. No hace falta volver a pedir autorización para cada test que siga ese contrato.

## Código legible sin comentarios

El código propio se escribe sin comentarios explicativos, bloques de código comentado ni TODO/FIXME. Se priorizan nombres de dominio, funciones pequeñas, tipos precisos y módulos cohesionados. Si necesita una explicación, primero se simplifica el diseño; contexto, decisiones y restricciones se documentan en Markdown junto al ticket o en una ADR.

No exigir docstrings de relleno ni usar docstrings para trasladar comentarios al código. Descripciones de API útiles para quien consume el contrato se definen como metadatos de documentación. Las cabeceras legales de dependencias o artefactos generados se conservan. Una directiva técnica imprescindible de una herramienta se permite solo de forma localizada, con motivo registrado en el reporte de revisión; no se añaden supresiones generales de lint/tipado para obtener verde.

## Herramientas y checks Python

B01 prepara la configuración; B03 implementa un comando único de verificación local y su equivalente obligatorio en CI. Se fijan versiones compatibles al implementar. Un solo formateador para Python: Ruff; no añadir Prettier a Python.

| Control | Configuración prevista | Condición de aprobación |
| --- | --- | --- |
| Formato | `ruff format --check` | Sin diferencias |
| Lint e imports | `ruff check`; reglas de errores, imports, modernización y bugs frecuentes acordes a versión Python | Cero infracciones; sin autofix silencioso en CI |
| Tipado | mypy estricto para código propio y tests tipados | Cero errores; Any o exclusiones deben tener una frontera externa justificada |
| Pruebas | pytest con configuración/markers estrictos, informe JUnit y Postgres desechable | Todos los tests aplicables pasan; no esconder fallos con skip/xfail |
| Persistencia | Migrar base vacía, comprobar consistencia de migraciones/modelos y pruebas de rollback/concurrencia cuando aplique | Sin migración pendiente ni pérdida de integridad |
| Contrato | Validación de entradas/salidas Pydantic y OpenAPI para las operaciones del ticket | Casos válidos e inválidos respetan el contrato |
| Higiene | Sin secretos, código comentado, TODO/FIXME ni comentarios explicativos propios | Inspección del diff; comprobación de comentarios por tokens de Python al implementar B03 |

La comprobación automática de comentarios usa tokens, no un grep que confunda `#` en cadenas. La ausencia de comentarios no demuestra legibilidad: el code review evalúa nombres, complejidad y organización. No se habilitan reglas que obliguen comentarios/docstrings innecesarios.

Se ejecuta el test específico durante Red/Green. Tras Green y cada refactor o corrección se ejecuta la suite de regresión pertinente. Antes de verificación, commit candidato, re-revisión final y PR se exige la batería completa aplicable al backend con configuración equivalente a CI. La integración bancaria real no se ejecuta automáticamente en CI; su evidencia externa sigue siendo obligatoria para los tickets que la exigen.

La cobertura de líneas/ramas puede ayudar a encontrar huecos, pero **no es el porcentaje de completitud** ni sustituye casos de uso o aceptación. No se impone un 97% de cobertura de código por confusión con el umbral pedido.

## Loop por ticket

1. Registrar ticket, base git fija, alcance, UC/AC/TC y fronteras de prueba aprobadas. Elegir modalidad de evidencia: resultado inicial para funcionalidad nueva, antes/después para cambios existentes, o No aplica justificado. Recuperar base aprobada solo cuando exista y corresponda.
2. **Red:** escribir un test de comportamiento y observar el fallo esperado. Un error de instalación o sintaxis no prueba que falta el comportamiento. Guardar comando y resultado.
3. **Green:** implementar el mínimo que hace pasar ese caso; repetir Red/Green para el siguiente TC. No escribir primero toda la suite y después todo el código.
4. **Refactor:** revisar y simplificar con tests verdes; repetir checks y regresión después de cambiar. Esta revisión posterior conserva la distinción de la skill TDD entre implementación y revisión.
5. Ejecutar la batería completa de checks aplicables y comparar resultados reales con UC, TC y AC; guardar la matriz de evidencia y la evidencia aplicable de API, panel o interfaz operativa: resultado inicial o comparación antes/después. Clasificar cada diferencia como esperada o regresión.
6. Calcular el umbral. Si hay un fallo obligatorio o resultado insuficiente, volver al caso concreto: reproducir, añadir/corregir prueba, implementar mínimo, refactorizar y verificar otra vez.
7. Con el umbral aprobado, hacer inspección previa del diff y un commit candidato revisable en la rama del ticket. No hacer push ni abrir PR automáticamente por tener un porcentaje alto.
8. Ejecutar **code review del commit candidato** contra la base fijada, en dos ejes separados: **Standards**, contra este protocolo y las reglas del repo; **Spec**, contra UC/AC/TC y alcance del ticket. Al usar la skill `code-review`, conservar sus dos revisiones independientes.
9. Cada hallazgo registra criterio, evidencia, severidad y corrección esperada. Un defecto funcional vuelve a Red/Green/Refactor; un hallazgo solo de legibilidad vuelve a refactor/checks sin crear un test que replique implementación. Hacer commit de corrección y repetir verificación y revisión sobre el nuevo HEAD. No basta revisar solo el hunk corregido si afecta otras reglas.
10. Con ambos ejes aprobados, cero hallazgos pendientes y checks/evidencia correspondientes al HEAD final, abrir PR para **human review**. Incluir ticket, alcance, trazabilidad, resultados, porcentaje, hallazgos resueltos, evidencia inicial o comparativa según aplique y limitaciones. Los cambios solicitados por la persona revisora repiten el loop; PR listo no significa merge autorizado.

## Comprobación visible según aplique: inicial o comparativa

Todos los tickets incluyen una sección de evidencia y declaran su aplicabilidad. **Nuevo:** registrar el resultado inicial y validarlo contra contrato/AC/TC; no exigir respuesta previa, 404 anterior, captura anterior ni diff. **Modificación:** comparar la última evidencia aprobada con el resultado actual. **No aplica:** justificar por qué no hay una superficie observable relevante; conservar las pruebas funcionales y checks del ticket. Una superficie sin UI no requiere capturas, aunque puede tener evidencia de API o comandos. La evidencia permite ver qué cambió; los tests y criterios deciden si ese cambio es correcto. Una captura o snapshot aprobado por inercia no sustituye verificar valores, estados, permisos ni reglas financieras.

### Base de comparación

- Usar la última evidencia **aprobada** del escenario y contrato relevantes, vinculada al SHA de base del ticket. Registrar también el SHA actual. No usar como baseline una ejecución fallida ni cambiar la base a mitad de una corrección para ocultar diferencias.
- Ejecutar antes y después con datos sintéticos equivalentes, mismo actor/rol, petición, entorno y configuración. En panel fijar además viewport, navegador, tema, escala de texto y estado del recorrido. Registrar cambios de entorno que impidan equivalencia.
- Si la funcionalidad es nueva, indicar «Resultado inicial». En API registrar petición, status, JSON y contrato esperado; en panel registrar capturas y recorrido de la vista nueva. No hay antes ni diff obligatorio. El resultado aprobado establece la primera base para cambios futuros. Si el mismo ticket modifica otra superficie existente, esa parte sí lleva comparación antes/después.
- Conservar baseline y resultado actual sin sobrescribirlos. La evidencia actual solo se propone como nueva base después de revisión aprobada; no regenerar snapshots para hacer desaparecer un test rojo.

### API: respuesta anterior, actual y diferencia

Por cada operación y caso de éxito/error afectado, guardar método, ruta, query/body de prueba sanitizados, rol, status HTTP, cabeceras relevantes permitidas y cuerpo JSON. Para un endpoint nuevo adjuntar solo resultado inicial y contrato esperado. Para cambios de un endpoint existente adjuntar respuesta anterior/actual, diferencia legible campo por campo y, si cambia el esquema, diferencia OpenAPI. Incluir al menos los TC del ticket que ejercitan esa interfaz, no solo un happy path.

El reporte debe mostrar JSON inicial o ambos JSON y diff, según modalidad, formateados como texto copiable; no requiere capturas de pantalla de JSON. Separar cambios de presencia/ausencia, tipo, nulabilidad, valor, formato y significado. Por ejemplo: un campo nuevo puede ser intencional; pasar centavos enteros a texto o perder una referencia puede ser una regresión aunque la respuesta siga siendo 200.

Normalizar únicamente valores no deterministas declarados: IDs sintéticos y timestamps controlados mediante una correspondencia estable. Conservar las relaciones entre referencias y no ocultar diferencias relevantes de importes, estados, tipos, permisos, zona horaria, expiración o orden contractual. No ordenar listas cuyo orden tenga significado. Mostrar las reglas de normalización y conservar evidencia original segura para diagnóstico cuando proceda.

No guardar Authorization, Set-Cookie, contraseñas, firmas, credenciales, CLABEs ni teléfonos reales. Usar datos ficticios y una lista explícita de cabeceras permitidas. Para login/renovación comparar la estructura de la credencial redactada y demostrar su funcionamiento mediante la consulta posterior, sin publicar el secreto.

Cada diferencia lleva: TC/AC afectado, antes, después, motivo, clasificación (aditiva compatible, incompatible, corrección o regresión), efecto en consumidores y resultado de review. Un cambio esperado del contrato se documenta y prueba; un cambio incompatible exige resolver compatibilidad con consumidores antes de aprobar. Una diferencia inesperada bloquea aunque los snapshots nuevos puedan generarse.

### Back office: capturas del mismo recorrido

Para una vista nueva guardar las capturas iniciales y validarlas contra los criterios. Para modificar una vista existente guardar capturas anteriores/actuales de la misma pantalla/estado, lado a lado en el reporte, y las peticiones/respuestas afectadas cuando corresponda. Enumerar vista, rol, fixture y pasos exactos. Capturar estados pertinentes: listado/detalle, formulario, validación/error, vacío/carga y resultado de acción, según el alcance del ticket; no exigir pantallas ajenas al cambio.

Revisar contenido y jerarquía, importes/fechas/estados, datos visibles por rol, controles/acciones disponibles, errores, desbordes y legibilidad. Las capturas no prueban teclado, foco ni lector de pantalla: registrar esas comprobaciones por separado cuando se cambie la interacción. Un botón oculto tampoco prueba autorización: mantener los tests de petición manipulada.

Si el ticket cambia API y panel, se exigen ambas evidencias. Una acción del panel que modifica datos se comprueba antes/después y por la lectura autorizada posterior; no basta mostrar el botón ni una notificación de éxito.

### Infraestructura, comandos y tareas sin pantalla

No inventar una UI para obtener una captura. Registrar salida sanitizada y código de salida del comando/check, o la respuesta de lectura que demuestra el efecto del trabajo. Para una capacidad nueva es evidencia inicial; para un cambio existente comparar antes/después con el mismo escenario. Para migraciones y restauración, adjuntar resultados operativos y consultas públicas de comprobación; para CI, salida de checks y enlaces a ejecuciones/artefactos. La sección de capturas puede indicar «No aplica: sin UI afectada»; usar evidencia inicial o comparativa de comandos/API cuando corresponda, sin imponer un antes inexistente.

### Condición de salida y automatización

Cada ticket incorpora **VC01**, declaración obligatoria de aplicabilidad y modalidad: resultado inicial validado o evidencia anterior/actual con diferencias explicadas, vinculados a revisiones y casos trazados; si no aplica, justificación revisada, sin regresiones pendientes. Es una condición de proceso; no se añade al denominador de AC para inflar el porcentaje. Su estado inicial es NOT_RUN. Si falta evidencia requerida o hay una diferencia no explicada, no se avanza al PR aunque la completitud supere 97%.

B03 preparará generación y conservación de reportes/diffs de API y salidas de checks; los tickets de panel incorporarán capturas al introducir las vistas. La implementación del mecanismo se hará con TDD en sus fronteras aprobadas. La comparación funcional de JSON/contrato debe poder fallar; las diferencias visuales se revisan con contexto. No usar un porcentaje arbitrario de píxeles como equivalencia de corrección de producto ni imponer un framework de capturas durante esta fase de planificación.

Usar la [plantilla de evidencia comparativa](EVIDENCE_COMPARISON_TEMPLATE.md). Cada PR incluirá el reporte o enlaces a artefactos accesibles al revisor; no depender únicamente de rutas efímeras del equipo local. No se generan ni publican artefactos visuales reales en esta tarea de documentación.

## Umbral de completitud: al menos 97%

La unidad de evaluación es el **criterio de aceptación**, no el número de asserts, tests, archivos o líneas. Cada criterio vale una unidad; no se pondera a posteriori para maquillar el resultado.

`completitud = 100 × AC verificados PASS / AC aplicables acordados`

- PASS: evidencia vigente del comportamiento esperado y todos sus TC aplicables aprobados.
- FAIL, BLOCKED y NOT_RUN: permanecen en el denominador y no suman al numerador.
- N/A: solo con justificación revisada antes de ejecutar; el reporte conserva quién/por qué lo excluyó. No reclasificar fallos como N/A ni fragmentar criterios para subir el porcentaje.
- Comparar con 97 sin redondear hacia arriba. Sin criterios aplicables el resultado es inválido, no 100%.
- Todos los AC de este backlog son **obligatorios por defecto**. Solo un criterio expresamente acordado como no bloqueante antes de implementar puede quedar pendiente dentro del margen del 3%, con seguimiento visible. No se inventan criterios opcionales para alcanzar un número.
- Con tres AC obligatorios, 2/3 equivale a 66.67% y bloquea; el ticket exige 3/3. En tickets pequeños, llegar al 97% normalmente exige 100% de sus AC. No aumentar artificialmente la granularidad para permitir un fallo.

Además del porcentaje, hay condiciones obligatorias: 100% de tests/checks aplicables pasan; todos los AC obligatorios pasan; VC01 aprobada con evidencia aplicable o No aplica justificado, sin diferencias inesperadas pendientes; cero defectos conocidos de dinero, identidad, permisos, aislamiento, evidencias o integridad; cero hallazgos pendientes en ambos ejes de code review. La ausencia de una prueba bancaria requerida bloquea ese ticket aunque la simulación pase.

Por tanto, 97% habilita avanzar solo cuando esas condiciones también se cumplen. El 3% no permite tolerar tests fallidos, requisitos obligatorios incompletos ni diferencias con la especificación. Una historia padre exige que todas sus subtareas obligatorias cumplan; no promedia porcentajes para ocultar un ticket pendiente.

## Registro de evidencia por ejecución

Guardar junto al ticket o enlazar desde su issue/PR una matriz por ejecución. La evidencia corresponde a una revisión exacta: SHA candidato/final, árbol local limpio o diff identificado, entorno, fecha y versiones. Si cambia código, configuración, fixtures o dependencias, se invalida la evidencia afectada y se repite verificación. No declarar éxito sobre un SHA previo.

| Campo | Contenido obligatorio |
| --- | --- |
| Identificación | Ticket, revisión, base de review, fecha, entorno y ejecutor |
| Trazabilidad | UC → AC → TC → nombre/comando real del test o pasos manuales |
| Resultado | Esperado, observado, PASS/FAIL/BLOCKED/NOT_RUN y enlace a evidencia sanitizada |
| TDD | Evidencia Red y Green por comportamiento añadido/corregido; refactor y regresión posterior |
| Checks | Comando exacto, salida/resumen, código de salida y revisión evaluada |
| Comparación VC01 | Modalidad y aplicabilidad; revisión actual y base solo si existe; resultado inicial o antes/después/diff de API/comando y capturas de UI cuando aplique; validación o diferencias y aprobación |
| Umbral | AC PASS / AC aplicables, porcentaje sin redondeo y estado de condiciones obligatorias |
| Review | Hallazgo por eje, corrección, revisión de cierre y re-revisión final |
| Pendientes | Criterio opcional acordado si existe, limitación e issue de seguimiento |

Hasta ejecutar, todos los TC y AC del borrador están **NOT_RUN**. Una casilla marcada, una salida inventada o el mero conteo de secciones no son evidencia funcional. La verificación estructural de estos documentos solo demuestra trazabilidad escrita.

## Fuentes y aplicación

Esta estrategia aplica TDD y el review Standards/Spec de las skills de Matt Pocock, adaptados a la petición del usuario. No se está ejecutando un code review de backend en esta tarea de documentación.

- [Ruff: linter y formateador Python](https://docs.astral.sh/ruff/).
- [mypy: interfaz de ejecución](https://mypy.readthedocs.io/en/stable/command_line.html).
- [pytest: selección y ejecución de pruebas](https://docs.pytest.org/en/stable/how-to/usage.html).

Referencias oficiales consultadas el 20 de noviembre de 2026. La instalación y configuración ejecutable se harán en B01–B03 después de aprobar el backlog.
