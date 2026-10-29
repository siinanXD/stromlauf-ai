import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { expect, test, type Page } from "@playwright/test";

/**
 * Demo-Abnahme (docs/FERTIG.md Punkt 4, SIN-1161): 10 Fragen zu FB-01 im Browser gegen die laufende Compose-Demo,
 * ohne api-mock.ts. Die Fragen sind feste IDs aus eval/questions.jsonl.
 *
 * Jede Frage hat zwei Pruefungen:
 *  - deterministisch (immer, 0 USD): die Ansicht, die diese Frage ohne Modell beantwortet (Bauteil-Befundkarte,
 *    SPS "Warum kommt ... nicht?", Signalweg), zeigt den erwarteten Wert und die Quelle.
 *  - Chat (nur mit E2E_CHAT=1 UND Modell-Schluessel im Backend, bezahlt): dieselbe Frage im Stoerfall-Chat; Antwort
 *    nicht leer, kein Fehlertext, mindestens eine Quellenangabe, erwartete Quelle aus eval/questions.jsonl dabei.
 *    Fehlt der Schluessel, meldet der Test die Frage als uebersprungen (Annotation), statt rot zu werden.
 *
 *   E2E_API_URL=http://localhost:8010 E2E_BASE_URL=http://localhost:3100 npx playwright test e2e/demo.spec.ts --project=desktop-1440
 * CI: Job compose-demo mit --repeat-each=3 --workers=1 (sonst greift das Chat-Limit der Demo).
 */

const API = process.env.E2E_API_URL?.replace(/\/$/, "");
const MACHINE = process.env.E2E_MACHINE ?? "Foerderband FB-01";
const CHAT = process.env.E2E_CHAT === "1";
/** DEMO_CHAT_RATE_LIMIT ist 10 je Minute und IP: Chat-Fragen im Abstand von mindestens 7 s starten. */
const CHAT_GAP_MS = 7_000;

type Eval = { id: string; question: string; expect_sources: string[] };

type Frage =
  | { id: string; art: "bauteil"; tag: string; zeigt: RegExp[]; quelle: string }
  | { id: string; art: "warum"; ausgang: string; zeigt: RegExp[]; quelle: RegExp }
  | { id: string; art: "signal"; tag: string; zeigt: RegExp[]; quelle: RegExp };

const FRAGEN: Frage[] = [
  { id: "fb01-f2-typ", art: "bauteil", tag: "-F2", zeigt: [/2,5-4 A/, /\/3\.2/], quelle: "02_Stueckliste_FB-01.xlsx" },
  { id: "fb01-m1-fact", art: "bauteil", tag: "-M1", zeigt: [/1,5 kW/, /-X4:U/, /\/3\.5/], quelle: "03_Klemmenplan_FB-01.csv" },
  { id: "fb01-t1-netzteil", art: "bauteil", tag: "-T1", zeigt: [/24 V DC/, /-X2/], quelle: "02_Stueckliste_FB-01.xlsx" },
  { id: "fb01-b2-eingang", art: "bauteil", tag: "-B2", zeigt: [/E0\.5/, /-X3:6/], quelle: "05_Symboltabelle_FB-01.sdf" },
  { id: "fb01-h2-ausgang", art: "bauteil", tag: "-H2", zeigt: [/A4\.3/, /-X3:12/], quelle: "03_Klemmenplan_FB-01.csv" },
  { id: "fb01-h3-gelb", art: "bauteil", tag: "-H3", zeigt: [/Not-Halt/, /\/4\.8/], quelle: "02_Stueckliste_FB-01.xlsx" },
  { id: "fb01-q2-reparaturschalter", art: "bauteil", tag: "-Q2", zeigt: [/Reparaturschalter/, /\+AN1/, /\/3\.5/], quelle: "02_Stueckliste_FB-01.xlsx" },
  { id: "fb01-warum-a40", art: "warum", ausgang: "A4.0", zeigt: [/FB 10 NW 2/, /FB 10 NW 1/, /-X3:9/], quelle: /FB 10 NW \d/ },
  { id: "fb01-warum-a41", art: "warum", ausgang: "A4.1", zeigt: [/FB 10 NW 3/, /M20\.0/], quelle: /FB 10 NW \d/ },
  // Seit #194 (Issue #121, SIN-1189) fuehrt der Hauptweg vom Taster ueber A4.0 und -K1 zum Motor -M1, nicht zur Leuchte -H2.
  { id: "fb01-signal-s1", art: "signal", tag: "-S1", zeigt: [/-X3:1/, /E0\.0/, /FB 10 NW 1/, /A4\.0/, /-K1/, /-M1/], quelle: /Blatt 4/ },
];

const evals = new Map<string, Eval>(
  readFileSync(resolve(process.cwd(), "../eval/questions.jsonl"), "utf8")
    .split("\n")
    .filter(Boolean)
    .map((line) => JSON.parse(line) as Eval)
    .map((q) => [q.id, q]),
);

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API}${path}`);
  if (!response.ok) throw new Error(`GET ${path}: HTTP ${response.status} ${await response.text()}`);
  return (await response.json()) as T;
}

async function expectZeigt(scope: ReturnType<Page["locator"]>, zeigt: RegExp[]) {
  for (const re of zeigt) await expect(scope.getByText(re).first(), `sichtbar: ${re}`).toBeVisible();
}

test.describe("Demo: 10 Fragen zu FB-01", () => {
  test.skip(!API, "E2E_API_URL nicht gesetzt: Demo-Abnahme uebersprungen");
  let machineId = "";
  let sourceId = "";
  let hasKey = false;
  let lastChatAt = 0;

  test.beforeAll(async () => {
    test.setTimeout(10 * 60_000);
    const machines = await getJson<{ id: string; name: string; source_id: string | null }[]>("/api/machines");
    const machine = machines.find((m) => m.name === MACHINE);
    expect(machine, `Maschine ${MACHINE} im Backend`).toBeTruthy();
    machineId = machine!.id;
    sourceId = machine!.source_id ?? "";
    expect(sourceId, "Wissensquelle der Maschine").not.toBe("");
    // Die Demo legt FB-01 im Hintergrund an: /api/health ist gruen, bevor die Dokumente gelesen sind
    await expect
      .poll(
        async () => {
          const docs = await getJson<{ status: string }[]>(`/api/sources/${sourceId}/documents`);
          return docs.length > 0 && docs.every((d) => d.status === "ready");
        },
        { message: "alle Dokumente von FB-01 gelesen", timeout: 8 * 60_000, intervals: [5_000] },
      )
      .toBe(true);
    hasKey = (await getJson<{ api_key_configured: boolean }>("/api/health")).api_key_configured;
  });

  test("alle 10 Fragen stammen aus eval/questions.jsonl", () => {
    expect(FRAGEN).toHaveLength(10);
    for (const f of FRAGEN) expect(evals.get(f.id), `Eval-Frage ${f.id}`).toBeTruthy();
  });

  for (const frage of FRAGEN) {
    test(`${frage.id}: Ansicht zeigt Wert und Quelle`, async ({ page }) => {
      if (frage.art === "warum") {
        await page.goto(`/werk/maschine/${machineId}?bereich=aufbau&tab=sps`);
        await page.getByLabel("Ausgang für „Warum kommt … nicht?“").fill(frage.ausgang);
        await page.getByRole("button", { name: "Warum?" }).click();
        const result = page.getByTestId("why-result");
        await expect(result.getByTestId("why-tree")).toBeVisible();
        await expectZeigt(result, frage.zeigt);
      } else if (frage.art === "bauteil") {
        // Wie ein Mensch: Maschine oeffnen, Aufbau, Bauteil im Modell antippen
        await page.goto(`/werk/maschine/${machineId}?bereich=aufbau`);
        await page.locator(`button.part-chip[data-tag="${frage.tag}"]`).click();
        const sheet = page.getByTestId("part-sheet");
        await expect(sheet).toBeVisible();
        await expectZeigt(sheet, frage.zeigt);
      } else {
        await page.goto(`/werk/maschine/${machineId}?bereich=aufbau&tab=signalweg&tag=${encodeURIComponent(frage.tag)}`);
        const panel = page.getByTestId("model-panel");
        await expectZeigt(panel, frage.zeigt);
      }
      // Quelle: Dateiname als Tooltip eines sichtbaren Belegs, beim SPS-Programm der Netzwerkverweis (AWL hat keine Seite)
      const quelle =
        typeof frage.quelle === "string"
          ? page.locator(`[title="${frage.quelle}"], [title^="${frage.quelle} "]`).or(page.getByText(frage.quelle)).first()
          : page.getByText(frage.quelle).first();
      await expect(quelle, `Quelle ${frage.quelle}`).toBeVisible();
    });
  }

  for (const frage of FRAGEN) {
    test(`${frage.id}: Chat-Antwort mit Quelle`, async ({ page }, testInfo) => {
      test.skip(!CHAT, "E2E_CHAT nicht gesetzt: bezahlte Chat-Frage uebersprungen");
      if (!hasKey) {
        testInfo.annotations.push({ type: "uebersprungen", description: `${frage.id}: Backend ohne Modell-Schluessel` });
        test.skip(true, "Backend ohne Modell-Schluessel (api_key_configured=false)");
      }
      test.setTimeout(240_000);
      const eval_ = evals.get(frage.id)!;
      const wait = lastChatAt + CHAT_GAP_MS - Date.now();
      if (wait > 0) await page.waitForTimeout(wait);
      lastChatAt = Date.now();

      await page.goto(`/werk/maschine/${machineId}`);
      const input = page.getByTestId("incident-input");
      await input.fill(eval_.question);
      await input.press("Enter");

      const answer = page.locator('[data-answer="blocks"]').last();
      await expect(page.getByTestId("answer-error")).toHaveCount(0);
      // Beleg-Stempel erscheint erst nach dem Stream; danach ist die Antwort vollstaendig
      await expect(answer.getByTestId("citations-valid")).toBeVisible({ timeout: 200_000 });
      await expect(page.getByTestId("answer-error")).toHaveCount(0);
      expect((await answer.innerText()).trim().length, "Antwort nicht leer").toBeGreaterThan(40);

      const stems = eval_.expect_sources.map((s) => s.replace(/\.[^.]+$/, ""));
      const gefunden = await answer.locator("[title]").evaluateAll(
        (nodes, wanted) => nodes.some((n) => wanted.some((w) => (n.getAttribute("title") ?? "").includes(w))),
        stems,
      );
      expect(gefunden, `erwartete Quelle ${eval_.expect_sources.join(" oder ")} in den Belegen`).toBe(true);
    });
  }
});
