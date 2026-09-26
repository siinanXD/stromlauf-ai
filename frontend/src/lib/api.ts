export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8010";

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
  const response = await fetch(`${API_URL}${path}`, init);
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
    `${API_URL}/api/documents/${documentId}/pages/${page}/image`,
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
    headers: { "Content-Type": "application/json" },
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

export interface Hall {
  id: string;
  name: string;
  description: string;
  created_at: string;
  machine_count: number;
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
  createHall: (name: string, description = "") => request<Hall>("/api/halls", json({ name, description })),
  getHall: (id: string) => request<HallDetail>(`/api/halls/${id}`),
  updateHall: (id: string, body: Partial<Pick<Hall, "name" | "description">>) =>
    request<Hall>(`/api/halls/${id}`, json(body, "PATCH")),
  deleteHall: (id: string) => request<void>(`/api/halls/${id}`, { method: "DELETE" }),
  replaceFlows: (hallId: string, flows: Flow[]) =>
    request<Flow[]>(`/api/halls/${hallId}/flows`, json(flows.map(({ from_machine_id, to_machine_id, label }) => ({ from_machine_id, to_machine_id, label })), "PUT")),

  createMachine: (hallId: string, body: { name: string; machine_type: MachineType; pos_x?: number; pos_y?: number }) =>
    request<Machine>(`/api/halls/${hallId}/machines`, json(body)),
  getMachine: (id: string) => request<MachineDetail>(`/api/machines/${id}`),
  updateMachine: (
    id: string,
    body: Partial<Pick<Machine, "name" | "machine_type" | "description" | "source_id" | "pos_x" | "pos_y" | "order_index">> & { clear_source?: boolean },
  ) => request<Machine>(`/api/machines/${id}`, json(body, "PATCH")),
  deleteMachine: (id: string) => request<void>(`/api/machines/${id}`, { method: "DELETE" }),
  uploadMachineImage: (id: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<Machine>(`/api/machines/${id}/image`, { method: "POST", body: form });
  },
  machineImageUrl: (id: string, bust = 0) => `${API_URL}/api/machines/${id}/image?v=${bust}`,

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
  cabinetImageUrl: (id: string) => `${API_URL}/api/cabinets/${id}/image`,
  deleteCabinet: (id: string) => request<void>(`/api/cabinets/${id}`, { method: "DELETE" }),
  detectCabinet: (id: string) => request<Cabinet>(`/api/cabinets/${id}/detect`, { method: "POST" }),
  createHotspot: (cabinetId: string, body: Omit<Hotspot, "id" | "cabinet_id" | "confidence" | "origin">) =>
    request<Hotspot>(`/api/cabinets/${cabinetId}/hotspots`, json(body)),
  updateHotspot: (id: string, body: Partial<Omit<Hotspot, "id" | "cabinet_id" | "confidence" | "origin">>) =>
    request<Hotspot>(`/api/hotspots/${id}`, json(body, "PATCH")),
  deleteHotspot: (id: string) => request<void>(`/api/hotspots/${id}`, { method: "DELETE" }),

  lookupTag: (machineId: string, tag: string) =>
    request<TagLookup>(`/api/machines/${machineId}/tags/${encodeURIComponent(tag)}`),
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
    const response = await fetch(`${API_URL}/api/machines/${machineId}/layout`);
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
  imageUrl: (machineId: string, bust = "") => `${API_URL}/api/machines/${machineId}/layout/image?v=${encodeURIComponent(bust)}`,
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
  const response = await fetch(`${API_URL}/api/facts?${params}`);
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return response.json();
}
