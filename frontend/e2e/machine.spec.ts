import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

import { MACHINE_ID, mockApi } from "./api-mock";

async function noHorizontalScroll(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow, "kein horizontaler Body-Scroll").toBeLessThanOrEqual(0);
}

const wide = (page: Page) => page.viewportSize()!.width >= 1024;

/** Meldung eingeben: der Stoerfall steht sofort in der Liste, der Chat oeffnet (am Handy als eigene Ebene). */
async function report(page: Page, text = "Störung Motorschutz Förderband") {
  const input = page.getByTestId("incident-input");
  await input.fill(text);
  await input.press("Enter");
}

test.describe("ohne gespeicherte Störfälle", () => {
  test.beforeEach(async ({ page }) => {
    await mockApi(page, { withHistory: false });
  });

  test("Maschinenansicht: Rail, Störfälle und Aufbau nach Breite", async ({ page }, testInfo) => {
    await page.goto(`/werk/maschine/${MACHINE_ID}`);
    await expect(page.getByRole("heading", { level: 1, name: "Förderband FB-01" })).toBeVisible();
    await expect(page.getByTestId("incident-input")).toBeVisible();
    await expect(page.getByTestId("incidents-empty")).toContainText("Keine offenen Störfälle");
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

    // Aufbau ueber die Kopfzeile, die Zurueck-Geste fuehrt zu den Stoerfaellen
    await page.getByTestId("area-aufbau").click();
    await expect(page.getByTestId("model-panel")).toBeVisible();
    await expect(page.getByRole("tab", { name: "Modell" })).toHaveAttribute("aria-selected", "true");
    await expect(page.getByRole("list", { name: "Zonen der Maschine" })).toBeVisible();
    await noHorizontalScroll(page);
    await page.goBack();
    await expect(page.getByTestId("incident-input")).toBeVisible();
    testInfo.annotations.push({ type: "viewport", description: `${width}px` });
  });

  test("Meldung legt den Störfall sofort an; Fehlerliste, Antwortblöcke und Detail", async ({ page }) => {
    await page.goto(`/werk/maschine/${MACHINE_ID}`);
    await report(page);

    // Fehlerliste als erster Block, der Stoerfall bekommt die ID vom Server
    await expect(page.getByTestId("block-faults")).toBeVisible();
    await expect(page.getByTestId("block-faults")).toContainText("Band steht");
    await expect(page).toHaveURL(/fall=conv-1/);
    if (wide(page)) await expect(page.getByTestId("incident-list").locator('[data-incident="conv-1"]')).toHaveAttribute("aria-current", "true");

    // nach der Antwort: Bauteile, Signalweg, Plan, Schrank, Belege in fester Reihenfolge
    const parts = page.getByTestId("referenced-parts");
    await expect(parts.getByRole("button", { name: "Bauteil -K1 öffnen" })).toBeVisible();
    await expect(parts).toContainText("Motorschutz");
    await expect(page.getByTestId("citations-valid")).toContainText("Belege: 1 von 3 gültig");
    const blocks = await page.getByTestId("incident-chat").locator("[data-block]").evaluateAll((els) => els.map((el) => el.getAttribute("data-block")));
    expect(blocks).toEqual(["faults", "text", "parts", "signal", "plan", "cabinet", "citations"]);
    await page.getByTestId("block-plan").scrollIntoViewIfNeeded();
    await expect(page.getByTestId("block-plan")).toContainText("Blatt 3");
    await page.getByTestId("block-cabinet").scrollIntoViewIfNeeded();
    await expect(page.getByTestId("evidence-cabinet")).toBeVisible();

    // Zitat-Resolver (Issue #46): ungueltige Belege tragen den Grund fuer Screenreader und Tooltip
    await expect(page.locator('span[data-invalid="true"]').first()).toContainText("Beleg ungültig: Kennzeichen -X9 nicht in 02_Stueckliste_FB-01.xlsx");
    await page.getByTestId("citations-valid").locator("summary").click();
    await expect(page.getByTestId("citations-valid").getByRole("listitem")).toHaveCount(2);

    // Bauteil antippen: Detail mit Befundkarte; die Zurueck-Geste schliesst es wieder
    await parts.getByRole("button", { name: "Bauteil -K1 öffnen" }).click();
    const detail = page.getByTestId("detail-pane");
    await expect(detail).toBeVisible();
    await expect(detail.getByTestId("part-fact-card")).toContainText("/3.4");
    await expect(page.getByTestId("machine-page")).toHaveAttribute("data-open-part", "-K1");
    await noHorizontalScroll(page);
    await page.goBack();
    await expect(detail).toBeHidden();
    await expect(page.getByTestId("referenced-parts")).toBeVisible();
  });

  test("Erledigt mit Befund und wieder öffnen", async ({ page }) => {
    await page.goto(`/werk/maschine/${MACHINE_ID}`);
    await report(page);
    await expect(page.getByTestId("referenced-parts")).toBeVisible();
    await page.getByTestId("incident-header").getByRole("button", { name: "Erledigt" }).click();
    await page.getByLabel("Befund (optional)").fill("Motorschutz ausgelöst, zurückgesetzt");
    await page.getByRole("dialog").getByRole("button", { name: "Erledigt" }).click();
    await expect(page.getByTestId("incident-status")).toContainText("Erledigt");
    await expect(page.getByTestId("incident-status")).toContainText("Motorschutz ausgelöst, zurückgesetzt");
    await page.getByRole("button", { name: "Wieder öffnen" }).click();
    await expect(page.getByTestId("incident-status")).toContainText("Offen");
  });
});

test.describe("mit gespeichertem Störfall", () => {
  test.beforeEach(async ({ page }) => {
    await mockApi(page);
  });

  test("Verlauf nach Reload: Blöcke ohne neue Frage (Issue #47)", async ({ page }) => {
    await page.goto(`/werk/maschine/${MACHINE_ID}?fall=conv-1`);
    await expect(page.getByTestId("referenced-parts").getByRole("button", { name: "Bauteil -K1 öffnen" })).toBeVisible();
    await expect(page.getByTestId("citations-valid")).toContainText("Belege: 1 von 3 gültig");
    await expect(page.getByText("Spule von -K1 an A1/A2 messen")).toBeVisible();
    // Kosten gibt es im Verlauf nicht (bekannte Grenze)
    await expect(page.getByText("Kosten dieser Antwort")).toHaveCount(0);

    // "Im Modell zeigen" markiert die Bauteile im Aufbau
    await page.getByRole("button", { name: "Im Modell zeigen" }).click();
    const zones = page.getByRole("list", { name: "Zonen der Maschine" });
    await expect(zones.locator('button.part-chip[data-tag="-K1"]')).toHaveAttribute("data-referenced", "true");
    await expect(zones.locator('li[data-zone="+ST1"]')).toHaveAttribute("data-lit", "true");
  });

  test("Alte Links: ?tab=… öffnet den Aufbau, ?tab=chat die Störfälle", async ({ page }) => {
    await page.goto(`/werk/maschine/${MACHINE_ID}?tab=schaltschrank`);
    await expect(page.getByRole("tab", { name: "Schaltschrank" })).toHaveAttribute("aria-selected", "true");
    await page.goto(`/werk/maschine/${MACHINE_ID}?tab=chat`);
    await expect(page.getByTestId("incident-input")).toBeVisible();
    await expect(page.getByTestId("incident-list")).toContainText("-K1 zieht nicht an");
  });

  test("axe: keine Verstöße auf Start, Störfällen und Aufbau", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText("Backend verbunden")).toBeVisible();
    const start = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
    expect(start.violations, JSON.stringify(start.violations, null, 1)).toEqual([]);

    await page.goto(`/werk/maschine/${MACHINE_ID}?fall=conv-1`);
    await expect(page.getByTestId("referenced-parts")).toBeVisible();
    const incidents = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
    expect(incidents.violations, JSON.stringify(incidents.violations, null, 1)).toEqual([]);

    await page.goto(`/werk/maschine/${MACHINE_ID}?bereich=aufbau`);
    await expect(page.getByRole("list", { name: "Zonen der Maschine" })).toBeVisible();
    const aufbau = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
    expect(aufbau.violations, JSON.stringify(aufbau.violations, null, 1)).toEqual([]);
  });
});
