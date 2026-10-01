/**
 * Erstes Laden der Maschinenseite: Maschine und Stoerfaelle starten gleichzeitig und schon beim ersten Rendern,
 * vor den Effekten von Kopfzeile, Kostenchip und Leiste (die sonst die Verbindungen zum Server belegen). Die
 * Stoerfall-Liste ist das groesste Element beim Oeffnen (LCP) und wartet so nicht mehr auf die Maschine.
 */
import { api, plant, type Conversation, type MachineDetail } from "@/lib/api";

interface Entry {
  machine?: Promise<MachineDetail>;
  incidents?: Promise<Conversation[] | null>;
  at: number;
}

const entries = new Map<string, Entry>();
/** Danach gilt ein gestarteter Abruf als veraltet und wird neu gestellt. */
const FRESH_MS = 10_000;

function fresh(machineId: string, now: number): Entry | undefined {
  const entry = entries.get(machineId);
  return entry && now - entry.at < FRESH_MS ? entry : undefined;
}

/** Idempotent; im Browser sofort, auf dem Server nie (dort gibt es keinen Zugang zur API des Nutzers). */
export function startInitialLoad(machineId: string, now = Date.now()): void {
  if (typeof window === "undefined" || fresh(machineId, now)) return;
  const machine = plant.getMachine(machineId);
  const incidents = api.listConversationsForMachine(machineId);
  // Wer sie abholt, haengt eigene Handler an; bis dahin keine unbehandelte Ablehnung
  machine.catch(() => {});
  incidents.catch(() => {});
  entries.set(machineId, { machine, incidents, at: now });
}

/** Der gestartete Abruf (einmal), sonst ein neuer. */
export function takeMachine(machineId: string, now = Date.now()): Promise<MachineDetail> {
  const entry = fresh(machineId, now);
  const pending = entry?.machine;
  if (entry && pending) {
    entry.machine = undefined;
    return pending;
  }
  return plant.getMachine(machineId);
}

export function takeIncidents(machineId: string, now = Date.now()): Promise<Conversation[] | null> {
  const entry = fresh(machineId, now);
  const pending = entry?.incidents;
  if (entry && pending) {
    entry.incidents = undefined;
    return pending;
  }
  return api.listConversationsForMachine(machineId);
}

/**
 * Stoerfaelle der Quelle dieser Maschine: Ergebnis von machine_id, sonst (aelteres Backend) source_id. Ein Server,
 * der machine_id still ignoriert, liefert alle Chats; deshalb zaehlen nur Konversationen mit genau dieser Quelle.
 */
export async function incidentsFor(request: Promise<Conversation[] | null>, sourceId: string): Promise<Conversation[]> {
  const byMachine = await request;
  const list = byMachine ?? (await api.listConversations(sourceId));
  return list.filter((c) => Array.isArray(c.source_ids) && c.source_ids.length === 1 && c.source_ids[0] === sourceId);
}

export function clearInitialLoad(): void {
  entries.clear();
}
