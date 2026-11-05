import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type Route } from "@playwright/test";

import { mockApi } from "./api-mock";

/** Gemockter Ablauf: POST /api/runs liefert Schritt 1 fertig, jedes GET einen Schritt mehr, das 8. GET den Abschluss. */

const KEYS = ["hochladen", "lesen", "maschine", "steckbrief", "modell", "zusammenfassung", "lernen", "fertig"] as const;
const LABELS = ["Hochladen", "Lesen", "Maschine", "Steckbrief", "Modell", "Zusammenfassung", "Lernen", "Fertig"];
const TRACE = "https://cloud.langfuse.com/trace/x";
const RUN_ID = "run-1";
// Zeiten relativ zu jetzt: ältere Zeiten ließen den Lauf als hängend gelten (haengt in knoten.ts).
const JETZT = new Date().toISOString();

const profile = {
  source_id: "s-run",
  source_name: "Förderband FB-01",
  documents: [{ id: "d1", filename: "01_Stromlaufplan_FB-01.pdf", doc_type: "schematic", status: "ready", page_count: 12, tag_count: 40 }],
  doc_types: [
    { doc_type: "schematic", present: true, filenames: ["01_Stromlaufplan_FB-01.pdf"] },
    { doc_type: "plc", present: true, filenames: ["04_SPS_Programm_FB-01.awl"] },
  ],
  sheets: [1, 2, 3],
  summary: { devices: 22, terminals: 14, plc_addresses: 9, gaps: 0 },
  gaps: [],
  coverage: [{ tag: "-K1", tag_type: "device", docs: { schematic: 2, plc: 1 } }],
};

function steps(fertig: number) {
  return KEYS.map((key, i) => ({
    key,
    label: LABELS[i],
    status: i < fertig ? "fertig" : i === fertig ? "laeuft" : "wartet",
    started_at: i <= fertig ? JETZT : null,
    finished_at: i < fertig ? JETZT : null,
    input: "",
    output: i < fertig ? "ok" : "",
    trace_url: TRACE,
    error: null,
  }));
}

function run(fertig: number, done: boolean, id = RUN_ID, name = "Förderband FB-01") {
  return {
    id,
    name,
    status: done ? "fertig" : "laeuft",
    model: "ollama:qwen3.5:9b",
    steps: steps(done ? KEYS.length : fertig),
    trace_url: TRACE,
    error: null,
    created_at: JETZT,
    finished_at: done ? JETZT : null,
    result: done
      ? {
          profile,
          map_counts: { zones: 5, parts: 22 },
          answers: [
            { question: "Welche Baugruppen gibt es?", answer_md: "Fünf Baugruppen.", sources: [] },
            { question: "Was schaltet -K1?", answer_md: "Den Motor -M1.", sources: [] },
            { question: "Wo steht der Motorschutz?", answer_md: "Im Schaltschrank +ST1.", sources: [] },
          ],
          machine_id: "m-fb01",
        }
      : { profile: null, map_counts: null, answers: null, machine_id: null },
  };
}

async function mockAblauf(page: Page) {
  await mockApi(page);
  let gets = 0;
  const json = (route: Route, body: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
  const kennzahl = (extra = {}) => ({ anzahl: 3, mittel_s: 10, median_s: 9, max_s: 12, letzter_s: 8, ziel_s: null, ueber_ziel: false, langsamster_run_id: null, langsamster_trace_url: null, ...extra });
  const zeiten = {
    laeufe: 3,
    schritte: Object.fromEntries(KEYS.map((key) => [key, kennzahl()])),
    gesamt: kennzahl(),
    fragen: kennzahl(),
  };
  zeiten.schritte.lesen = kennzahl({ median_s: 48, max_s: 75, letzter_s: 75, ziel_s: 60, ueber_ziel: true, langsamster_run_id: RUN_ID, langsamster_trace_url: TRACE });
  // spaeter registrierte Routen gelten zuerst
  await page.route("**/api/runs/zeiten", (route) => json(route, zeiten));
  await page.route("**/api/runs**", (route) => {
    const method = route.request().method();
    if (method === "POST") return json(route, run(1, false), 201);
    if (method === "GET" && route.request().url().includes(RUN_ID)) {
      gets += 1;
      return json(route, gets >= KEYS.length ? run(KEYS.length, true) : run(Math.min(gets + 1, KEYS.length - 1), false));
    }
    return route.fallback();
  });
}

test("Zeiten stehen auch vor dem ersten Lauf da", async ({ page }) => {
  await mockAblauf(page);
  await page.goto("/ablauf");
  await expect(page.getByRole("heading", { name: "Zeiten" })).toBeVisible();
  await expect(page.getByTestId("zeiten-lesen")).toBeVisible();
});

test("Förderband-Lauf wird in acht Schritten grün", async ({ page }) => {
  test.setTimeout(60_000);
  await mockAblauf(page);
  await page.goto("/ablauf");
  // genau eine Datei ohne Ordner: der direkte Weg ohne Vorschlag
  await page.setInputFiles('[data-testid="ablauf-dateien"]', "../examples/foerderband/01_Stromlaufplan_FB-01.pdf");
  await page.getByRole("button", { name: "Lauf starten" }).click();
  for (const key of KEYS) {
    await expect(page.getByTestId(`schritt-${key}`)).toHaveAttribute("data-status", "fertig", { timeout: 25_000 });
  }
  await page.getByTestId("schritt-zusammenfassung").click();
  await expect(page.getByRole("link", { name: "In Langfuse öffnen" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Maschine öffnen" })).toBeVisible();
  const lesen = page.getByTestId("zeiten-lesen");
  await expect(page.getByRole("heading", { name: "Zeiten" })).toBeVisible();
  await expect(lesen.getByRole("rowheader", { name: "Lesen je Dokument" })).toBeVisible();
  await expect(lesen.locator("[aria-label*='über Ziel']")).toBeVisible();
  await expect(lesen.getByRole("link", { name: "Langfuse" })).toHaveAttribute("href", TRACE);
  const axe = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  expect(axe.violations, JSON.stringify(axe.violations, null, 1)).toEqual([]);
});

test("Zwei Anlagen: Vorschlag bestätigen, zwei Läufe werden grün", async ({ page }) => {
  test.setTimeout(90_000);
  await mockAblauf(page);
  const gets: Record<string, number> = {};
  let posts = 0;
  let aufrufe = 0;
  const json = (route: Route, body: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
  const A = "01_Stromlaufplan_FB-01.pdf";
  const B = "01_Stromlaufplan_UR-01.pdf";
  await page.route("**/api/runs/gruppen", (route) =>
    json(route, {
      gruppen: [
        { name: "FB-01", quelle: "kennung", dateien: [A] },
        { name: "UR-01", quelle: "kennung", dateien: [B] },
      ],
      unzugeordnet: [],
      ignoriert: [],
    }),
  );
  await page.route("**/api/runs/run-*", (route) => {
    const id = route.request().url().split("/").pop()!;
    gets[id] = (gets[id] ?? 0) + 1;
    const name = id === "run-1" ? "FB-01" : "UR-01";
    return json(route, gets[id] >= KEYS.length ? run(KEYS.length, true, id, name) : run(Math.min(gets[id] + 1, KEYS.length - 1), false, id, name));
  });
  await page.route("**/api/runs", (route) => {
    if (route.request().method() !== "POST") return route.fallback();
    aufrufe += 1;
    // der zweite Aufruf scheitert einmal
    if (aufrufe === 2) return json(route, { detail: "Backend nicht erreichbar" }, 500);
    posts += 1;
    return json(route, run(1, false, `run-${posts}`, posts === 1 ? "FB-01" : "UR-01"), 201);
  });
  await page.goto("/ablauf");
  await page.setInputFiles('[data-testid="ablauf-dateien"]', [`../examples/foerderband/${A}`, `../examples/umroller/${B}`]);
  await expect(page.getByRole("heading", { name: "2 Anlagen erkannt" })).toBeVisible();
  await expect(page.getByLabel(`${A} verschieben nach`)).toBeVisible();
  const axeVorschlag = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  expect(axeVorschlag.violations, JSON.stringify(axeVorschlag.violations, null, 1)).toEqual([]);
  await page.getByRole("button", { name: "Alle starten" }).click();
  // Teilstart: Lauf 1 steht, der Vorschlag behält nur die gescheiterte Gruppe
  await expect(page.getByRole("alert").filter({ hasText: "Lauf für UR-01 konnte nicht gestartet werden" })).toBeVisible();
  await expect(page.getByTestId("lauf-run-1")).toBeVisible();
  await expect(page.getByRole("heading", { name: "1 Anlage erkannt" })).toBeVisible();
  await expect(page.getByLabel("Name der Anlage 1")).toHaveValue("UR-01");
  await page.getByRole("button", { name: "Alle starten" }).click();
  await expect(page.getByTestId("lauf-run-1")).toBeVisible();
  for (const id of ["run-1", "run-2"]) {
    const block = page.getByTestId(`lauf-${id}`);
    for (const key of KEYS) {
      await expect(block.getByTestId(`schritt-${key}`)).toHaveAttribute("data-status", "fertig", { timeout: 40_000 });
    }
  }
  expect(posts).toBe(2);
  // Kein Inhalt läuft über seinen Block hinaus (Überlappung mit dem nächsten Lauf); Bild als Beleg
  for (const id of ["run-1", "run-2"]) {
    const { hoehe, sichtbar } = await page.getByTestId(`lauf-${id}`).evaluate((el) => ({ hoehe: el.scrollHeight - el.clientHeight, sichtbar: el.clientHeight }));
    expect(sichtbar).toBeGreaterThan(0);
    expect(hoehe).toBeLessThanOrEqual(1);
  }
  const eins = (await page.getByTestId("lauf-run-1").boundingBox())!;
  const zwei = (await page.getByTestId("lauf-run-2").boundingBox())!;
  expect(eins.y + eins.height).toBeLessThanOrEqual(zwei.y + 1);
  await page.screenshot({ path: `test-results/ablauf-zwei-laeufe-${test.info().project.name}.png`, fullPage: true });
  const axe = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  expect(axe.violations, JSON.stringify(axe.violations, null, 1)).toEqual([]);
});

test("Lose Dateien bilden eine Anlage; Verschieben nur per Knopf, Fokus bleibt an der Datei", async ({ page }) => {
  await mockAblauf(page);
  const A = "01_Stromlaufplan_FB-01.pdf";
  const B = "01_Stromlaufplan_UR-01.pdf";
  await page.route("**/api/runs/gruppen", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ gruppen: [], unzugeordnet: [A, B], ignoriert: [] }) }),
  );
  await page.goto("/ablauf");
  await page.setInputFiles('[data-testid="ablauf-dateien"]', [`../examples/foerderband/${A}`, `../examples/umroller/${B}`]);
  await expect(page.getByRole("heading", { name: "1 Anlage erkannt" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Alle starten" })).toBeEnabled();
  const wahl = page.getByLabel(`${B} verschieben nach`);
  await wahl.selectOption("neu");
  // Auswahl allein verschiebt nichts
  await expect(page.getByRole("heading", { name: "1 Anlage erkannt" })).toBeVisible();
  await page.getByRole("button", { name: `${B} jetzt verschieben` }).click();
  await expect(page.getByRole("heading", { name: "2 Anlagen erkannt" })).toBeVisible();
  await expect(page.getByLabel(`${B} verschieben nach`)).toBeFocused();
  const axe = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  expect(axe.violations, JSON.stringify(axe.violations, null, 1)).toEqual([]);
});

/** Ordner mit einer erkannten Anlage (FB-01) und zwei losen Dateien; die Vorschau-Routen sind gemockt und protokollieren ihre Aufrufe. */
async function mockVorschlag(page: Page, opts: { aehnlichkeit: "ok" | "fehler" }) {
  await mockAblauf(page);
  const A = "01_Stromlaufplan_FB-01.pdf";
  const B = "01_Stromlaufplan_UR-01.pdf";
  const C = "03_Klemmenplan_FB-01.csv";
  const json = (route: Route, body: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
  const log: string[] = [];
  const geloescht: string[] = [];
  let lesestand = 0;
  await page.route("**/api/runs/gruppen", (route) =>
    json(route, { gruppen: [{ name: "FB-01", quelle: "kennung", dateien: [A] }], unzugeordnet: [B, C], ignoriert: [] }),
  );
  await page.route("**/api/runs/lesen", (route) => {
    const lose = (route.request().postData() ?? "").includes(B);
    log.push(lose ? "lesen:lose" : "lesen:FB-01");
    return json(
      route,
      lose
        ? { source_id: "q-lose", dateien: [{ pfad: B, document_id: "d-b" }, { pfad: C, document_id: "d-c" }] }
        : { source_id: "q-fb01", dateien: [{ pfad: A, document_id: "d-a" }] },
      201,
    );
  });
  await page.route("**/api/sources/q-*/documents", (route) => {
    log.push("lesestand");
    // beim ersten Abfragen ist noch nichts gelesen
    lesestand += 1;
    return json(route, [{ id: "d", source_id: "q", filename: "x", doc_type: "auto", status: lesestand <= 2 ? "processing" : "ready", progress: "", error: null, page_count: 1, vision_enrichment: false }]);
  });
  await page.route("**/api/runs/aehnlichkeit", (route) => {
    log.push("aehnlichkeit");
    if (opts.aehnlichkeit === "fehler") return json(route, { detail: "Gruppennamen müssen verschieden sein" }, 400);
    return json(route, [
      { pfad: B, vorschlag: "FB-01", wert: 0.83, herkunft: "aehnlichkeit" },
      { pfad: C, vorschlag: null, wert: 0.41, herkunft: "aehnlichkeit" },
    ]);
  });
  await page.route("**/api/sources/q-*", (route) => {
    if (route.request().method() !== "DELETE") return route.fallback();
    geloescht.push(route.request().url().split("/").pop()!);
    return route.fulfill({ status: 204 });
  });
  return { A, B, C, log, geloescht };
}

test("Ähnlichkeit: Vorschlag erst nach dem Lesen, Übernehmen verschiebt, Start räumt die Vorschau auf", async ({ page }) => {
  test.setTimeout(60_000);
  const { A, B, C, log, geloescht } = await mockVorschlag(page, { aehnlichkeit: "ok" });
  await page.goto("/ablauf");
  await page.setInputFiles('[data-testid="ablauf-dateien"]', [`../examples/foerderband/${A}`, `../examples/umroller/${B}`, `../examples/foerderband/${C}`]);
  await expect(page.getByText("Ähnlichkeit 0,83")).toBeVisible({ timeout: 15_000 });
  // alles wurde gelesen, bevor die Ähnlichkeit gefragt wurde; je Anlage und für die Losen eine Vorschau-Quelle
  expect(log.filter((l) => l.startsWith("lesen")).sort()).toEqual(["lesen:FB-01", "lesen:lose"]);
  expect(log.filter((l) => l === "aehnlichkeit")).toHaveLength(1);
  expect(log.slice(0, log.indexOf("aehnlichkeit")).filter((l) => l === "lesestand").length).toBeGreaterThanOrEqual(3);
  // ohne Klick ändert sich nichts; die zweite Datei (vorschlag null) hat nur die Auswahl
  await expect(page.getByLabel("Unzugeordnete Dateien").getByRole("listitem")).toHaveCount(2);
  await expect(page.getByRole("button", { name: `${C} nach FB-01 übernehmen` })).toHaveCount(0);
  await expect(page.getByLabel(`${C} verschieben nach`)).toBeVisible();
  expect(geloescht).toEqual([]);
  const axe = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  expect(axe.violations, JSON.stringify(axe.violations, null, 1)).toEqual([]);
  await page.screenshot({ path: `test-results/ablauf-vorschlag-${test.info().project.name}.png`, fullPage: true });

  await page.getByRole("button", { name: `${B} nach FB-01 übernehmen` }).click();
  await expect(page.getByLabel("Unzugeordnete Dateien").getByRole("listitem")).toHaveCount(1);
  await expect(page.getByLabel("Dateien von Anlage 1").getByText(B)).toBeVisible();
  await expect(page.getByRole("button", { name: "Alle starten" })).toBeDisabled();

  await page.getByLabel(`${C} verschieben nach`).selectOption({ label: "FB-01" });
  await page.getByRole("button", { name: `${C} jetzt verschieben` }).click();
  await page.getByRole("button", { name: "Alle starten" }).click();
  await expect(page.getByTestId("lauf-run-1")).toBeVisible();
  expect(geloescht.sort()).toEqual(["q-fb01", "q-lose"]);
});

test("Ähnlichkeit: Verwerfen räumt die Vorschau auf", async ({ page }) => {
  const { A, B, C, geloescht } = await mockVorschlag(page, { aehnlichkeit: "ok" });
  await page.goto("/ablauf");
  await page.setInputFiles('[data-testid="ablauf-dateien"]', [`../examples/foerderband/${A}`, `../examples/umroller/${B}`, `../examples/foerderband/${C}`]);
  await expect(page.getByText("Ähnlichkeit 0,83")).toBeVisible({ timeout: 15_000 });
  await page.getByRole("button", { name: "Verwerfen" }).click();
  await expect.poll(() => [...geloescht].sort()).toEqual(["q-fb01", "q-lose"]);
});

test("Ähnlichkeit: Fehler der Route lässt wie bisher per Auswahl zuordnen", async ({ page }) => {
  const { A, B, C } = await mockVorschlag(page, { aehnlichkeit: "fehler" });
  await page.goto("/ablauf");
  await page.setInputFiles('[data-testid="ablauf-dateien"]', [`../examples/foerderband/${A}`, `../examples/umroller/${B}`, `../examples/foerderband/${C}`]);
  await expect(page.getByText("Kein Vorschlag möglich: Gruppennamen müssen verschieden sein")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByRole("button", { name: "Übernehmen" })).toHaveCount(0);
  await page.getByLabel(`${B} verschieben nach`).selectOption({ label: "FB-01" });
  await page.getByRole("button", { name: `${B} jetzt verschieben` }).click();
  await expect(page.getByLabel("Unzugeordnete Dateien").getByRole("listitem")).toHaveCount(1);
});
