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

test("Verlauf nach Reload: Chips, Belegbilder und Markierung ohne neue Frage (Issue #47)", async ({ page }) => {
  await page.goto(`/werk/maschine/${MACHINE_ID}?tab=chat`);
  const composer = page.getByPlaceholder(/Frag etwas zu/);
  await composer.fill("-K1 zieht nicht an");
  await composer.press("Enter");
  await expect(page.getByTestId("referenced-parts")).toBeVisible();
  await expect(page.getByRole("combobox", { name: "Chatverlauf wählen" })).toHaveValue("conv-1");

  await page.reload();
  // der zuletzt geoeffnete Chat ist wieder gewaehlt, sein Verlauf kommt aus GET /messages mit meta
  await expect(page.getByRole("combobox", { name: "Chatverlauf wählen" })).toHaveValue("conv-1");
  await expect(page.getByTestId("referenced-parts")).toBeVisible();
  await expect(page.getByTestId("referenced-parts").getByRole("button", { name: "Bauteil -K1 öffnen" })).toBeVisible();
  await expect(page.getByTestId("evidence-row").locator("img")).toHaveCount(2);
  await expect(page.getByTestId("citations-valid")).toContainText("Belege: 1 von 3 gültig");
  const zones = page.getByRole("list", { name: "Zonen der Maschine" });
  await expect(zones.locator('li[data-zone="+ST1"]')).toHaveAttribute("data-lit", "true");
  await expect(zones.locator('button.part-chip[data-tag="-K1"]')).toHaveAttribute("data-referenced", "true");
  // Kosten gibt es im Verlauf nicht (bekannte Grenze), die Antwort selbst ist vollstaendig da
  await expect(page.getByText("Kosten dieser Antwort")).toHaveCount(0);
  await expect(page.getByText("Spule von -K1 an A1/A2 messen")).toBeVisible();

  // "Neuer Chat" vergisst die Auswahl: nach Reload wieder leer
  await page.getByRole("button", { name: "Neuer Chat" }).click();
  await page.reload();
  await expect(page.getByRole("combobox", { name: "Chatverlauf wählen" })).toHaveValue("");
  await expect(page.getByTestId("referenced-parts")).toHaveCount(0);
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

  // Zitat-Resolver (Issue #46): ungueltige Belege (Span ohne Ziel und klickbarer PDF-Chip) tragen den Grund fuer
  // Screenreader und Tooltip, der Fuss zaehlt und listet die Gruende auf
  await expect(page.locator('span[data-invalid="true"]').first()).toContainText("Beleg ungültig: Kennzeichen -X9 nicht in 02_Stueckliste_FB-01.xlsx");
  await expect(page.locator('button[data-invalid="true"]').first()).toHaveAccessibleName(/Beleg ungültig: Seite 9 nicht in 01_Stromlaufplan_FB-01.pdf/);
  await expect(page.getByTestId("citations-valid")).toContainText("Belege: 1 von 3 gültig");
  await page.getByTestId("citations-valid").locator("summary").click();
  await expect(page.getByTestId("citations-valid").getByRole("listitem")).toHaveCount(2);

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
