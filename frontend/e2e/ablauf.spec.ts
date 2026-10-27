import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type Route } from "@playwright/test";

import { mockApi } from "./api-mock";

/** Gemockter Ablauf: POST /api/runs liefert Schritt 1 fertig, jedes GET einen Schritt mehr, das 7. GET den Abschluss. */

const KEYS = ["hochladen", "lesen", "maschine", "steckbrief", "modell", "zusammenfassung", "fertig"] as const;
const LABELS = ["Hochladen", "Lesen", "Maschine", "Steckbrief", "Modell", "Zusammenfassung", "Fertig"];
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

function run(fertig: number, done: boolean) {
  return {
    id: RUN_ID,
    name: "Förderband FB-01",
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
      return json(route, gets >= 7 ? run(KEYS.length, true) : run(Math.min(gets + 1, KEYS.length - 1), false));
    }
    return route.fallback();
  });
}

test("Förderband-Lauf wird in sieben Schritten grün", async ({ page }) => {
  test.setTimeout(60_000);
  await mockAblauf(page);
  await page.goto("/ablauf");
  await page.setInputFiles('input[type="file"]', ["../examples/foerderband/01_Stromlaufplan_FB-01.pdf", "../examples/foerderband/04_SPS_Programm_FB-01.awl"]);
  await page.getByRole("button", { name: "Lauf starten" }).click();
  for (const key of KEYS) {
    await expect(page.getByTestId(`schritt-${key}`)).toHaveAttribute("data-status", "fertig", { timeout: 25_000 });
  }
  await page.getByTestId("schritt-zusammenfassung").click();
  await expect(page.getByRole("link", { name: "In Langfuse öffnen" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Maschine öffnen" })).toBeVisible();
  const lesen = page.getByTestId("zeiten-lesen");
  await expect(page.getByRole("heading", { name: "Zeiten" })).toBeVisible();
  await expect(lesen.getByRole("rowheader", { name: "Lesen" })).toBeVisible();
  await expect(lesen.locator("[aria-label*='über Ziel']")).toBeVisible();
  await expect(lesen.getByRole("link", { name: "Langfuse" })).toHaveAttribute("href", TRACE);
  const axe = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  expect(axe.violations, JSON.stringify(axe.violations, null, 1)).toEqual([]);
});
