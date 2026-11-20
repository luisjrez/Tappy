# Issue tracker: GitHub

Repositorio: https://github.com/luisjrez/Tappy. Usar gh CLI para leer/publicar/actualizar issues y comentarios. Para cuerpos multilínea usar archivo con --body-file o JSON por stdin; conservar saltos de línea reales. Nunca publicar secretos.

## Convenciones

- Leer ticket completo, comentarios, etiquetas, padre y bloqueos antes de implementar: gh issue view NUM --repo luisjrez/Tappy --comments.
- Historias padre H1–H8; subtareas B01–B40 como sub-issues nativas. IDs B/H se conservan en títulos; números GitHub son los identificadores del tracker.
- Dependencias nativas blocked_by son la puerta de ejecución; el cuerpo también enumera enlaces para lectura. Usar database id del blocker, no el número de issue, al crear una dependencia.
- ready-for-agent significa especificado para implementación, no libre de dependencias. Empezar solo cuando todos los bloqueos estén cerrados y accesos/contratos externos requeridos estén disponibles.
- ready-for-human para comprobaciones que requieren personas/accesos externos. external-dependency y scope:additional describen restricciones sin sustituir triage.
- Reclamar con assignee antes de implementar. Resolver una subtarea con PR y evidencia; no cerrar/modificar automáticamente su historia padre ni confundir publicación con implementación.
- Al publicar un ticket incluir casos de uso, AC/TC, TDD, evidencia aplicable VC01 y referencia al protocolo compartido. Los enlaces a archivos en cuerpos de issues deben ser URLs completas de GitHub.
- El mapa publicado vive en docs/planning/GITHUB_BACKLOG.md; GitHub es la fuente del estado vivo. Cambios posteriores de alcance deben mantener consistencia con los documentos.

## Pull requests as a triage surface

PRs as a request surface: no. Los PRs de implementación sí pasan review, pero no entran automáticamente como solicitudes nuevas a la cola de triage.

## Operaciones de relación

Sub-issue: POST repos/luisjrez/Tappy/issues/PADRE/sub_issues con sub_issue_id del hijo.
Bloqueo: POST repos/luisjrez/Tappy/issues/HIJO/dependencies/blocked_by con issue_id del blocker.
Si la plataforma no soporta una relación, conservar enlaces explícitos en cuerpos y reportar el límite; no afirmar relación nativa no verificada.
