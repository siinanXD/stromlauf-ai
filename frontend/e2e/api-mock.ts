import type { Page, Route } from "@playwright/test";

/** Gemockte Backend-API fuer die Maschinenansicht: FB-01 mit Schaltschrankfoto, Modell und einem SSE-Chat. */

export const MACHINE_ID = "m-fb01";
const SOURCE_ID = "s-fb01";
const HALL_ID = "h-1";
const DOC_ID = "d-plan";
const CABINET_ID = "c-1";

// 1x1-PNG (transparent), reicht als Bild fuer Seiten und Schaltschrankfotos
const PNG = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==", "base64");

const machine = {
  id: MACHINE_ID,
  hall_id: HALL_ID,
  hall_name: "Halle 1",
  name: "Förderband FB-01",
  machine_type: "conveyor",
  description: "",
  source_id: SOURCE_ID,
  source_name: "FB-01 Doku",
  has_image: false,
  order_index: 0,
  fault_count: 1,
  cabinet_count: 1,
  document_count: 3,
  line: "Linie A",
  created_at: "2026-09-01T00:00:00Z",
  faults: [{ id: "f1", machine_id: MACHINE_ID, code: "E03", symptom: "Band steht", tags: ["-K1"], cause: "", fix: "", created_at: "2026-09-01T00:00:00Z" }],
  cabinets: [
    {
      id: CABINET_ID,
      machine_id: MACHINE_ID,
      title: "Schaltschrank +ST1",
      width: 800,
      height: 600,
      created_at: "2026-09-01T00:00:00Z",
      hotspots: [{ id: "hs1", cabinet_id: CABINET_ID, tag: "-K1", label: "Hauptschütz", kind: "contactor", x: 0.2, y: 0.3, w: 0.1, h: 0.12, confidence: 0.9, origin: "manual", confirmed: true }],
    },
  ],
};

const machineList = [
  {
    id: MACHINE_ID,
    name: machine.name,
    machine_type: "conveyor",
    line: "Linie A",
    hall_id: HALL_ID,
    hall_name: "Halle 1",
    source_id: SOURCE_ID,
    source_name: "FB-01 Doku",
    document_count: 3,
    ready_document_count: 3,
    fault_count: 1,
    open_diagnoses: 0,
    cabinet_count: 1,
  },
  { id: "m-2", name: "Presse P-02", machine_type: "main", line: "", hall_id: HALL_ID, hall_name: "Halle 1", source_id: null, source_name: null, document_count: 0, ready_document_count: 0, fault_count: 0, open_diagnoses: 0, cabinet_count: 0 },
];

const map = {
  machine_id: MACHINE_ID,
  source_id: SOURCE_ID,
  part_count: 4,
  connectors: [{ source: "+ST1", target: "+FE1", label: "-W3" }],
  zones: [
    { id: "+ST1", code: "+ST1", name: "Schaltschrank", parts: [{ tag: "-K1", label: "Hauptschütz", kind: "Schuetz/Relais", source: "bom" }, { tag: "-F2", label: "Motorschutz", kind: "Schutz", source: "bom" }] },
    { id: "+FE1", code: "+FE1", name: "Feld", parts: [{ tag: "-M1", label: "Getriebemotor", kind: "Motor", source: "bom" }] },
    { id: "?", code: "?", name: "Ohne Einbauort", parts: [{ tag: "-B7", label: "", kind: "Sensor", source: "index" }] },
  ],
};

function sse(events: [string, unknown][]): string {
  return events.map(([event, data]) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`).join("");
}

const ANSWER_SOURCES = [{ document_id: DOC_ID, filename: "01_Stromlaufplan_FB-01.pdf", doc_type: "schematic", page: 3, section: "" }];
const ANSWER_TEXT =
  "## Kurzantwort\n\nSchütz -K1 zieht nicht an, wenn der Motorschutz -F2 ausgelöst hat [[01_Stromlaufplan_FB-01.pdf|/3.4]].\n\n## Prüfen\n\n1. -F2 zurücksetzen [[02_Stueckliste_FB-01.xlsx|-X9]].\n2. Spule von -K1 an A1/A2 messen [[01_Stromlaufplan_FB-01.pdf|S. 9]].";
const ANSWER_META = {
  referenced_tags: ["-K1", "-F2"],
  citations: ANSWER_SOURCES,
  evidence: [
    { kind: "cabinet", cabinet_id: CABINET_ID, cabinet_title: "Schaltschrank +ST1", hotspot_id: "hs1", tag: "-K1", label: "Hauptschütz", box: { x: 0.2, y: 0.3, w: 0.1, h: 0.12 }, confirmed: true },
    { kind: "page", document_id: DOC_ID, filename: "01_Stromlaufplan_FB-01.pdf", doc_type: "schematic", page: 3, label: "01_Stromlaufplan_FB-01.pdf S. 3" },
  ],
  // Zitat-Resolver (Issue #46): der zweite Beleg zeigt auf ein Kennzeichen, das die Stueckliste nicht kennt
  citation_checks: [
    { text: "[[01_Stromlaufplan_FB-01.pdf|/3.4]]", file: "01_Stromlaufplan_FB-01.pdf", locator: "/3.4", valid: true, checked: true, reason: "" },
    { text: "[[02_Stueckliste_FB-01.xlsx|-X9]]", file: "02_Stueckliste_FB-01.xlsx", locator: "-X9", valid: false, checked: true, reason: "Kennzeichen -X9 nicht in 02_Stueckliste_FB-01.xlsx" },
    { text: "[[01_Stromlaufplan_FB-01.pdf|S. 9]]", file: "01_Stromlaufplan_FB-01.pdf", locator: "S. 9", valid: false, checked: true, reason: "Seite 9 nicht in 01_Stromlaufplan_FB-01.pdf (7 Seiten)" },
  ],
  citations_valid: { valid: 1, checked: 3, total: 3 },
  // Stoerfall-Arbeitsflaeche: Art je Kennzeichen, Start des Signalwegs, Fundstellen im Stromlaufplan
  part_kinds: { "-K1": "Schütz", "-F2": "Motorschutz" },
  signal_start: "-K1",
  plan_spots: [{ tag: "-K1", document_id: DOC_ID, filename: "01_Stromlaufplan_FB-01.pdf", page: 3, sheet: 3, title: "Motor Förderband", column: 4 }],
};

export const CHAT_STREAM = sse([
  ["conversation", { id: "conv-1", title: "-K1 zieht nicht an" }],
  ["tool_start", { name: "find_tag", args: { tag: "-K1" } }],
  ["tool_end", { name: "find_tag" }],
  ["sources", ANSWER_SOURCES],
  ["token", { text: ANSWER_TEXT }],
  ["usage", { input_tokens: 1200, output_tokens: 80, model: "claude-sonnet-5", cost_cents: 0.32 }],
  ["meta", ANSWER_META],
  ["done", {}],
]);

/** Gespeicherter Stoerfall conv-1 (Issue #47): der Verlauf traegt dasselbe meta wie der Stream, aber keine Kosten. */
type MockConversation = { id: string; title: string; source_ids: string[]; updated_at: string; outcome?: string; finding?: string };
const CONVERSATION_1: MockConversation = { id: "conv-1", title: "-K1 zieht nicht an", source_ids: [SOURCE_ID], updated_at: "2026-09-29T10:00:00Z", outcome: "open", finding: "" };
const HISTORY = [
  { role: "user", content: "-K1 zieht nicht an", tool_calls: [], sources: [], index: 0 },
  { role: "assistant", content: ANSWER_TEXT, tool_calls: [{ name: "find_tag", args: { tag: "-K1" } }], sources: ANSWER_SOURCES, meta: ANSWER_META, index: 1 },
];

/** Fehlerliste zur Meldung (GET /api/machines/{id}/fault-hits), ohne Modell. */
const FAULT_HITS = {
  faults: [{ id: "f1", machine_id: MACHINE_ID, code: "E03", symptom: "Band steht", tags: ["-K1"], cause: "Motorschutz -F2 ausgelöst", fix: "-F2 zurücksetzen", doc_ref: "" }],
  experience: [],
  incidents: [],
};

const factCard = {
  tag: "-K1",
  title: "Hauptschütz",
  bom_line: "-K1 | Hauptschütz | 3RT2015 | +ST1",
  rows: [
    { label: "Einbauort", values: [{ text: "+ST1 Schaltschrank", ref: "", document_id: null, filename: null, page: null }] },
    { label: "Stromlaufplan", values: [{ text: "/3.4", ref: "/3.4", document_id: DOC_ID, filename: "01_Stromlaufplan_FB-01.pdf", page: 3 }] },
    { label: "Klemmen", values: [{ text: "-X1:5", ref: "", document_id: null, filename: null, page: null }] },
  ],
};

const tagLookup = {
  tag: "-K1",
  bom_line: "-K1 | Hauptschütz | 3RT2015 | +ST1",
  hits: [
    { document_id: DOC_ID, filename: "01_Stromlaufplan_FB-01.pdf", doc_type: "schematic", page: 3, section: "", context: "-K1 Hauptschütz A1/A2" },
    { document_id: "d-bom", filename: "02_Stueckliste_FB-01.xlsx", doc_type: "bom", page: null, section: "", context: "-K1 | Hauptschütz | 3RT2015 | +ST1" },
  ],
};

const signal = {
  start: "-K1",
  nodes: [
    { id: "-K1", kind: "device", label: "-K1", ref: "", detail: "", level: 0 },
    { id: "-X1:5", kind: "terminal", label: "-X1:5", ref: "", detail: "", level: 1 },
    { id: "-F2", kind: "device", label: "-F2", ref: "", detail: "", level: 2 },
    { id: "-M1", kind: "device", label: "-M1", ref: "", detail: "", level: 1 },
  ],
  edges: [
    { source: "-K1", target: "-X1:5" },
    { source: "-X1:5", target: "-F2" },
    { source: "-K1", target: "-M1" },
  ],
  schematic: { document_id: DOC_ID, filename: "01_Stromlaufplan_FB-01.pdf" },
};

/** Von Tests eingesehene PATCH-Bodies (Box-Roundtrip). */
export const patched: { id: string; body: Record<string, unknown> }[] = [];

function json(route: Route, body: unknown, status = 200) {
  return route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
}

/**
 * withHistory: conv-1 gibt es schon (Verlauf, Reload). Ohne legt erst der Chat-Stream conv-1 an, wie der Server.
 * Der Zustand gilt je Seite, PATCH aendert outcome und finding.
 */
export async function mockApi(page: Page, { withHistory = true, chatFailures = 0 }: { withHistory?: boolean; chatFailures?: number } = {}) {
  const conversations: MockConversation[] = withHistory ? [{ ...CONVERSATION_1 }] : [];
  // chatFailures: so oft antwortet POST /api/chat mit 400 wie ohne Modell-Schluessel, bevor er gelingt
  let failuresLeft = chatFailures;
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    const method = route.request().method();
    if (method === "OPTIONS") return route.fulfill({ status: 204, headers: { "access-control-allow-origin": "*", "access-control-allow-headers": "*", "access-control-allow-methods": "*" } });

    if (path === "/api/health") return json(route, { status: "ok", chat_model: "claude-sonnet-5", api_key_configured: true });
    if (path === "/api/auth/mode") return json(route, { mode: "legacy", dev_link: false });
    if (path === "/api/auth/me") return json(route, { user_id: null, email: null, via: "open", workspace: { id: "default", name: "Standard", role: "admin" } });
    if (path === "/api/workspace/budget") return json(route, { month_cents: 187.5, month_calls: 42, cap_cents: null, exceeded: false });
    if (path === "/api/machines") return json(route, machineList);
    if (path === `/api/machines/${MACHINE_ID}`) return json(route, machine);
    if (path === `/api/machines/${MACHINE_ID}/tags/-K1`) return json(route, tagLookup);
    if (path.startsWith(`/api/machines/${MACHINE_ID}/tags/`)) return json(route, { tag: decodeURIComponent(path.split("/").pop()!), hits: [], bom_line: null });
    if (path === "/api/facts") return url.searchParams.get("tag") === "-K1" ? json(route, factCard) : json(route, { detail: "nichts" }, 404);
    if (path === "/api/signal-path") return url.searchParams.get("tag") === "-K1" ? json(route, signal) : json(route, { detail: "nichts" }, 404);
    if (path.startsWith("/api/hotspots/") && method === "PATCH") {
      const id = path.split("/").pop()!;
      const body = route.request().postDataJSON() as Record<string, unknown>;
      patched.push({ id, body });
      for (const cabinet of machine.cabinets) {
        const hotspot = cabinet.hotspots.find((h) => h.id === id);
        if (hotspot) {
          Object.assign(hotspot, body, { origin: "manual", confirmed: true });
          return json(route, hotspot);
        }
      }
      return json(route, { detail: "nicht gefunden" }, 404);
    }
    if (path === `/api/machines/${MACHINE_ID}/map`) return json(route, map);
    if (path === `/api/machines/${MACHINE_ID}/costs`)
      return json(route, { machine_id: MACHINE_ID, month: { cents: 117, calls: 12, by_purpose: { chat: { cents: 17, calls: 11 }, "vision.cabinet": { cents: 100, calls: 1 } } }, total: { cents: 117, calls: 12, by_purpose: {} }, workspace: { month_cents: 187.5, month_calls: 42, cap_cents: null, exceeded: false } });
    if (path === `/api/machines/${MACHINE_ID}/diagnoses`) return json(route, []);
    if (path === "/api/sources") return json(route, [{ id: SOURCE_ID, name: "FB-01 Doku", description: "", document_count: 3, created_at: "2026-09-01T00:00:00Z" }]);
    if (path === `/api/sources/${SOURCE_ID}/documents`)
      return json(route, [{ id: DOC_ID, source_id: SOURCE_ID, filename: "01_Stromlaufplan_FB-01.pdf", doc_type: "schematic", status: "ready", progress: "", error: null, page_count: 12, vision_enrichment: false, created_at: "2026-09-01T00:00:00Z" }]);
    if (path === "/api/conversations") return json(route, url.searchParams.get("source_id") === SOURCE_ID || !url.searchParams.get("source_id") ? conversations : []);
    if (path === "/api/conversations/conv-1/messages") return json(route, HISTORY);
    if (path === "/api/conversations/conv-1" && method === "PATCH") {
      const target = conversations.find((c) => c.id === "conv-1");
      if (!target) return json(route, { detail: "nicht gefunden" }, 404);
      Object.assign(target, route.request().postDataJSON() as Partial<MockConversation>, { updated_at: "2026-10-01T09:00:00Z" });
      return json(route, target);
    }
    if (path === `/api/machines/${MACHINE_ID}/fault-hits`) return json(route, FAULT_HITS);
    if (path === "/api/chat" && method === "POST") {
      if (failuresLeft > 0) {
        failuresLeft -= 1;
        return json(route, { detail: "ANTHROPIC_API_KEY fehlt fuer Modell 'claude-sonnet-5'. In .env eintragen und Backend neu starten." }, 400);
      }
      if (!conversations.some((c) => c.id === "conv-1")) conversations.unshift({ ...CONVERSATION_1, updated_at: "2026-10-01T08:00:00Z" });
      return route.fulfill({ status: 200, contentType: "text/event-stream", body: CHAT_STREAM });
    }
    if (path.endsWith("/image") || /\/pages\/\d+\/image$/.test(path)) return route.fulfill({ status: 200, contentType: "image/png", body: PNG });
    if (path === "/api/tags/search") return json(route, []);
    return json(route, { detail: `nicht gemockt: ${method} ${path}` }, 404);
  });
}
