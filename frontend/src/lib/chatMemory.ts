/** Zuletzt geoeffneter Chat je Maschine (Browser-Komfort, localStorage) und das meta der letzten Antwort im Verlauf. */

import type { AnswerMeta, ChatMessage } from "./api";

const key = (machineId: string) => `stromlauf:chat:${machineId}`;

function storage(): Storage | undefined {
  try {
    return (globalThis as { localStorage?: Storage }).localStorage;
  } catch {
    return undefined;
  }
}

/** id merken; null vergisst die Auswahl. Ohne oder mit blockiertem Speicher passiert nichts. */
export function rememberConversation(machineId: string, id: string | null): void {
  try {
    const store = storage();
    if (!store) return;
    if (id) store.setItem(key(machineId), id);
    else store.removeItem(key(machineId));
  } catch {
    // privates Fenster, gesperrte Website-Daten: dann eben kein Gedaechtnis
  }
}

export function recallConversation(machineId: string): string | null {
  try {
    return storage()?.getItem(key(machineId)) ?? null;
  } catch {
    return null;
  }
}

/** meta der letzten Antwort mit meta, damit die Maschinenseite nach dem Laden des Verlaufs markieren kann. */
export function lastAnswerMeta(messages: ChatMessage[]): AnswerMeta | undefined {
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const message = messages[i];
    if (message.role === "assistant" && message.meta) return message.meta;
  }
  return undefined;
}
