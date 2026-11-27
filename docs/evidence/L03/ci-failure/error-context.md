# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: quality-probe.spec.ts >> L03-TC03: fallo controlado para verificar artefactos CI
- Location: tests/quality-probe.spec.ts:3:1

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByRole('link', { name: 'Destino inexistente' })
Expected: visible
Timeout: 100ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" getByRole('link', { name: 'Destino inexistente' }) with timeout 100ms
  - waiting for getByRole('link', { name: 'Destino inexistente' })

```

```yaml
- banner:
  - link "Tappy, inicio":
    - /url: /
    - text: Tappy
- main:
  - heading "Cobra con claridad. Entrega cuando el pago esté confirmado." [level=1]
  - paragraph: Tappy está diseñado para ayudarte a solicitar cobros y consultar su recepción. El dinero llega a la cuenta bancaria de tu comercio.
  - link "Cómo funciona":
    - /url: "#como-funciona"
  - region "Del importe a la confirmación, paso a paso.":
    - heading "Del importe a la confirmación, paso a paso." [level=2]
    - paragraph: Captura el importe, genera la solicitud por un canal habilitado y comprueba la recepción antes de entregar.
```

# Test source

```ts
  1  | import { expect, test } from "@playwright/test";
  2  | 
  3  | test("L03-TC03: fallo controlado para verificar artefactos CI", async ({
  4  |   page,
  5  | }) => {
  6  |   await page.goto("/");
  7  |   await expect(
  8  |     page.getByRole("link", { name: "Destino inexistente" }),
> 9  |   ).toBeVisible({ timeout: 100 });
     |     ^ Error: expect(locator).toBeVisible() failed
  10 | });
  11 | 
```