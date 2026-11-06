import { mkdirSync } from "node:fs";
import { resolve } from "node:path";

import { expect, test, type Page } from "@playwright/test";

/**
 * Nutzerwege (SIN-1458): FB-01 in der laufenden Demo wie ein Mensch durchspielen, nur ueber die Oberflaeche, ohne
 * api-mock.ts. Aufruf ueber `npm run test:nutzerweg` (scripts/nutzerweg.mjs), das LIVE_URL prueft und die Ergebnisse
 * je Weg zusammenfasst. Jeder Weg prueft fachliche Werte (Fehlereintrag, Fundstelle, Planseite), nicht nur "Seite laedt".
 *
 * Kein Modellaufruf: POST /api/chat wird abgefangen (NUTZERWEG_CHAT=1 laesst ihn durch und kostet Geld). Was ohne Modell
 * antwortet, ist die Fehlerliste, die Befundkarte und der Signalweg; der Antworttext selbst ist dann ungeprueft.
 * Je Weg entsteht ein Screenshot in NUTZERWEG_DIR (Standard ../tmp/nutzerweg), auch bei Rot.
 * Welcher Weg zu welchem Figma-Frame gehoert: docs/product/nutzerweg.md.
 */
const OUT = resolve(process.cwd(), process.env.NUTZERWEG_DIR ?? "../tmp/nutzerweg");
const MACHINE = /F(ö|oe)rderband FB-01/;
const MELDUNG = "Störung Motorschutz Förderband";
const CHAT = process.env.NUTZERWEG_CHAT === "1";
const LIVE = Boolean(process.env.E2E_API_URL);

// Nur gegen die laufende Demo (scripts/nutzerweg.mjs setzt E2E_API_URL); die Mock-CI hat kein Backend und ueberspringt sie.
test.skip(!LIVE, "E2E_API_URL nicht gesetzt: Nutzerwege brauchen die laufende Demo (npm run test:nutzerweg)");

test.beforeAll(() => mkdirSync(OUT, { recursive: true }));

test.beforeEach(async ({ page }) => {
  if (CHAT) return;
  await page.route("**/api/chat", (route) =>
    route.request().method() === "POST" ? route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Nutzerweg ohne Modell" }) }) : route.continue(),
  );
});

test.afterEach(async ({ page }, testInfo) => {
  const slug = testInfo.title.split(":")[0].trim().replace(/\s+/g, "-").toLowerCase();
  const path = resolve(OUT, `${slug}.png`);
  await page.screenshot({ path });
  await testInfo.attach("screenshot", { path, contentType: "image/png" });
});

/** Von der Maschinenuebersicht aus, wie ein Mensch: FB-01 antippen. */
async function openMachine(page: Page) {
  await page.goto("/werk/maschinen");
  await page.getByText(MACHINE).first().click();
  await expect(page).toHaveURL(/\/werk\/maschine\//);
  await expect(page.getByRole("heading", { level: 1, name: MACHINE })).toBeVisible();
}

async function report(page: Page) {
  const input = page.getByTestId("incident-input");
  await input.fill(MELDUNG);
  await input.press("Enter");
}

/** Meldung, Fehlereintrag E-F2 oeffnen, dessen Bauteil -F2 oeffnen: Detailspalte zeigt Bauteil mit Befundkarte. */
async function openFaultPart(page: Page) {
  await openMachine(page);
  await report(page);
  await page.getByTestId("block-faults").getByRole("button", { name: /E-F2/ }).click();
  await page.getByTestId("fault-detail").getByRole("button", { name: "Bauteil -F2 öffnen" }).click();
  const part = page.getByTestId("part-detail");
  await expect(part).toBeVisible();
  return part;
}

test("1-maschine-oeffnen: Maschinenuebersicht fuehrt zu den Stoerfaellen von FB-01", async ({ page }) => {
  await openMachine(page);
  await expect(page.getByTestId("incident-input")).toBeVisible();
  await expect(page.getByTestId("area-aufbau")).toBeVisible();
});

test("2-stoerfall-melden: Meldung findet den Fehlereintrag E-F2 mit Ursache", async ({ page }) => {
  await openMachine(page);
  await report(page);
  const faults = page.getByTestId("block-faults");
  await expect(faults).toBeVisible();
  await expect(faults).toContainText("E-F2");
  await expect(faults).toContainText(/Motorschutz -F2 ausgel(ö|oe)st/);
  // Haftungszeile unter dem Eingabefeld (SIN-1218)
  await expect(page.getByTestId("haftungszeile")).toHaveText("Belegte Hinweise; Prüfung durch Elektrofachkraft nach den 5 Sicherheitsregeln");
});

test("3-quelle-der-antwort: Fehlereintrag nennt Fundstelle Stromlaufplan Blatt 3, die Planseite oeffnet", async ({ page }) => {
  await openMachine(page);
  await report(page);
  await page.getByTestId("block-faults").getByRole("button", { name: /E-F2/ }).click();
  await expect(page.getByTestId("fault-detail")).toContainText("Stromlaufplan Blatt 3");

  const part = await openFaultPart(page);
  const card = part.getByTestId("part-fact-card");
  await expect(card).toContainText("/3.2");
  await card.getByRole("button", { name: /\/3\.2/ }).first().click();
  const viewer = page.getByRole("dialog", { name: /01_Stromlaufplan_FB-01\.pdf, Seite \d+/ });
  await expect(viewer).toBeVisible();
  await expect(viewer.getByRole("img", { name: /01_Stromlaufplan_FB-01\.pdf, Seite \d+/ })).toBeVisible();
});

/** Bauteil -F2 im Stoerfall, dann "Signalweg oeffnen" (Figma: Detail -F2 -> Signalweg Vollbild). */
async function openSignal(page: Page) {
  await openFaultPart(page);
  await page.getByTestId("detail-pane").getByRole("button", { name: "Signalweg öffnen" }).click();
  const detail = page.getByTestId("detail-pane");
  await expect(detail).toHaveAttribute("data-detail", "signal");
  return detail;
}

test("4-signalweg-oeffnen: Signalweg von -F2 laeuft ueber -X3:3, E0.2 und A4.0 bis zum Motor -M1", async ({ page }) => {
  const detail = await openSignal(page);
  // Hauptweg seit Issue #121 (vorwaerts gewinnt der Weg zum Motor): Figma "Desktop · Signalweg Vollbild" und
  // design/figma/beispiele/signalweg.json zeigen noch den aelteren Weg ueber NW 4 zu -H2, siehe docs/product/nutzerweg.md
  await expect(detail.getByText(/Hauptweg von -F2 bis -M1/)).toBeVisible();
  for (const re of [/-X3:3/, /E0\.2/, /FB 10 NW 1/, /A4\.0/, /-X3:9/, /-K1/, /-X4:U/]) await expect(detail.getByText(re).first(), `sichtbar: ${re}`).toBeVisible();
});

test("5-signalweg-quelle: Planseite zum Signalweg oeffnet gross, Stromlaufplan Blatt 3", async ({ page }) => {
  const detail = await openSignal(page);
  const plan = detail.getByRole("region", { name: "Planseite" });
  await expect(plan).toContainText("Seite 3");
  await plan.getByRole("button", { name: "Groß öffnen" }).click();
  const viewer = page.getByRole("dialog", { name: "01_Stromlaufplan_FB-01.pdf, Seite 3" });
  await expect(viewer).toBeVisible();
  await expect(viewer.getByRole("img", { name: "01_Stromlaufplan_FB-01.pdf, Seite 3" })).toBeVisible();
});
