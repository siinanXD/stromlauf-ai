import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

import { MACHINE_ID, mockApi } from "./api-mock";

test.beforeEach(async ({ page }) => {
  await mockApi(page);
});

async function noHorizontalScroll(page: import("@playwright/test").Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow, "kein horizontaler Body-Scroll").toBeLessThanOrEqual(0);
}

test("Maschinenansicht: Rail, Modell, Chat und Composer nach Breite", async ({ page }, testInfo) => {
  await page.goto(`/werk/maschine/${MACHINE_ID}?tab=chat`);
  await expect(page.getByRole("heading", { level: 1, name: "Förderband FB-01" })).toBeVisible();
  await expect(page.getByTestId("model-panel")).toBeVisible();
  await expect(page.getByPlaceholder(/Frag etwas zu/)).toBeVisible();
  await noHorizontalScroll(page);

  const width = page.viewportSize()!.width;
  if (width >= 1280) {
    await expect(page.getByTestId("rail-full")).toBeVisible();
    await expect(page.getByTestId("rail-full").getByRole("link", { name: /Förderband FB-01/ })).toBeVisible();
    await expect(page.getByTestId("rail-toggle")).toBeHidden();
  } else if (width >= 768) {
    await expect(page.getByTestId("rail-icons")).toBeVisible();
    await expect(page.getByTestId("rail-full")).toBeHidden();
  } else {
    await expect(page.getByTestId("rail-full")).toBeHidden();
    await page.getByTestId("rail-toggle").click();
    await expect(page.getByTestId("rail-drawer").getByRole("link", { name: /Förderband FB-01/ })).toBeVisible();
    await page.getByRole("button", { name: "Menü schließen" }).first().click();
    await expect(page.getByTestId("rail-drawer")).toBeHidden();
  }

  // Modell einklappen (Streifen) und wieder oeffnen
  await page.getByTestId("panel-toggle").click();
  await expect(page.getByTestId("model-panel")).toHaveAttribute("data-panel", "strip");
  await noHorizontalScroll(page);
  await page.getByTestId("panel-toggle").click();
  await expect(page.getByTestId("model-panel")).toHaveAttribute("data-panel", "open");
  testInfo.annotations.push({ type: "viewport", description: `${width}px` });
});

test("Antwort markiert -K1 im Modell, zeigt Belegbild, Chip löst openPart aus", async ({ page }) => {
  await page.goto(`/werk/maschine/${MACHINE_ID}?tab=chat`);
  await expect(page.getByRole("list", { name: "Zonen der Maschine" })).toBeVisible();
  const composer = page.getByPlaceholder(/Frag etwas zu/);
  await composer.fill("-K1 zieht nicht an");
  await composer.press("Enter");

  await expect(page.getByTestId("referenced-parts")).toBeVisible();
  await expect(page.getByTestId("referenced-parts").getByRole("button", { name: "Bauteil -K1 öffnen" })).toBeVisible();
  await expect(page.getByTestId("evidence-row").locator("img")).toHaveCount(2);
  await expect(page.getByTestId("evidence-cabinet")).toBeVisible();

  // Modell: -K1 und -F2 als referenziert markiert, Zone +ST1 leuchtet
  const zones = page.getByRole("list", { name: "Zonen der Maschine" });
  await expect(zones.locator('button.part-chip[data-tag="-K1"]')).toHaveAttribute("data-referenced", "true");
  await expect(zones.locator('button.part-chip[data-tag="-M1"]')).toHaveAttribute("data-referenced", "false");
  await expect(zones.locator('li[data-zone="+ST1"]')).toHaveAttribute("data-lit", "true");
  await expect(page.getByTestId("highlight-count")).toContainText("2 Bauteile aus der Antwort markiert");
  await expect(page.getByRole("status")).toContainText("2 Bauteile im Modell markiert");

  // Klick auf den Chip unter der Antwort -> openPart(tag): Datenblatt-Sheet, Bauteil gewaehlt, Schaltschrank-Ansicht (Hotspot vorhanden)
  await page.getByTestId("referenced-parts").getByRole("button", { name: "Bauteil -K1 öffnen" }).click();
  await expect(page.getByTestId("part-sheet")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("part-sheet")).toBeHidden();
  await expect(page.getByTestId("machine-page")).toHaveAttribute("data-open-part", "-K1");
  await expect(page.getByRole("tab", { name: "Schaltschrank" })).toHaveAttribute("aria-selected", "true");
  await noHorizontalScroll(page);
});

test("axe: keine Verstöße auf Start und Maschinenansicht", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Backend verbunden")).toBeVisible();
  const start = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  expect(start.violations, JSON.stringify(start.violations, null, 1)).toEqual([]);

  await page.goto(`/werk/maschine/${MACHINE_ID}?tab=chat`);
  await expect(page.getByRole("list", { name: "Zonen der Maschine" })).toBeVisible();
  const machine = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  expect(machine.violations, JSON.stringify(machine.violations, null, 1)).toEqual([]);
});
