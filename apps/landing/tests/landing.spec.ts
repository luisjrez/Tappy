import { expect, test } from "@playwright/test";

test("L02-TC01: la raíz entrega HTML con título Tappy", async ({ request }) => {
  const response = await request.get("/");
  expect(response.status()).toBe(200);
  expect(response.headers()["content-type"]).toContain("text/html");
  expect(await response.text()).toMatch(/<title>Tappy[^<]*<\/title>/);
});

test("L02-TC02: contenido y navegación disponibles sin JavaScript", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "Cobra con claridad",
  );
  await page.getByRole("link", { name: "Cómo funciona", exact: true }).click();
  await expect(page).toHaveURL(/#como-funciona$/);
  await expect(page.locator("#como-funciona")).toBeVisible();
});

test("L02-TC03: una ruta inexistente ofrece regreso al inicio con estado 404", async ({
  page,
}) => {
  const response = await page.goto("/ruta-inexistente");
  expect(response?.status()).toBe(404);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "Esta página no existe",
  );
  await page.getByRole("link", { name: "Volver al inicio" }).click();
  await expect(page).toHaveURL("/");
});

for (const viewport of [
  { width: 360, height: 800 },
  { width: 768, height: 1024 },
  { width: 1440, height: 900 },
]) {
  test(`L02-VC01: evidencia inicial ${viewport.width}`, async ({ page }) => {
    await page.setViewportSize(viewport);
    for (const [route, name] of [
      ["/", "inicio"],
      ["/ruta-inexistente", "404"],
    ]) {
      await page.goto(route);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      await page.screenshot({
        path: `../../docs/evidence/L02/${name}-${viewport.width}.png`,
        fullPage: true,
      });
    }
  });
}
