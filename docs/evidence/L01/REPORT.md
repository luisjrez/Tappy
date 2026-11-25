# Evidencia L01 — referencia y copy web

Fecha: 2026-11-25. Ticket [#93](https://github.com/luisjrez/Tappy/issues/93). Base fija de review: `96287d7`. La revisión evaluada es el commit que introduce este reporte (resolver con `git log -1 --format=%H -- docs/evidence/L01/REPORT.md`). No hay implementación web ni prueba bancaria en esta entrega.

## Resultado inicial documental

| Trazabilidad | Pasos y esperado | Observado | Resultado |
| --- | --- | --- | --- |
| L01-UC01 → AC01 → TC01 | Leer f0UZM por MCP, contrastar secciones, fuentes, assets y tamaños con archivos | Siete secciones identificadas; Inter y 19 assets inventariados con hash, dimensiones de PNG y procedencia/licencia explícita; ver ASSETS.json e índice Pen | PASS |
| L01-UC02 → AC02 → TC02 | Contrastar cada afirmación con PRODUCT_BASE/CONTEXT y plan aprobado | Matriz conservar/corregir/retirar cubre hero, pasos, cinco beneficios, pagador, CTA y footer; incluye contradicciones en bitmaps | PASS |
| L01-UC03 → AC03 → TC03 | Revisar enlaces sin demo/contacto/legal confirmados | CTA interno establecido; destinos pendientes con responsable por asignar y condición de habilitación; ninguna URL externa inventada | PASS |

Completitud documental: 3/3 AC obligatorios = 100%. No acredita aprobación humana de L01 ni desbloquea L02. Los pendientes registrados en AC03 siguen pendientes en los tickets correspondientes.

## VC01

Resultado inicial de documento/inventario. [Referencia entregada](../../landing/IMPLEMENTATION_REFERENCE.md), [inventario](../../landing/ASSETS.json), [comparación visual navegable](review.html), [capturas Pen originales](../../design/landing/2026-11-25/README.md). El HTML es un informe para revisar decisiones, no la landing implementada. No existe un antes de código ni una UI nueva que capturar; se muestra diseño original frente a copy preparado. La aceptación humana del informe se realizará en el PR.

Revisión visual: capturas originales sin modificación; diferencias de copy enumeradas en la matriz. El hero no se usa como bitmap de página. Antes/después de implementación, móvil y accesibilidad de la web se verificarán en sus tickets, no se marcan aprobados aquí.

## Checks y aplicabilidad

- Comando Python reproducible al final del reporte: inventario de 19 assets y hashes, 12 capturas y hashes, enlaces locales del informe/referencia. Código 0 en ejecución local; conservar salida en el PR.
- `git diff --check`: sin errores.
- TDD: No aplica, conforme a L01; no existe comportamiento de aplicación añadido. La verificación estructural no sustituye los tres TC manuales anteriores.
- Ruff/mypy/pytest/Postgres/build Astro: No aplica a esta entrega documental; no se modifica backend ni se instala una aplicación web.
- Review Standards/Spec del commit candidato: resultados se registran en el PR y deben aprobar antes de entrega. Cualquier hallazgo obliga a corregir y revalidar.

## Comando de comprobación documental

Desde la raíz del repositorio:

```sh
python3 - <<'PY'
import hashlib
import json
import re
from pathlib import Path

root = Path.cwd()
assets = json.loads((root / 'docs/landing/ASSETS.json').read_text())['assets']
for asset in assets:
    path = root / asset['path']
    assert path.is_file(), path
    assert hashlib.sha256(path.read_bytes()).hexdigest() == asset['sha256'], path
manifest = root / 'docs/design/landing/2026-11-25/manifest.json'
images = json.loads(manifest.read_text())['images']
for image in images:
    path = manifest.parent / image['file']
    assert hashlib.sha256(path.read_bytes()).hexdigest() == image['sha256'], path
for path in [root / 'docs/landing/IMPLEMENTATION_REFERENCE.md', root / 'docs/evidence/L01/REPORT.md']:
    for link in re.findall(r'\]\(([^)]+)\)', path.read_text()):
        if not link.startswith('https:'):
            assert (path.parent / link.split('#')[0]).exists(), link
print(f'PASS: {len(assets)} assets, {len(images)} capturas, hashes y enlaces locales')
PY
```
