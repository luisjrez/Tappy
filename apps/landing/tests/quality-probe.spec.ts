import { expect, test } from "@playwright/test";

test("L03-TC03: fallo controlado para verificar artefactos CI", async ({
  page,
}) => {
  await page.goto("/");
  await expect(
    page.getByRole("link", { name: "Destino inexistente" }),
  ).toBeVisible({ timeout: 100 });
});
