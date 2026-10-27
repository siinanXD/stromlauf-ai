import type { MachineNote } from "@/lib/api";

export const QUELLE_LABELS: Record<MachineNote["quelle"], string> = { lauf: "Lauf", chat: "Chat", mensch: "Mensch" };

/** Beschriftung eines Belegs: Dateiname, mit Seite wenn bekannt. */
export function belegText(b: MachineNote["belege"][number]): string {
  return b.page === null ? b.filename : `${b.filename} S. ${b.page}`;
}

/** Gesperrte Sätze zuerst, dann neueste zuerst; die Eingabe bleibt unverändert. */
export function sortiert(notes: MachineNote[]): MachineNote[] {
  return [...notes].sort((a, b) => Number(b.gesperrt) - Number(a.gesperrt) || b.created_at.localeCompare(a.created_at));
}
