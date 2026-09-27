import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

import { MACHINE_ID, mockApi, patched } from "./api-mock";

test.beforeEach(async ({ page }) => {
  patched.length = 0;
  await mockApi(page);
});

async function ask(page: import("@playwright/test").Page) {
  await page.goto(`/werk/maschine/${MACHINE_ID}?tab=chat`);
  await expect(page.getByRole("list", { name: "Zonen der Maschine" })).toBeVisible();
  const composer = page.getByPlaceholder(/Frag etwas zu/);
  await composer.fill("-K1 zieht nicht an");
  await composer.press("Enter");
  await expect(page.getByTestId("referenced-parts")).toBeVisible();
}

test("Sheet öffnet aus Chat-Chip, Modell-Chip und Belegbild; Esc schließt, Fokus kehrt zurück", async ({ page }) => {
  await ask(page);
  const chip = page.getByTestId("referenced-parts").getByRole("button", { name: "Bauteil -K1 öffnen" });
  await chip.click();
  const sheet = page.getByTestId("part-sheet");
  await expect(sheet).toBeVisible();
  await expect(sheet.getByRole("heading", { name: "Hauptschütz" })).toBeVisible();
  await expect(sheet.getByTestId("datasheet-missing")).toBeVisible(); // nur Stromlaufplan/Stueckliste, kein Handbuch
  await expect(sheet.getByRole("list", { name: "Verbundene Bauteile" }).getByRole("button", { name: "Bauteil -F2 öffnen" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(sheet).toBeHidden();
  await expect(chip).toBeFocused();

  // Modell-Chip (openPart hat auf Schaltschrank umgeschaltet: zurueck zum Schema)
  await page.getByRole("tab", { name: "Schema" }).click();
  await page.getByRole("list", { name: "Zonen der Maschine" }).locator('button.part-chip[data-tag="-M1"]').click();
  await expect(page.getByTestId("part-sheet")).toBeVisible();
  await expect(page.getByTestId("part-sheet").getByRole("heading", { name: /Getriebemotor|Bauteil -M1/ })).toBeVisible();
  await page.getByRole("button", { name: "Datenblatt schließen" }).click();
  await expect(page.getByTestId("part-sheet")).toBeHidden();

  // Belegbild (Foto)
  await page.getByTestId("evidence-cabinet").getByRole("button").click();
  await expect(page.getByTestId("part-sheet")).toBeVisible();
  await expect(page.getByTestId("part-sheet").getByRole("heading", { name: "Hauptschütz" })).toBeVisible();

  const axe = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  expect(axe.violations, JSON.stringify(axe.violations, null, 1)).toEqual([]);
});

test("Lightbox: Rahmen per Tastatur verschieben und speichern, bleibt nach Reload", async ({ page }) => {
  await ask(page);
  await page.getByTestId("referenced-parts").getByRole("button", { name: "Bauteil -K1 öffnen" }).click();
  await page.getByTestId("show-in-photo").click();
  const lightbox = page.getByTestId("cabinet-lightbox");
  await expect(lightbox).toBeVisible();
  await expect(lightbox.getByRole("button", { name: /-K1, in der Antwort referenziert/ })).toBeVisible();

  const axe = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  expect(axe.violations, JSON.stringify(axe.violations, null, 1)).toEqual([]);

  await page.getByTestId("edit-box").click();
  const frame = page.getByTestId("edit-frame");
  await expect(frame).toBeFocused();
  for (let i = 0; i < 4; i++) await page.keyboard.press("ArrowRight");
  await page.keyboard.press("Shift+ArrowDown");
  await page.keyboard.press("Enter");
  await expect(frame).toBeHidden();
  expect(patched).toHaveLength(1);
  expect(patched[0].id).toBe("hs1");
  expect(patched[0].body.x as number).toBeCloseTo(0.22, 5);
  expect(patched[0].body.h as number).toBeCloseTo(0.125, 5);

  // Esc schliesst die Lightbox, danach ist die neue Position auch nach Reload da (Mock haelt den Zustand)
  await page.keyboard.press("Escape");
  await expect(lightbox).toBeHidden();
  await page.reload();
  await expect(page.getByRole("list", { name: "Zonen der Maschine" })).toBeVisible();
  await page.getByRole("list", { name: "Zonen der Maschine" }).locator('button.part-chip[data-tag="-K1"]').click();
  await page.getByTestId("show-in-photo").click();
  const box = page.getByTestId("cabinet-lightbox").locator('button[data-hotspot="hs1"]');
  await expect(box).toHaveCSS("left", /.+/);
  const left = await box.evaluate((el) => (el as HTMLElement).style.left);
  expect(left).toBe("22%");
  await expect(page.getByTestId("cabinet-lightbox").getByRole("list", { name: "Markierte Bauteile" })).toContainText("manuell");
});
