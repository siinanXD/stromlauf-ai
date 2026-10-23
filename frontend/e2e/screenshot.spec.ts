import { expect, test } from "@playwright/test";

/**
 * Screenshot der Maschinenseite FB-01 mit Stoerfall-Antwort und Belegen (SIN-976) fuer docs/assets/maschinenseite.png.
 * Laeuft nur im Compose-Job: E2E_BASE_URL (Frontend), E2E_API_URL (Backend im Demo-Modus) und E2E_SCREENSHOT=<Zieldatei>.
 * Die Frage kostet eine Modellantwort, deshalb braucht das Backend ANTHROPIC_API_KEY.
 */
const API = process.env.E2E_API_URL;
const TARGET = process.env.E2E_SCREENSHOT;
const MACHINE = process.env.E2E_MACHINE ?? "Foerderband FB-01";

test.describe("Screenshot Maschinenseite", () => {
  test.skip(!API || !TARGET, "E2E_API_URL oder E2E_SCREENSHOT nicht gesetzt");

  test("FB-01 mit Antwort und Belegen", async ({ page }) => {
    test.setTimeout(300_000);
    await page.goto("/werk/maschinen");
    await page.getByLabel("Maschinen filtern").fill(MACHINE);
    await page.getByRole("link", { name: MACHINE, exact: true }).click();
    await page.waitForURL(/\/werk\/maschine\/[^/?]+/);
    await expect(page.getByRole("heading", { level: 1, name: MACHINE })).toBeVisible();

    const input = page.getByTestId("incident-input");
    await input.fill("-K1 zieht nicht an");
    await input.press("Enter");
    await expect(page.getByTestId("referenced-parts")).toBeVisible({ timeout: 240_000 });
    await page.waitForTimeout(1_000);
    await page.screenshot({ path: TARGET, fullPage: false });
  });
});
