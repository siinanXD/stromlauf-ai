import { expect, test, type Page } from "@playwright/test";

/**
 * Abnahme-Durchlauf gegen ein echtes Backend (Staging oder lokal), ohne Mocks (Issue #29, Teil 2):
 * Login -> Maschinenuebersicht -> Maschine -> Aufbau/Modell -> Bauteil-Sheet -> Schaltschrankfoto
 * [-> Stoerfall mit Meldung -> Antwortbloecke -> Markierung im Modell].
 *
 * Laeuft nur mit E2E_API_URL (Backend-URL). E2E_BASE_URL zeigt auf ein laufendes Frontend (Vercel-Preview);
 * ohne E2E_BASE_URL startet playwright.config.ts den lokalen Server gegen E2E_API_URL.
 *   E2E_API_URL=http://127.0.0.1:8010 npx playwright test e2e/staging.spec.ts --project=desktop-1440
 * Login: meldet das Backend mode=jwt, braucht es AUTH_DEV_LINK=true und E2E_EMAIL; der Link steht dann in der Antwort.
 * Frage an den Agenten nur mit E2E_ASK=1 (eine bezahlte Antwort, laut docs/product/cost-model.md ca. 0,02 $).
 */

const API = process.env.E2E_API_URL?.replace(/\/$/, "");
const MACHINE = process.env.E2E_MACHINE ?? "Foerderband FB-01";
const EMAIL = process.env.E2E_EMAIL ?? "";
const ASK = process.env.E2E_ASK === "1";

type AuthMode = { mode: "jwt" | "legacy"; dev_link: boolean };
type MagicLink = { sent: boolean; dev_link: string | null };

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, { ...init, headers: { "content-type": "application/json", ...init?.headers } });
  if (!response.ok) throw new Error(`${init?.method ?? "GET"} ${path}: HTTP ${response.status} ${await response.text()}`);
  return (await response.json()) as T;
}

/** Magic-Link anfordern wie ein Mensch; im Entwicklungsmodus liefert das Backend den Link direkt zurueck. */
async function loginToken(): Promise<string | null> {
  const auth = await api<AuthMode>("/api/auth/mode");
  if (auth.mode !== "jwt") return null;
  if (!EMAIL) throw new Error("E2E_EMAIL fehlt: das Backend verlangt eine Anmeldung");
  const link = await api<MagicLink>("/api/auth/magic-link", { method: "POST", body: JSON.stringify({ email: EMAIL }) });
  if (!link.dev_link) throw new Error("Kein dev_link in der Antwort: fuer den E2E-Login braucht das Backend AUTH_DEV_LINK=true");
  const token = new URL(link.dev_link).searchParams.get("token");
  if (!token) throw new Error(`dev_link ohne token: ${link.dev_link}`);
  return token;
}

async function noHorizontalScroll(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow, "kein horizontaler Body-Scroll").toBeLessThanOrEqual(0);
}

test.describe("Abnahme gegen echtes Backend", () => {
  test.skip(!API, "E2E_API_URL nicht gesetzt: Durchlauf gegen ein echtes Backend uebersprungen");
  let token: string | null = null;

  test.beforeAll(async () => {
    token = await loginToken();
  });

  test("Login, Maschine, Modell, Bauteil-Sheet, Schaltschrankfoto", async ({ page }, testInfo) => {
    test.setTimeout(ASK ? 240_000 : 120_000);
    if (token) {
      await page.goto(`/login/exchange?token=${encodeURIComponent(token)}`);
      await page.waitForURL(/\/werk\/maschinen/, { timeout: 30_000 });
    } else {
      await page.goto("/werk/maschinen");
    }

    // Maschinenuebersicht: Demo-Maschine finden und oeffnen
    await page.getByLabel("Maschinen filtern").fill(MACHINE);
    await page.getByRole("link", { name: MACHINE, exact: true }).click();
    await page.waitForURL(/\/werk\/maschine\/[^/?]+/);
    const machineId = new URL(page.url()).pathname.split("/").pop() ?? "";
    testInfo.annotations.push({ type: "machine", description: `${MACHINE} (${machineId})` });

    // Maschinenansicht: Stoerfaelle zuerst, das Modell mit Zonen und Teilen liegt im Bereich Aufbau
    await expect(page.getByRole("heading", { level: 1, name: MACHINE })).toBeVisible();
    await expect(page.getByTestId("incident-list")).toBeVisible();
    await page.getByTestId("area-aufbau").click();
    await expect(page.getByTestId("model-panel")).toBeVisible();
    const zones = page.getByRole("list", { name: "Zonen der Maschine" });
    await expect(zones).toBeVisible();
    const chips = zones.locator("button.part-chip");
    await expect.poll(() => chips.count(), { message: "Modell zeigt mindestens ein Teil" }).toBeGreaterThan(0);
    testInfo.annotations.push({ type: "parts", description: `${await chips.count()} Teile im Modell` });
    await noHorizontalScroll(page);

    // Bauteil-Sheet aus dem Modell, Esc schliesst
    const firstTag = (await chips.first().getAttribute("data-tag")) ?? "";
    await chips.first().click();
    const sheet = page.getByTestId("part-sheet");
    await expect(sheet).toBeVisible();
    await expect(sheet.getByText(firstTag, { exact: false }).first()).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(sheet).toBeHidden();

    // Schaltschrankfoto laedt wirklich (naturalWidth > 0), nicht nur das img-Element; das Modell-Panel hat keinen tabpanel-Container
    await page.getByRole("tab", { name: "Schaltschrank" }).click();
    const photo = page.getByTestId("model-panel").locator("img").first();
    await expect(photo).toBeVisible();
    await expect.poll(() => photo.evaluate((img) => (img as HTMLImageElement).naturalWidth), { message: "Schaltschrankfoto geladen" }).toBeGreaterThan(0);
    await noHorizontalScroll(page);

    if (!ASK) {
      testInfo.annotations.push({ type: "frage", description: "uebersprungen (E2E_ASK=1 fuer eine bezahlte Antwort)" });
      return;
    }
    // Meldung als neuer Stoerfall: Antwort mit Bauteil-Block, "Im Modell zeigen" markiert die Teile
    await page.getByTestId("area-stoerfaelle").click();
    const input = page.getByTestId("incident-input");
    await input.fill("-K1 zieht nicht an");
    await input.press("Enter");
    await expect(page.getByTestId("referenced-parts")).toBeVisible({ timeout: 180_000 });
    await page.getByRole("button", { name: "Im Modell zeigen" }).click();
    await expect(page.getByTestId("highlight-count")).toContainText("markiert");
    await expect(zones.locator('button.part-chip[data-referenced="true"]').first()).toBeVisible();
  });
});
