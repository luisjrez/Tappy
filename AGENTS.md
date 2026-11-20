# Tappy — instrucciones para agentes

Leer `CONTEXT.md`, `PRODUCT_BASE.md`, `docs/agents/domain.md` y el ticket con sus comentarios antes de trabajar. El backend usa FastAPI/APIRouter, PostgreSQL, SQLAlchemy y Pydantic, organizado por dominios; desarrollo con .venv local y Postgres en Docker Compose.

## Calidad por ticket

Seguir `docs/planning/TICKET_QUALITY_PROTOCOL.md`: UC/AC/TC trazables, TDD Red/Green, refactor con checks verdes, código simple sin comentarios explicativos, Ruff, mypy y pytest con Postgres real aislado. Evidencia inicial para funciones nuevas; antes/después para cambios existentes; No aplica justificado. Umbral de completitud ≥97% con todos los requisitos obligatorios y tests/checks aprobados; no tolerar fallos financieros o de permisos por porcentaje.

Commit candidato → review Standards/Spec → corregir y repetir pruebas/verificación/review → PR para revisión humana. No implementar el backlog entero en un cambio ni cerrar una historia por promediar subtareas pendientes. Una simulación no demuestra integración bancaria real. No registrar secretos ni datos bancarios/personales reales en git, issues, logs o evidencia pública. Ningún operador/admin puede marcar recibido sin evidencia validada.

## Agent skills

### Issue tracker

GitHub Issues en https://github.com/luisjrez/Tappy; PRs externos no son superficie automática de triage. Ver `docs/agents/issue-tracker.md`.

### Triage labels

Vocabulario estándar: needs-triage, needs-info, ready-for-agent, ready-for-human y wontfix. Ver `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `CONTEXT.md` global y `docs/adr/`. Ver `docs/agents/domain.md`.
