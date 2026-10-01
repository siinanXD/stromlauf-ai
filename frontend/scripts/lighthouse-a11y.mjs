#!/usr/bin/env node
/**
 * Lighthouse-Accessibility-Gate fuer die Maschinenansicht (docs/product/contract.md Abschnitt 5: Score >= 90).
 *
 * Aufruf:
 *   node frontend/scripts/lighthouse-a11y.mjs --base http://localhost:3100 --api http://localhost:8010 [--machine "Foerderband FB-01"]
 *   node frontend/scripts/lighthouse-a11y.mjs --url "http://localhost:3100/werk/maschine/<id>?tab=chat"
 *   Optionen: --min 0.9  --out eval/results  --desktop (sonst Mobil-Emulation wie bei Lighthouse ueblich)
 *             --performance: misst zusaetzlich die Kategorie Performance (mobil, Ziel >= 90 laut Spec der
 *             Stoerfall-Arbeitsflaeche) und berichtet Wert und Kennzahlen; der Exit-Code haengt weiter nur an
 *             Accessibility, bis drei stabile Laeufe ein Gate rechtfertigen.
 *
 * Startet Lighthouse als CLI ueber npx in fester Version (kein Eintrag in package.json), nur die Kategorie
 * Accessibility, schreibt <out>/lighthouse-a11y.report.{json,html} und beendet mit Exit 1 unter --min.
 * Ohne --url wird die Demo-Maschine ueber GET /api/machines gesucht; Zugriff ueber STROMLAUF_TOKEN (Bearer)
 * oder STROMLAUF_API_KEY (X-API-Key). Chrome: Standardsuche von Lighthouse, sonst CHROME_PATH setzen.
 * Fuer eine angemeldete Staging-Ansicht (JWT im localStorage) braucht Lighthouse ein vorbereitetes Profil;
 * TODO: Staging-Lauf mit Login klaeren, sobald Railway steht (bis dahin offenes Backend oder API-Key).
 */
import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const LIGHTHOUSE = "lighthouse@13.5.0";

function parseArgs(argv) {
  const options = { base: "http://localhost:3100", api: "http://localhost:8010", machine: "Foerderband FB-01", min: 0.9, out: "eval/results", desktop: false, url: "", performance: false };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    const next = () => argv[(i += 1)];
    if (arg === "--base") options.base = next();
    else if (arg === "--api") options.api = next();
    else if (arg === "--machine") options.machine = next();
    else if (arg === "--url") options.url = next();
    else if (arg === "--min") options.min = Number(next());
    else if (arg === "--out") options.out = next();
    else if (arg === "--desktop") options.desktop = true;
    else if (arg === "--performance") options.performance = true;
    else if (arg === "--help" || arg === "-h") {
      console.log(readFileSync(new URL(import.meta.url), "utf8").split("*/")[0]);
      process.exit(0);
    } else throw new Error(`Unbekannte Option: ${arg}`);
  }
  return options;
}

function authHeaders() {
  const token = (process.env.STROMLAUF_TOKEN ?? "").trim();
  if (token) return { Authorization: `Bearer ${token}` };
  const key = (process.env.STROMLAUF_API_KEY ?? "").trim();
  return key ? { "X-API-Key": key } : {};
}

/** Erst exakter Name, dann Namensteil ohne Gross/Klein (wie scripts/acceptance.py). */
export function findMachine(machines, name) {
  const exact = machines.find((m) => m.name === name);
  if (exact) return exact;
  const needle = name.toLowerCase();
  return machines.find((m) => (m.name ?? "").toLowerCase().includes(needle)) ?? null;
}

async function resolveUrl(options) {
  if (options.url) return options.url;
  const response = await fetch(`${options.api.replace(/\/$/, "")}/api/machines`, { headers: authHeaders() });
  if (!response.ok) throw new Error(`GET /api/machines: HTTP ${response.status}`);
  const machine = findMachine(await response.json(), options.machine);
  if (!machine) throw new Error(`Maschine "${options.machine}" nicht gefunden unter ${options.api}`);
  return `${options.base.replace(/\/$/, "")}/werk/maschine/${machine.id}?tab=chat`;
}

/** npx ohne Shell: node + npx-cli.js (Windows: neben node.exe, sonst ../lib/node_modules); Rueckfall npx via Shell. */
function npxCommand() {
  const nodeDir = dirname(process.execPath);
  for (const candidate of [
    join(nodeDir, "node_modules", "npm", "bin", "npx-cli.js"),
    join(nodeDir, "..", "lib", "node_modules", "npm", "bin", "npx-cli.js"),
  ]) {
    if (existsSync(candidate)) return { command: process.execPath, prefix: [candidate], shell: false };
  }
  return { command: "npx", prefix: [], shell: true };
}

/** Gewichtete Audits der Kategorie, die nicht voll bestanden haben (score < 1). */
export function failingAudits(report) {
  const refs = report.categories.accessibility.auditRefs.filter((ref) => ref.weight > 0);
  return refs
    .map((ref) => report.audits[ref.id])
    .filter((audit) => audit && typeof audit.score === "number" && audit.score < 1)
    .map((audit) => ({ id: audit.id, title: audit.title, items: audit.details?.items?.length ?? 0 }));
}

/** Kennzahlen der Kategorie Performance, wie Lighthouse sie anzeigt (displayValue), fuer den Bericht. */
const PERFORMANCE_METRICS = [
  ["first-contentful-paint", "First Contentful Paint"],
  ["largest-contentful-paint", "Largest Contentful Paint"],
  ["total-blocking-time", "Total Blocking Time"],
  ["cumulative-layout-shift", "Cumulative Layout Shift"],
  ["speed-index", "Speed Index"],
];

/** Performance-Wert (0..1) und Kennzahlen; null, wenn der Bericht die Kategorie nicht enthaelt. */
export function performanceSummary(report) {
  const category = report.categories?.performance;
  if (!category || typeof category.score !== "number") return null;
  const metrics = PERFORMANCE_METRICS.map(([id, label]) => ({ id, label, value: report.audits?.[id]?.displayValue ?? "–" }));
  return { score: category.score, metrics };
}

export function lighthouseCategories(performance) {
  return performance ? "accessibility,performance" : "accessibility";
}

export function runLighthouse(url, outDir, desktop, performance = false) {
  mkdirSync(outDir, { recursive: true });
  const outputPath = join(outDir, "lighthouse-a11y");
  const args = [
    url,
    `--only-categories=${lighthouseCategories(performance)}`,
    "--output=json",
    "--output=html",
    `--output-path=${outputPath}`,
    "--chrome-flags=--headless=new --no-sandbox --disable-gpu",
    "--quiet",
  ];
  if (desktop) args.push("--preset=desktop");
  const npx = npxCommand();
  const result = spawnSync(npx.command, [...npx.prefix, "--yes", LIGHTHOUSE, ...args], { stdio: "inherit", shell: npx.shell });
  if (result.status !== 0) throw new Error(`Lighthouse beendet mit Exit ${result.status ?? result.signal}`);
  return JSON.parse(readFileSync(`${outputPath}.report.json`, "utf8"));
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  const url = await resolveUrl(options);
  const outDir = resolve(options.out);
  console.log(`Lighthouse (${options.performance ? "Accessibility und Performance" : "Accessibility"}) gegen ${url}`);
  const report = runLighthouse(url, outDir, options.desktop, options.performance);
  const score = report.categories.accessibility.score;
  const failing = failingAudits(report);
  console.log(`Accessibility: ${Math.round(score * 100)} (Schwelle ${Math.round(options.min * 100)}); Bericht: ${join(outDir, "lighthouse-a11y.report.html")}`);
  for (const audit of failing) console.log(`  nicht bestanden: ${audit.id} (${audit.items} Stellen) - ${audit.title}`);
  if (options.performance) {
    const perf = performanceSummary(report);
    const form = options.desktop ? "Desktop" : "mobil";
    if (perf) {
      console.log(`Performance (${form}): ${Math.round(perf.score * 100)} (Ziel 90, nur berichtet)`);
      for (const metric of perf.metrics) console.log(`  ${metric.label}: ${metric.value}`);
    } else console.log(`Performance (${form}): kein Wert im Bericht`);
  }
  if (score < options.min) {
    console.error(`Lighthouse Accessibility ${Math.round(score * 100)} liegt unter ${Math.round(options.min * 100)}`);
    process.exit(1);
  }
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch((error) => {
    console.error(error.message);
    process.exit(1);
  });
}
