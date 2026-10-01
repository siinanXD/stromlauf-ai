/**
 * Treffer der Fehlerliste je (Maschine, Meldung), einmal je Sitzung geladen: Beim Senden startet die Abfrage
 * parallel zum Chat, der Block "Fehlerliste" liest dasselbe Ergebnis. Fehler (alter Server ohne Endpunkt, kein
 * Netz) ergeben null, der Block entfaellt dann still.
 */
import { api, type Fault, type FaultHits } from "@/lib/api";

interface Entry {
  promise: Promise<FaultHits | null>;
  value?: FaultHits | null;
  done: boolean;
}

const cache = new Map<string, Entry>();
/** Fehlereintraege aus Treffern, auch von anderen Maschinen, fuer das Detail "Fehlereintrag". */
const faults = new Map<string, { fault: Fault; machineName: string | null }>();

const keyOf = (machineId: string, query: string) => `${machineId}\u0000${query.trim().toLowerCase()}`;

/** Fehlende Listen (halb fertiges Backend) als leer lesen, hoechstens 5 je Liste anzeigen. */
export function normalizeHits(raw: Partial<FaultHits> | null | undefined): FaultHits | null {
  if (!raw || typeof raw !== "object") return null;
  return {
    faults: Array.isArray(raw.faults) ? raw.faults.slice(0, 5) : [],
    experience: Array.isArray(raw.experience) ? raw.experience.slice(0, 5) : [],
    incidents: Array.isArray(raw.incidents) ? raw.incidents.slice(0, 5) : [],
  };
}

export function hasHits(hits: FaultHits | null | undefined): hits is FaultHits {
  return Boolean(hits && (hits.faults.length > 0 || hits.experience.length > 0 || hits.incidents.length > 0));
}

function remember(hits: FaultHits | null) {
  if (!hits) return;
  for (const fault of hits.faults) faults.set(fault.id, { fault, machineName: null });
  for (const entry of hits.experience) faults.set(entry.fault.id, { fault: entry.fault, machineName: entry.machine_name });
}

/** Startet die Abfrage (oder liefert die laufende); nie abgelehnt. */
export function prefetchFaultHits(machineId: string, query: string): Promise<FaultHits | null> {
  const key = keyOf(machineId, query);
  const existing = cache.get(key);
  if (existing) return existing.promise;
  const entry: Entry = { done: false, promise: Promise.resolve(null) };
  entry.promise = api
    .faultHits(machineId, query.trim())
    .then((raw) => normalizeHits(raw))
    .catch(() => null)
    .then((value) => {
      entry.value = value;
      entry.done = true;
      remember(value);
      return value;
    });
  cache.set(key, entry);
  return entry.promise;
}

/** Ergebnis, wenn schon da; undefined = noch nicht geladen oder laeuft. */
export function peekFaultHits(machineId: string, query: string): FaultHits | null | undefined {
  const entry = cache.get(keyOf(machineId, query));
  return entry?.done ? entry.value : undefined;
}

/** Fuer Tests und Vorschau: Ergebnis direkt hinterlegen. */
export function seedFaultHits(machineId: string, query: string, hits: FaultHits | null): void {
  const value = normalizeHits(hits);
  cache.set(keyOf(machineId, query), { promise: Promise.resolve(value), value, done: true });
  remember(value);
}

export function knownFault(faultId: string): { fault: Fault; machineName: string | null } | undefined {
  return faults.get(faultId);
}

export function clearFaultHits(): void {
  cache.clear();
  faults.clear();
}
