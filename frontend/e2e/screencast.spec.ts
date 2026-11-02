import { mkdirSync } from "node:fs";
import { resolve } from "node:path";

import { expect, test, type Page } from "@playwright/test";

/**
 * Screencast (SIN-1432): nimmt den Demo-Ablauf aus docs/product/demo.md als Video auf, 1280x720, ohne Modellaufruf.
 * Laeuft nur mit SCREENCAST=1 und gegen die laufende Compose-Demo (FB-01), nie in der CI.
 *
 *   SCREENCAST=1 E2E_API_URL=http://localhost:8010 E2E_BASE_URL=http://localhost:3100 \
 *     npx playwright test e2e/screencast.spec.ts --project=desktop-1440
 * Ausgabe: SCREENCAST_DIR (Standard ../tmp/screencast) / rohvideo.webm; Schneiden: scripts/screencast.sh.
 */
const API = process.env.E2E_API_URL?.replace(/\/$/, "");
const OUT = resolve(process.cwd(), process.env.SCREENCAST_DIR ?? "../tmp/screencast");
const MACHINE = "Foerderband FB-01";
const PAUSE = 3_000;

async function warte(page: Page, ms = PAUSE) {
  await page.waitForTimeout(ms);
}

test("Screencast: FB-01 von der Uebersicht bis zum Signalweg", async ({ browser }) => {
  test.skip(process.env.SCREENCAST !== "1" || !API, "SCREENCAST=1 und E2E_API_URL fehlen: keine Aufnahme");
  test.setTimeout(5 * 60_000);
  mkdirSync(OUT, { recursive: true });

  const machines = (await (await fetch(`${API}/api/machines`)).json()) as { id: string; name: string }[];
  const machine = machines.find((m) => m.name === MACHINE);
  expect(machine, `Maschine ${MACHINE} im Backend`).toBeTruthy();

  const context = await browser.newContext({
    viewport: { width: 1280, height: 720 },
    recordVideo: { dir: OUT, size: { width: 1280, height: 720 } },
  });
  const page = await context.newPage();
  const fehler: string[] = [];
  page.on("pageerror", (e) => fehler.push(e.message));

  // 1. Maschinenuebersicht
  await page.goto("/werk/maschinen");
  await expect(page.getByText(MACHINE).first()).toBeVisible();
  await warte(page);
  // 2. Maschine oeffnen: Stoerfaelle
  await page.getByText(MACHINE).first().click();
  await expect(page).toHaveURL(new RegExp(`/werk/maschine/${machine!.id}`));
  await warte(page);
  // 3. Aufbau: Bauteil im Modell antippen, Steckbrief mit Quelle
  await page.goto(`/werk/maschine/${machine!.id}?bereich=aufbau`);
  await page.locator('button.part-chip[data-tag="-M1"]').click();
  await expect(page.getByTestId("part-sheet")).toBeVisible();
  await warte(page, 4_000);
  // 4. SPS: Warum kommt A4.0 nicht?
  await page.goto(`/werk/maschine/${machine!.id}?bereich=aufbau&tab=sps`);
  await page.getByLabel("Ausgang für „Warum kommt … nicht?“").fill("A4.0");
  await page.getByRole("button", { name: "Warum?" }).click();
  await expect(page.getByTestId("why-result").getByTestId("why-tree")).toBeVisible();
  await warte(page, 5_000);
  // 5. Signalweg vom Taster -S1 zum Motor
  await page.goto(`/werk/maschine/${machine!.id}?bereich=aufbau&tab=signalweg&tag=${encodeURIComponent("-S1")}`);
  await expect(page.getByTestId("model-panel").getByText(/-M1/).first()).toBeVisible();
  await warte(page, 6_000);

  const video = page.video();
  await context.close();
  await video?.saveAs(resolve(OUT, "rohvideo.webm"));
  expect(fehler, "keine Seitenfehler im Video").toEqual([]);
});
