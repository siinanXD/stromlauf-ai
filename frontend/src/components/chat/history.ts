/** Verlauf in Seiten fuer den Chat, rein und ohne React. */
import type { ChatMessage } from "@/lib/api";

/** So viele Nachrichten laedt der Chat beim Oeffnen und je Nachladen. */
export const PAGE_SIZE = 30;

/**
 * Index der aeltesten geladenen Nachricht, wenn es davor noch welche gibt; sonst null. Ein Server ohne Seiten
 * (kein index an den Nachrichten) liefert ohnehin den ganzen Verlauf.
 */
export function olderBefore(messages: Pick<ChatMessage, "index">[]): number | null {
  const first = messages[0];
  return first && typeof first.index === "number" && first.index > 0 ? first.index : null;
}

/** Aeltere Seite vorne anfuegen; doppelte und nicht aeltere Nachrichten fallen weg (Server ohne before). */
export function olderPage<T extends Pick<ChatMessage, "index">>(current: T[], page: T[]): T[] {
  const before = olderBefore(current);
  if (before === null) return [];
  const known = new Set(current.map((m) => m.index));
  return page.filter((m) => typeof m.index === "number" && m.index < before && !known.has(m.index));
}
