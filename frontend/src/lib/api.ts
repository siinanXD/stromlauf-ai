export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8010";
/** Gemeinsamer Schlüssel (Backend-Setting API_KEY). Leer = Backend läuft offen. */
export const API_KEY = process.env.NEXT_PUBLIC_API_KEY ?? "";

/** Header für fetch(): X-API-Key, wenn ein Schlüssel gesetzt ist. */
export function authHeaders(extra?: HeadersInit): HeadersInit {
  const headers = new Headers(extra);
  if (API_KEY) headers.set("X-API-Key", API_KEY);
  return headers;
}

/** Bild-URLs für <img src>: der Browser schickt keine Header, deshalb ?api_key=. */
export function withApiKey(url: string): string {
  if (!API_KEY) return url;
  return `${url}${url.includes("?") ? "&" : "?"}api_key=${encodeURIComponent(API_KEY)}`;
}

export type DocType =
  | "auto"
  | "schematic"
  | "bom"
  | "terminal_plan"
  | "plc_program"
  | "plc_symbols"
  | "manual"
  | "other";

export const DOC_TYPE_LABELS: Record<DocType, string> = {
  auto: "Automatisch erkennen",
  schematic: "Stromlaufplan",
  bom: "Stückliste",
  terminal_plan: "Klemmenplan",
  plc_program: "SPS-Programm (AWL)",
  plc_symbols: "Symboltabelle",
  manual: "Handbuch",
  other: "Sonstiges",
};

export interface KnowledgeSource {
  id: string;
  name: string;
  description: string;
  document_count: number;
}

export interface SourceDocument {
  id: string;
  source_id: string;
  filename: string;
  doc_type: DocType;
  status: "pending" | "processing" | "ready" | "failed";
  progress: string;
  error: string | null;
  page_count: number | null;
  vision_enrichment: boolean;
}

export interface Conversation {
  id: string;
  title: string;
  source_ids: string[];
  updated_at: string;
}

export interface SourceRef {
  document_id: string;
  filename: string;
  doc_type: string;
  page: number | null;
  section: string;
}

export interface ToolCall {
  name: string;
  args: Record<string, unknown>;
  done?: boolean;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  tool_calls: ToolCall[];
  sources: SourceRef[];
  error?: string;
}

export interface Health {
  status: string;
  chat_model: string;
  api_key_configured: boolean;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, { ...init, headers: authHeaders(init?.headers) });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? `${response.status} ${response.statusText}`);
  }
  return response.status === 204 ? (undefined as T) : response.json();
}

export const api = {
  health: () => request<Health>("/api/health"),
  listSources: () => request<KnowledgeSource[]>("/api/sources"),
  createSource: (name: string, description: string) =>
    request<KnowledgeSource>("/api/sources", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, description }),
    }),
  deleteSource: (id: string) => request<void>(`/api/sources/${id}`, { method: "DELETE" }),
  listDocuments: (sourceId: string) =>
    request<SourceDocument[]>(`/api/sources/${sourceId}/documents`),
  uploadDocument: (sourceId: string, file: File, docType: DocType, vision: boolean) => {
    const form = new FormData();
    form.append("file", file);
    form.append("doc_type", docType);
    form.append("vision", String(vision));
    return request<SourceDocument>(`/api/sources/${sourceId}/documents`, {
      method: "POST",
      body: form,
    });
  },
  reingestDocument: (id: string) =>
    request<SourceDocument>(`/api/documents/${id}/reingest`, { method: "POST" }),
  deleteDocument: (id: string) => request<void>(`/api/documents/${id}`, { method: "DELETE" }),
  listConversations: () => request<Conversation[]>("/api/conversations"),
  deleteConversation: (id: string) =>
    request<void>(`/api/conversations/${id}`, { method: "DELETE" }),
  getMessages: (conversationId: string) =>
    request<ChatMessage[]>(`/api/conversations/${conversationId}/messages`),
  pageImageUrl: (documentId: string, page: number) =>
    withApiKey(`${API_URL}/api/documents/${documentId}/pages/${page}/image`),
};

export type ChatEvent =
  | { event: "conversation"; data: { id: string; title: string } }
  | { event: "token"; data: { text: string } }
  | { event: "tool_start"; data: { name: string; args: Record<string, unknown> } }
  | { event: "tool_end"; data: { name: string } }
  | { event: "sources"; data: SourceRef[] }
  | { event: "error"; data: { message: string } }
  | { event: "done"; data: Record<string, never> };

/** POST /api/chat und die SSE-Antwort Ereignis für Ereignis ausliefern. */
export async function* streamChat(
  body: { conversation_id: string | null; message: string; source_ids: string[] },
  signal: AbortSignal,
): AsyncGenerator<ChatEvent> {
  const response = await fetch(`${API_URL}/api/chat`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(body),
    signal,
  });
  if (!response.ok || !response.body) {
    const detail = await response.json().catch(() => null);
    throw new Error(detail?.detail ?? `${response.status} ${response.statusText}`);
  }

  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += value;
    let boundary: number;
    while ((boundary = buffer.indexOf("\n\n")) >= 0) {
      const block = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const event = block.match(/^event: (.+)$/m)?.[1];
      const data = block.match(/^data: (.+)$/m)?.[1];
      if (event && data) yield { event, data: JSON.parse(data) } as ChatEvent;
    }
  }
}

// --- Werk: Hallen, Maschinen, Fehlerliste, Schaltschrank ---------------------------------

export type MachineType = "conveyor" | "main" | "packaging" | "robot" | "storage" | "other";

export const MACHINE_TYPE_LABELS: Record<MachineType, string> = {
  conveyor: "Förderband",
  main: "Hauptmaschine",
  packaging: "Verpackung",
  robot: "Roboter",
  storage: "Lager / Puffer",
  other: "Sonstiges",
};

export type HallKind = "generic" | "base" | "production" | "warehouse" | "office";

export const HALL_KIND_LABELS: Record<HallKind, string> = {
  generic: "Halle",
  base: "Grundstoff",
  production: "Verarbeitung",
  warehouse: "Lager",
  office: "Büro",
};

export interface Hall {
  id: string;
  name: string;
  description: string;
  created_at: string;
  machine_count: number;
  kind: HallKind;
  site_x: number;
  site_y: number;
  site_w: number;
  site_h: number;
}

export interface Machine {
  id: string;
  hall_id: string;
  name: string;
  machine_type: MachineType;
  description: string;
  source_id: string | null;
  source_name: string | null;
  has_image: boolean;
  pos_x: number;
  pos_y: number;
  order_index: number;
  fault_count: number;
  cabinet_count: number;
  document_count: number;
  line: string;
  /** Erste Kennzahl als Kurztext, z. B. "2.200 m/min" */
  key_figure: string;
  hall_name: string;
}

export interface Flow {
  id?: string;
  from_machine_id: string;
  to_machine_id: string;
  label: string;
}

export interface HallDetail extends Hall {
  machines: Machine[];
  flows: Flow[];
}

export interface Fault {
  id: string;
  machine_id: string;
  code: string;
  symptom: string;
  cause: string;
  fix: string;
  doc_ref: string;
  tags: string[];
}

export type FaultInput = Omit<Fault, "id" | "machine_id">;

export interface Hotspot {
  id: string;
  cabinet_id: string;
  tag: string;
  label: string;
  kind: string;
  x: number;
  y: number;
  w: number;
  h: number;
  confidence: number | null;
  origin: "manual" | "vision";
  confirmed: boolean;
}

export interface Cabinet {
  id: string;
  machine_id: string;
  title: string;
  width: number;
  height: number;
  created_at: string;
  hotspots: Hotspot[];
}

export interface SiteMachine {
  id: string;
  name: string;
  machine_type: MachineType;
  pos_x: number;
  pos_y: number;
  line: string;
}

export interface SiteHall {
  id: string;
  name: string;
  kind: HallKind;
  description: string;
  x: number;
  y: number;
  w: number;
  h: number;
  machine_count: number;
  /** Eintraege der Fehlerlisten (Katalog) */
  fault_count: number;
  /** laufende Fehlersuchen: der einzige rote Wert im Standortplan */
  open_diagnoses: number;
  lines: string[];
  docks: number;
  machines: SiteMachine[];
}

export interface SiteFlow {
  id?: string;
  from_hall_id: string;
  to_hall_id: string;
  label: string;
}

export interface SiteData {
  halls: SiteHall[];
  flows: SiteFlow[];
}

export interface MachineSpec {
  id?: string;
  position?: number;
  label: string;
  value: string;
  unit: string;
  source: string;
}

export interface MachineDetail extends Machine {
  faults: Fault[];
  cabinets: Cabinet[];
}

export interface TagHit {
  document_id: string;
  filename: string;
  doc_type: string;
  page: number | null;
  section: string;
  context: string;
}

export interface TagLookup {
  tag: string;
  hits: TagHit[];
  bom_line: string | null;
}

const json = (body: unknown, method = "POST"): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const plant = {
  listHalls: () => request<Hall[]>("/api/halls"),
  createHall: (name: string, description = "", kind: HallKind = "generic") =>
    request<Hall>("/api/halls", json({ name, description, kind })),
  getHall: (id: string) => request<HallDetail>(`/api/halls/${id}`),
  updateHall: (id: string, body: Partial<Pick<Hall, "name" | "description" | "kind" | "site_x" | "site_y" | "site_w" | "site_h">>) =>
    request<Hall>(`/api/halls/${id}`, json(body, "PATCH")),
  deleteHall: (id: string) => request<void>(`/api/halls/${id}`, { method: "DELETE" }),
  replaceFlows: (hallId: string, flows: Flow[]) =>
    request<Flow[]>(`/api/halls/${hallId}/flows`, json(flows.map(({ from_machine_id, to_machine_id, label }) => ({ from_machine_id, to_machine_id, label })), "PUT")),

  createMachine: (hallId: string, body: { name: string; machine_type: MachineType; pos_x?: number; pos_y?: number; line?: string }) =>
    request<Machine>(`/api/halls/${hallId}/machines`, json(body)),
  getMachine: (id: string) => request<MachineDetail>(`/api/machines/${id}`),
  updateMachine: (
    id: string,
    body: Partial<Pick<Machine, "name" | "machine_type" | "description" | "source_id" | "pos_x" | "pos_y" | "order_index" | "line">> & { clear_source?: boolean },
  ) => request<Machine>(`/api/machines/${id}`, json(body, "PATCH")),
  deleteMachine: (id: string) => request<void>(`/api/machines/${id}`, { method: "DELETE" }),
  uploadMachineImage: (id: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<Machine>(`/api/machines/${id}/image`, { method: "POST", body: form });
  },
  machineImageUrl: (id: string, bust = 0) => withApiKey(`${API_URL}/api/machines/${id}/image?v=${bust}`),

  createFault: (machineId: string, body: FaultInput) => request<Fault>(`/api/machines/${machineId}/faults`, json(body)),
  updateFault: (id: string, body: FaultInput) => request<Fault>(`/api/faults/${id}`, json(body, "PATCH")),
  deleteFault: (id: string) => request<void>(`/api/faults/${id}`, { method: "DELETE" }),

  uploadCabinet: (machineId: string, file: File, title: string) => {
    const form = new FormData();
    form.append("file", file);
    form.append("title", title);
    return request<Cabinet>(`/api/machines/${machineId}/cabinets`, { method: "POST", body: form });
  },
  getCabinet: (id: string) => request<Cabinet>(`/api/cabinets/${id}`),
  cabinetImageUrl: (id: string) => withApiKey(`${API_URL}/api/cabinets/${id}/image`),
  deleteCabinet: (id: string) => request<void>(`/api/cabinets/${id}`, { method: "DELETE" }),
  detectCabinet: (id: string) => request<Cabinet>(`/api/cabinets/${id}/detect`, { method: "POST" }),
  createHotspot: (cabinetId: string, body: Omit<Hotspot, "id" | "cabinet_id" | "confidence" | "origin">) =>
    request<Hotspot>(`/api/cabinets/${cabinetId}/hotspots`, json(body)),
  updateHotspot: (id: string, body: Partial<Omit<Hotspot, "id" | "cabinet_id" | "confidence" | "origin">>) =>
    request<Hotspot>(`/api/hotspots/${id}`, json(body, "PATCH")),
  deleteHotspot: (id: string) => request<void>(`/api/hotspots/${id}`, { method: "DELETE" }),

  lookupTag: (machineId: string, tag: string) =>
    request<TagLookup>(`/api/machines/${machineId}/tags/${encodeURIComponent(tag)}`),

  getSite: () => request<SiteData>("/api/site"),
  replaceSiteFlows: (flows: SiteFlow[]) =>
    request<SiteFlow[]>("/api/site/flows", json(flows.map(({ from_hall_id, to_hall_id, label }) => ({ from_hall_id, to_hall_id, label })), "PUT")),
  getSpecs: (machineId: string) => request<MachineSpec[]>(`/api/machines/${machineId}/specs`),
  replaceSpecs: (machineId: string, specs: MachineSpec[]) =>
    request<MachineSpec[]>(`/api/machines/${machineId}/specs`, json(specs.map(({ label, value, unit, source }) => ({ label, value, unit, source })), "PUT")),
};

// --- Draufsicht (Maschinen-Layout) und globale Suche --------------------------------------------

export const LAYOUT_KINDS = [
  "Motor",
  "Sensor",
  "Taster",
  "Not-Halt",
  "Leuchte",
  "Schaltschrank",
  "Band/Förderer",
  "Rahmen",
  "Schutztür",
  "Sonstiges",
] as const;

export type LayoutKind = (typeof LAYOUT_KINDS)[number];

export interface LayoutPart {
  id: string;
  layout_id: string;
  tag: string;
  label: string;
  kind: LayoutKind;
  shape: "rect" | "circle";
  x_mm: number;
  y_mm: number;
  w_mm: number;
  h_mm: number;
  rotation_deg: number;
  confidence: number | null;
  origin: "manual" | "vision";
  confirmed: boolean;
}

export type LayoutPartInput = Omit<LayoutPart, "id" | "layout_id" | "confidence" | "origin">;

export interface Layout {
  id: string;
  machine_id: string;
  width_mm: number;
  depth_mm: number;
  has_image: boolean;
  document_id: string | null;
  page: number | null;
  scale_note: string;
  updated_at: string;
  parts: LayoutPart[];
}

export type LayoutInput = Pick<Layout, "width_mm" | "depth_mm" | "document_id" | "page" | "scale_note">;

export interface TagSearchHit {
  tag: string;
  tag_type: string;
  occurrences: number;
  machines: { id: string; name: string }[];
}

export const layout = {
  /** null, wenn die Maschine noch keine Draufsicht hat (404). */
  get: async (machineId: string): Promise<Layout | null> => {
    const response = await fetch(`${API_URL}/api/machines/${machineId}/layout`, { headers: authHeaders() });
    if (response.status === 404) return null;
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(body?.detail ?? `${response.status} ${response.statusText}`);
    }
    return response.json();
  },
  put: (machineId: string, body: LayoutInput) =>
    request<Layout>(`/api/machines/${machineId}/layout`, json(body, "PUT")),
  uploadImage: (machineId: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<Layout>(`/api/machines/${machineId}/layout/image`, { method: "POST", body: form });
  },
  imageUrl: (machineId: string, bust = "") =>
    withApiKey(`${API_URL}/api/machines/${machineId}/layout/image?v=${encodeURIComponent(bust)}`),
  createPart: (layoutId: string, body: Partial<LayoutPartInput>) =>
    request<LayoutPart>(`/api/layouts/${layoutId}/parts`, json(body)),
  updatePart: (partId: string, body: Partial<LayoutPartInput>) =>
    request<LayoutPart>(`/api/layout-parts/${partId}`, json(body, "PATCH")),
  deletePart: (partId: string) => request<void>(`/api/layout-parts/${partId}`, { method: "DELETE" }),
  detect: (layoutId: string) => request<Layout>(`/api/layouts/${layoutId}/detect`, { method: "POST" }),
  exportUrl: (layoutId: string) => `${API_URL}/api/layouts/${layoutId}/export`,
};

export const searchTags = (q: string) =>
  request<TagSearchHit[]>(`/api/tags/search?q=${encodeURIComponent(q)}`);

// --- Chat: Belege anspringen, Befundkarte --------------------------------------------------------

export interface LocateResult {
  page: number;
  column: number | null;
  box: { x0: number; y0: number; x1: number; y1: number } | null;
}

export interface FactValue {
  text: string;
  ref: string;
  document_id: string | null;
  filename: string | null;
  page: number | null;
}

export interface FactCardData {
  tag: string;
  title: string | null;
  bom_line: string | null;
  rows: { label: string; values: FactValue[] }[];
}

export const locate = (documentId: string, ref: string) =>
  request<LocateResult>(`/api/documents/${documentId}/locate?ref=${encodeURIComponent(ref)}`);

/** null, wenn der Index zu dem Kennzeichen nichts hat (404). */
export async function factCard(tag: string, sourceIds: string[]): Promise<FactCardData | null> {
  const params = new URLSearchParams({ tag });
  sourceIds.forEach((id) => params.append("source_ids", id));
  const response = await fetch(`${API_URL}/api/facts?${params}`, { headers: authHeaders() });
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return response.json();
}

// --- Signalweg ---------------------------------------------------------------------------------

export type SignalNodeKind = "device" | "terminal" | "address" | "network" | "variable";

export interface SignalNode {
  id: string;
  kind: SignalNodeKind;
  label: string;
  ref: string;
  detail: string;
  level: number;
}

export interface SignalPathData {
  start: string;
  nodes: SignalNode[];
  edges: { source: string; target: string }[];
  schematic: { document_id: string; filename: string } | null;
}

export const signalPath = (tag: string, sourceId: string) =>
  request<SignalPathData>(`/api/signal-path?tag=${encodeURIComponent(tag)}&source_id=${encodeURIComponent(sourceId)}`);

// --- Gefuehrte Fehlersuche -------------------------------------------------------------------

export type StepStatus = "open" | "ok" | "nok" | "skip";

export interface DiagnosisStep {
  text: string;
  tag: string;
  ref: string;
  status: StepStatus;
  note: string;
}

export interface Diagnosis {
  id: string;
  machine_id: string;
  fault_id: string | null;
  title: string;
  steps: DiagnosisStep[];
  outcome: "open" | "resolved" | "unresolved";
  finding: string;
  started_at: string;
  finished_at: string | null;
}

export const diagnoses = {
  list: (machineId: string) => request<Diagnosis[]>(`/api/machines/${machineId}/diagnoses`),
  start: (machineId: string, faultId: string | null, title = "") =>
    request<Diagnosis>(`/api/machines/${machineId}/diagnoses`, json({ fault_id: faultId, title })),
  updateStep: (id: string, index: number, change: { status?: StepStatus; note?: string }) =>
    request<Diagnosis>(`/api/diagnoses/${id}/steps/${index}`, json(change, "PATCH")),
  update: (id: string, body: { steps?: DiagnosisStep[]; finding?: string }) =>
    request<Diagnosis>(`/api/diagnoses/${id}`, json(body, "PATCH")),
  finish: (id: string, body: { outcome: "resolved" | "unresolved"; finding: string; add_to_faults: boolean }) =>
    request<Diagnosis>(`/api/diagnoses/${id}/finish`, json(body)),
  remove: (id: string) => request<void>(`/api/diagnoses/${id}`, { method: "DELETE" }),
};

// --- Onboarding aus der Doku -----------------------------------------------------------------

export interface OnboardingProposal {
  source_id: string;
  source_name: string;
  name: string;
  machine_type: MachineType;
  devices: number;
  documents: { filename: string; doc_type: DocType }[];
  faults: FaultInput[];
  hints: string[];
}

export const onboarding = {
  proposal: (sourceId: string) => request<OnboardingProposal>(`/api/sources/${sourceId}/onboarding`),
  create: (hallId: string, body: { source_id: string; name: string; machine_type: MachineType; faults: FaultInput[] }) =>
    request<Machine>(`/api/halls/${hallId}/onboard`, json(body)),
};

// --- Planung: Vorkalkulation ------------------------------------------------------------------

export type RateUnit = "unit_min" | "pallet_h";
export type QuantityUnit = "unit" | "pallet";

export interface BomInfo {
  material_code: string;
  material_name: string;
  unit: string;
  qty: number;
  per: QuantityUnit;
}

export interface RoutingInfo {
  seq: number;
  machine_id: string;
  machine_name: string;
  machine_line: string;
  rate: number;
  rate_unit: RateUnit;
  setup_min: number;
  coupled: boolean;
  basis: string;
  hourly_rate: number | null;
}

export interface ArticleInfo {
  id: string;
  code: string;
  name: string;
  unit_name: string;
  units_per_pallet: number;
  sheets_per_unit: number;
  sheet_w_mm: number;
  sheet_l_mm: number;
  plies: number;
  gsm: number;
  waste_pct: number;
  line: string;
  description: string;
  paper_kg_per_unit: number;
  routing: RoutingInfo[];
  bom: BomInfo[];
}

export interface MaterialInfo {
  id: string;
  code: string;
  name: string;
  unit: string;
  price: number | null;
  price_source: string;
  made_on: string | null;
  made_rate_per_h: number | null;
  made_basis: string;
  bom: BomInfo[];
}

export interface CalcPositionInput {
  article_id: string;
  quantity: number;
  unit: QuantityUnit;
}

export interface CalcRequest {
  received_at?: string;
  due_date?: string | null;
  positions: CalcPositionInput[];
}

export type CalendarKey = "office" | "production" | "shipping";

export interface CalcStation {
  key: string;
  label: string;
  group: string;
  start: string;
  end: string;
  work_minutes: number;
  calendar: CalendarKey;
  basis: string;
  bottleneck: string | null;
  machines: string[];
  position: number | null;
}

export interface CalcMaterial {
  code: string;
  name: string;
  unit: string;
  qty: number;
  level: number;
  parent: string | null;
  basis: string;
  price: number | null;
  price_source: string;
  cost: number;
  made: boolean;
}

export interface CalcCost {
  article: string;
  units: number;
  unit_name: string;
  material: number;
  production: number;
  office: number;
  shipping: number;
  total: number;
  per_unit: number;
}

export interface CalcResult {
  received_at: string;
  due_date: string | null;
  ready_at: string;
  meets_due: boolean | null;
  days_delta: number | null;
  summary: {
    units: number;
    pallets: number;
    trucks: number;
    paper_t: number;
    line_minutes: number;
    bottleneck: string | null;
    lead_minutes: number;
  };
  stations: CalcStation[];
  closed: Partial<Record<CalendarKey, [string, string][]>>;
  positions: { article_id: string; article: string; code: string; unit_name: string; units: number; pallets: number; paper_kg_per_unit: number; ready: string }[];
  materials: CalcMaterial[];
  costs: { positions: CalcCost[]; total: Omit<CalcCost, "article" | "units" | "unit_name" | "per_unit">; office_minutes: number; trucks: number };
  warnings: string[];
}

export const planning = {
  articles: () => request<ArticleInfo[]>("/api/articles"),
  materials: () => request<MaterialInfo[]>("/api/materials"),
  calc: (body: CalcRequest) => request<CalcResult>("/api/calc", json(body)),
};

// --- Leitstand: Auftragsbuch und Simulation ---------------------------------------------------

export type SimResourceKind = "office" | "paper" | "line" | "dock";

export interface SimStage {
  stage: string;
  label: string;
  resource: string;
  slot: number | null;
  arrive: string;
  start: string;
  end: string;
}

export interface SimOrderResult {
  id: string;
  number: string;
  customer: string;
  value: number;
  pallets: number;
  due: string | null;
  received_at: string;
  ready_at: string | null;
  shipped_at: string | null;
  days_delta: number | null;
  on_time: boolean | null;
  positions: { code: string; units: number; from_stock: number; produced: number }[];
  stages: SimStage[];
  trucks: { truck: number; dock: number; start: string; end: string }[];
}

export interface SimResult {
  start: string | null;
  end: string | null;
  resources: { key: string; label: string; kind: SimResourceKind; capacity: number }[];
  orders: SimOrderResult[];
  stock: Record<string, { name: string; units_per_pallet: number; points: [string, number][] }>;
  closed: Partial<Record<"office" | "shipping", [string, string][]>>;
  kpis: {
    on_time_rate: number | null;
    avg_lead_hours: number | null;
    utilization: Record<string, number>;
    avg_wait_hours: Record<string, number>;
  };
  warnings: string[];
}

export interface OrderInfo {
  id: string;
  number: string;
  customer: string | null;
  received_at: string;
  due_date: string | null;
  lines: { article_id: string; code: string; name: string; unit_name: string; quantity: number; unit: QuantityUnit }[];
}

export const leitstand = {
  orders: () => request<OrderInfo[]>("/api/orders"),
  createOrder: (body: { customer: string; received_at?: string; due_date?: string | null; lines: CalcPositionInput[] }) =>
    request<OrderInfo>("/api/orders", json(body)),
  deleteOrder: (id: string) => request<void>(`/api/orders/${id}`, { method: "DELETE" }),
  simulate: (orderIds?: string[]) => request<SimResult>("/api/simulation", json({ order_ids: orderIds ?? null })),
};
