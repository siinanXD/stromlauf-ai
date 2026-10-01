/**
 * Stoerfall-Liste als reine Funktionen: sofort anlegen mit vorlaeufiger ID, nach dem Stream-Ereignis
 * "conversation" die echte ID einsetzen, mit der Serverliste zusammenfuehren, filtern und sortieren.
 */
import type { Conversation } from "@/lib/api";

export type Outcome = "open" | "resolved";
export type IncidentFilter = Outcome;

export interface Incident extends Conversation {
  /** Angelegt, der Server hat die ID noch nicht vergeben. */
  pending?: boolean;
  /** In dieser Sitzung angelegt: bleibt sichtbar, auch wenn eine aeltere Serverliste ihn noch nicht kennt. */
  local?: boolean;
}

export const TEMP_PREFIX = "tmp-";

export const isTempId = (id: string | null | undefined): boolean => Boolean(id?.startsWith(TEMP_PREFIX));

let counter = 0;
/** Vorlaeufige ID; eindeutig je Sitzung, beginnt mit "tmp-". */
export function newTempId(now = Date.now()): string {
  counter += 1;
  return `${TEMP_PREFIX}${now.toString(36)}-${counter}`;
}

/** Fehlt outcome (Backend vor der Stoerfall-Arbeitsflaeche), gilt der Stoerfall als offen. */
export function outcomeOf(incident: Pick<Conversation, "outcome">): Outcome {
  return incident.outcome === "resolved" ? "resolved" : "open";
}

/** Neuer Eintrag oben in der Liste, bevor der Server antwortet. */
export function addPending(list: Incident[], input: { id: string; title: string; sourceId: string; now?: Date }): Incident[] {
  const incident: Incident = {
    id: input.id,
    title: input.title,
    source_ids: [input.sourceId],
    updated_at: (input.now ?? new Date()).toISOString(),
    outcome: "open",
    finding: "",
    pending: true,
    local: true,
  };
  return [incident, ...list.filter((i) => i.id !== input.id)];
}

/** Ereignis "conversation": vorlaeufige ID durch die echte ersetzen, Titel vom Server uebernehmen. */
export function confirmPending(list: Incident[], tempId: string, conversation: { id: string; title?: string }): Incident[] {
  const pending = list.find((i) => i.id === tempId);
  if (!pending) return list;
  const confirmed: Incident = { ...pending, id: conversation.id, title: conversation.title || pending.title, pending: false };
  return list.filter((i) => i.id !== conversation.id).map((i) => (i.id === tempId ? confirmed : i));
}

/** Serverliste gewinnt; lokale Eintraege, die der Server noch nicht kennt, bleiben stehen. */
export function mergeServer(list: Incident[], server: Conversation[]): Incident[] {
  const known = new Set(server.map((c) => c.id));
  const local = list.filter((i) => (i.pending || i.local) && !known.has(i.id));
  return [...local, ...server];
}

export function replaceIncident(list: Incident[], conversation: Conversation): Incident[] {
  return list.map((i) => (i.id === conversation.id ? { ...i, ...conversation, pending: false } : i));
}

export function removeIncident(list: Incident[], id: string): Incident[] {
  return list.filter((i) => i.id !== id);
}

const time = (incident: Incident) => {
  const t = Date.parse(incident.updated_at);
  return Number.isNaN(t) ? 0 : t;
};

/** Gefiltert nach Stand und Suchtext (Titel oder Befund), neuester Stand zuerst. */
export function visibleIncidents(list: Incident[], filter: IncidentFilter, query = ""): Incident[] {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean);
  return list
    .filter((i) => outcomeOf(i) === filter)
    .filter((i) => {
      if (words.length === 0) return true;
      const text = `${i.title} ${i.finding ?? ""}`.toLowerCase();
      return words.every((w) => text.includes(w));
    })
    .sort((a, b) => time(b) - time(a));
}

export function countByOutcome(list: Incident[]): Record<Outcome, number> {
  const counts: Record<Outcome, number> = { open: 0, resolved: 0 };
  for (const incident of list) counts[outcomeOf(incident)] += 1;
  return counts;
}

/** "vor 5 Min." / "heute 14:03" / "12.09." fuer die Liste; Eingabe ISO-Zeit. */
export function relativeTime(iso: string, now = new Date()): string {
  const t = new Date(iso);
  if (Number.isNaN(t.getTime())) return "";
  const minutes = Math.round((now.getTime() - t.getTime()) / 60000);
  if (minutes < 1) return "gerade eben";
  if (minutes < 60) return `vor ${minutes} Min.`;
  const sameDay = t.toDateString() === now.toDateString();
  const hhmm = `${String(t.getHours()).padStart(2, "0")}:${String(t.getMinutes()).padStart(2, "0")}`;
  if (sameDay) return `heute ${hhmm}`;
  return `${String(t.getDate()).padStart(2, "0")}.${String(t.getMonth() + 1).padStart(2, "0")}.`;
}
