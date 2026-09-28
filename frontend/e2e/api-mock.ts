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
  pos_x: 0,
  pos_y: 0,
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
    has_layout: false,
  },
  { id: "m-2", name: "Presse P-02", machine_type: "main", line: "", hall_id: HALL_ID, hall_name: "Halle 1", source_id: null, source_name: null, document_count: 0, ready_document_count: 0, fault_count: 0, open_diagnoses: 0, cabinet_count: 0, has_layout: false },
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

export const CHAT_STREAM = sse([
  ["conversation", { id: "conv-1", title: "-K1 zieht nicht an" }],
  ["tool_start", { name: "find_tag", args: { tag: "-K1" } }],
  ["tool_end", { name: "find_tag" }],
  ["sources", [{ document_id: DOC_ID, filename: "01_Stromlaufplan_FB-01.pdf", doc_type: "schematic", page: 3, section: "" }]],
  ["token", { text: "## Kurzantwort\n\nSchütz -K1 zieht nicht an, wenn der Motorschutz -F2 ausgelöst hat [[01_Stromlaufplan_FB-01.pdf|/3.4]].\n\n## Prüfen\n\n1. -F2 zurücksetzen.\n2. Spule von -K1 an A1/A2 messen." }],
  ["usage", { input_tokens: 1200, output_tokens: 80, model: "claude-sonnet-5", cost_cents: 0.32 }],
  [
    "meta",
    {
      referenced_tags: ["-K1", "-F2"],
      citations: [{ document_id: DOC_ID, filename: "01_Stromlaufplan_FB-01.pdf", doc_type: "schematic", page: 3, section: "" }],
      evidence: [
        { kind: "cabinet", cabinet_id: CABINET_ID, cabinet_title: "Schaltschrank +ST1", hotspot_id: "hs1", tag: "-K1", label: "Hauptschütz", box: { x: 0.2, y: 0.3, w: 0.1, h: 0.12 }, confirmed: true },
        { kind: "page", document_id: DOC_ID, filename: "01_Stromlaufplan_FB-01.pdf", doc_type: "schematic", page: 3, label: "01_Stromlaufplan_FB-01.pdf S. 3" },
      ],
    },
  ],
  ["done", {}],
]);

function json(route: Route, body: unknown, status = 200) {
  return route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
}

export async function mockApi(page: Page) {
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
    if (path === `/api/machines/${MACHINE_ID}/map`) return json(route, map);
    if (path === `/api/machines/${MACHINE_ID}/layout`) return json(route, { detail: "Keine Draufsicht" }, 404);
    if (path === `/api/machines/${MACHINE_ID}/costs`)
      return json(route, { machine_id: MACHINE_ID, month: { cents: 117, calls: 12, by_purpose: { chat: { cents: 17, calls: 11 }, flow: { cents: 100, calls: 1 } } }, total: { cents: 117, calls: 12, by_purpose: {} }, workspace: { month_cents: 187.5, month_calls: 42, cap_cents: null, exceeded: false } });
    if (path === `/api/machines/${MACHINE_ID}/diagnoses`) return json(route, []);
    if (path === "/api/sources") return json(route, [{ id: SOURCE_ID, name: "FB-01 Doku", description: "", document_count: 3, created_at: "2026-09-01T00:00:00Z" }]);
    if (path === `/api/sources/${SOURCE_ID}/documents`)
      return json(route, [{ id: DOC_ID, source_id: SOURCE_ID, filename: "01_Stromlaufplan_FB-01.pdf", doc_type: "schematic", status: "ready", progress: "", error: null, page_count: 12, vision_enrichment: false, created_at: "2026-09-01T00:00:00Z" }]);
    if (path === "/api/conversations") return json(route, []);
    if (path === "/api/chat" && method === "POST") return route.fulfill({ status: 200, contentType: "text/event-stream", body: CHAT_STREAM });
    if (path.endsWith("/image") || /\/pages\/\d+\/image$/.test(path)) return route.fulfill({ status: 200, contentType: "image/png", body: PNG });
    if (path === "/api/tags/search") return json(route, []);
    return json(route, { detail: `nicht gemockt: ${method} ${path}` }, 404);
  });
}
