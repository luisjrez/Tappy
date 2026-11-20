# Tappy

Herramienta de cobros para micronegocios mexicanos: solicitar un cobro, comprobar su recepción y consultar lo recibido por periodo.

## Estado

Proyecto en definición y planificación. Este repositorio contiene documentación y referencias de diseño; todavía no contiene una aplicación o integración bancaria implementada.

- [Mapa de historias y tickets en GitHub](docs/planning/GITHUB_BACKLOG.md)
- [Protocolo de calidad por ticket](docs/planning/TICKET_QUALITY_PROTOCOL.md)
- [Base de producto](PRODUCT_BASE.md)
- [Vocabulario del dominio](CONTEXT.md)
- [Identidad de marca](TAPPY_BRAND_IDENTITY_SPEC.md)
- [Sistema de diseño](design-system/README.md)
- [Diseño Pen](tappy-design.pen)
- [Documentación anterior](docs/README.md)

## Dirección actual del backend

FastAPI con routers por módulo de negocio, PostgreSQL, SQLAlchemy y Pydantic. Desarrollo local con Docker Compose para PostgreSQL y entorno virtual Python dentro del proyecto. Starlette Admin para el back office. Implementación con TDD en incrementos pequeños.

El backlog aprobado se organiza en GitHub Issues con historias padre, subtareas y bloqueos. La publicación no implica implementación. Las propuestas anteriores de backend contenidas en `docs/` son antecedentes; no sustituyen esta dirección actual.

## Regla central

Una solicitud creada o enviada no significa pago recibido. La confirmación requiere evidencia bancaria validada; Tappy no custodia fondos.
