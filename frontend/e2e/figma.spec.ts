import { expect, test, type Page } from "@playwright/test";

/**
 * Abgleich mit den Figma-Frames (SIN-1463) gegen ein echtes Backend mit der Beispielmaschine FB-01:
 * dunkle Seitenleiste (Desktop 1440), lesbarer Signalweg (>= 12 px ohne Zoom), Maschinenliste als Karten (Mobile 390).
 * Laeuft nur mit E2E_API_URL; E2E_SCREENSHOT_DIR schreibt die Screenshots fuer den PR.
 */
const API = process.env.E2E_API_URL;
const SHOTS = process.env.E2E_SCREENSHOT_DIR;
const MIN_TEXT_PX = 12;

test.skip(!API, "E2E_API_URL nicht gesetzt");

async function shot(page: Page, name: string) {
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/${name}.png` });
}

async function machineId(page: Page): Promise<string> {
  const machines: { id: string; name: string }[] = await (await page.request.get(`${API}/api/machines`)).json();
  const fb01 = machines.find((m) => /FB-01/.test(m.name));
  expect(fb01, "Beispielmaschine FB-01 im Backend").toBeTruthy();
  return fb01!.id;
}

test("Seitenleiste: dunkel, 280 px, Werte aus dem Figma-Frame Rail", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop-1440");
  await page.goto("/werk/maschinen");
  const rail = page.getByTestId("rail-full").locator("nav");
  await expect(rail).toBeVisible();
  await expect(rail).toHaveCSS("background-color", "rgb(18, 21, 27)");
  expect((await rail.boundingBox())!.width).toBe(280);
  await expect(page.getByTestId("rail-full").getByText(/^Maschinen · [1-9]\d*$/)).toBeVisible();
  await expect(page.getByTestId("rail-full").getByRole("link", { name: "Alle Maschinen" })).toHaveCSS("font-size", "14px");
  await expect(page.locator("tbody tr").first()).toBeVisible();
  await shot(page, "desktop-1440-maschinen");

  // Die Umschaltung bleibt, die Seitenleiste bleibt auch im dunklen Design dunkel
  await page.getByRole("button", { name: "Dunkles Design" }).first().click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expect(rail).toHaveCSS("background-color", "rgb(18, 21, 27)");
});

test("Signalweg: Knotentext ohne Zoom mindestens 12 px", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop-1440");
  const id = await machineId(page);
  await page.goto(`/werk/maschine/${id}?bereich=aufbau&tab=signalweg&tag=${encodeURIComponent("-S1")}`);
  const nodes = page.locator(".react-flow__node-signal");
  await expect(nodes.first()).toBeVisible({ timeout: 30_000 });
  await page.waitForTimeout(500);

  const sizes = await page.evaluate(() => {
    const viewport = document.querySelector(".react-flow__viewport") as HTMLElement;
    const zoom = new DOMMatrixReadOnly(getComputedStyle(viewport).transform).a;
    const texts: { text: string; px: number }[] = [];
    for (const node of document.querySelectorAll(".react-flow__node-signal, .react-flow__node-header")) {
      for (const el of node.querySelectorAll("span, div")) {
        const own = [...el.childNodes].filter((n) => n.nodeType === Node.TEXT_NODE && n.textContent?.trim());
        if (own.length === 0) continue;
        texts.push({ text: el.textContent!.trim().slice(0, 30), px: parseFloat(getComputedStyle(el).fontSize) * zoom });
      }
    }
    return { zoom, texts };
  });
  expect(sizes.texts.length).toBeGreaterThan(0);
  const smallest = Math.min(...sizes.texts.map((t) => t.px));
  testInfo.annotations.push({ type: "kleinster Knotentext", description: `${smallest.toFixed(1)} px bei Zoom ${sizes.zoom.toFixed(2)}` });
  expect(smallest, JSON.stringify(sizes.texts.filter((t) => t.px < MIN_TEXT_PX))).toBeGreaterThanOrEqual(MIN_TEXT_PX);
  await shot(page, "desktop-1440-signalweg");
});

test("Maschinenliste am Handy: Karten mit Dokumentation, Fehler und Kennzahl", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile-390");
  await page.goto("/werk/maschinen");
  const cards = page.getByTestId("machine-cards");
  await expect(cards).toBeVisible();
  await expect(cards.getByText("Dokumentation").first()).toBeVisible();
  await expect(cards.getByText("Fehler").first()).toBeVisible();
  await expect(cards.getByText("Kennzahl").first()).toBeVisible();
  await expect(page.locator("table")).toBeHidden();
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(0);
  await shot(page, "mobile-390-maschinen");
});
