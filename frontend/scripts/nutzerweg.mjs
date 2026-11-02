// Nutzerwege (SIN-1458): `npm run test:nutzerweg`. Prueft, ob die Demo erreichbar und FB-01 gelesen ist, laeuft dann
// e2e/nutzerweg.spec.ts und schreibt je Weg gruen/rot samt Laufzeit nach NUTZERWEG_DIR/ergebnis.md.
//
//   LIVE_URL=http://localhost:3100 npm run test:nutzerweg      (LIVE_API_URL, Standard http://localhost:8010)
//
// Exit 0 = alle Wege gruen, 1 = mindestens ein Weg rot, 2 = nicht pruefbar (Demo nicht erreichbar oder nicht bereit).
import { spawnSync } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";

const live = process.env.LIVE_URL?.replace(/\/$/, "");
const api = (process.env.LIVE_API_URL ?? "http://localhost:8010").replace(/\/$/, "");
const out = resolve(process.cwd(), process.env.NUTZERWEG_DIR ?? "../tmp/nutzerweg");
const MACHINE = "Foerderband FB-01";
const READY_TIMEOUT_MS = 8 * 60_000;

function nichtPruefbar(grund) {
  console.log(`NUTZERWEG: nicht prüfbar. ${grund}`);
  process.exit(2);
}

async function getJson(url) {
  const response = await fetch(url, { signal: AbortSignal.timeout(10_000) });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

async function bereit() {
  const machines = await getJson(`${api}/api/machines`);
  const machine = machines.find((m) => m.name === MACHINE);
  if (!machine?.source_id) return `Maschine ${MACHINE} fehlt im Backend`;
  const docs = await getJson(`${api}/api/sources/${machine.source_id}/documents`);
  // Die Demo legt FB-01 im Hintergrund an: /api/health ist gruen, bevor die Dokumente gelesen sind
  return docs.length > 0 && docs.every((d) => d.status === "ready") ? null : "Dokumente von FB-01 sind noch nicht gelesen";
}

if (!live) nichtPruefbar("LIVE_URL fehlt (lokale Demo: LIVE_URL=http://localhost:3100, Start: docker compose --profile demo up --build).");

try {
  const response = await fetch(live, { redirect: "manual", signal: AbortSignal.timeout(10_000) });
  if (response.status >= 500) throw new Error(`HTTP ${response.status}`);
} catch (e) {
  nichtPruefbar(`Frontend ${live} nicht erreichbar (${e.message}).`);
}
try {
  await getJson(`${api}/api/health`);
} catch (e) {
  nichtPruefbar(`Backend ${api} nicht erreichbar (${e.message}). Ohne Backend gibt es keine Daten; Hosting steht aus (SIN-1251).`);
}
const start = Date.now();
let grund = await bereit().catch((e) => `Backend antwortet nicht (${e.message})`);
while (grund && Date.now() - start < READY_TIMEOUT_MS) {
  await new Promise((r) => setTimeout(r, 5_000));
  grund = await bereit().catch((e) => `Backend antwortet nicht (${e.message})`);
}
if (grund) nichtPruefbar(grund);

mkdirSync(out, { recursive: true });
const jsonPath = resolve(out, "playwright.json");
const run = spawnSync(
  "npx",
  ["playwright", "test", "e2e/nutzerweg.spec.ts", "--project=desktop-1440", "--workers=1", "--reporter=list,json"],
  {
    stdio: "inherit",
    shell: true,
    env: { ...process.env, E2E_BASE_URL: live, E2E_API_URL: api, NUTZERWEG_DIR: out, PLAYWRIGHT_JSON_OUTPUT_NAME: jsonPath },
  },
);

const wege = [];
const walk = (suite) => {
  for (const spec of suite.specs ?? []) {
    const result = spec.tests?.[0]?.results?.at(-1);
    wege.push({ titel: spec.title, ok: spec.ok, ms: result?.duration ?? 0, fehler: result?.error?.message?.split("\n")[0] ?? "" });
  }
  for (const child of suite.suites ?? []) walk(child);
};
try {
  for (const suite of JSON.parse(readFileSync(jsonPath, "utf8")).suites ?? []) walk(suite);
} catch {
  nichtPruefbar("Playwright hat kein Ergebnis geschrieben (Start fehlgeschlagen).");
}

const sekunden = (ms) => `${(ms / 1000).toFixed(1)} s`;
const zeilen = wege.map((w) => `| ${w.titel.split(":")[0]} | ${w.ok ? "grün" : "ROT"} | ${sekunden(w.ms)} | ${w.fehler.replace(/\|/g, "/")} |`);
const gesamt = Date.now() - start;
const bericht = ["| Weg | Ergebnis | Dauer | Fehler |", "| --- | --- | --- | --- |", ...zeilen, "", `Laufzeit gesamt: ${sekunden(gesamt)}. Screenshots: ${out}`].join("\n");
writeFileSync(resolve(out, "ergebnis.md"), `${bericht}\n`);
console.log(`\n${bericht}`);
process.exit(wege.length > 0 && wege.every((w) => w.ok) && run.status === 0 ? 0 : 1);
