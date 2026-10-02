import { MACHINE_TYPE_LABELS, type MachineListItem } from "./api";

/** Volltextfilter der Maschinenübersicht: Name, Linie, Halle, Typ, Wissensquelle; Wörter UND-verknüpft. */
export function filterMachines(machines: MachineListItem[], query: string): MachineListItem[] {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean);
  if (words.length === 0) return machines;
  return machines.filter((m) => {
    const haystack = [m.name, m.line, m.hall_name, MACHINE_TYPE_LABELS[m.machine_type] ?? m.machine_type, m.source_name ?? ""]
      .join(" ")
      .toLowerCase();
    return words.every((word) => haystack.includes(word));
  });
}

export interface MachineSummary {
  total: number;
  /** Ohne Wissensquelle oder ohne fertig verarbeitetes Dokument */
  withoutDocs: number;
  faults: number;
}

export function summarizeMachines(machines: MachineListItem[]): MachineSummary {
  return {
    total: machines.length,
    withoutDocs: machines.filter((m) => m.ready_document_count === 0).length,
    faults: machines.reduce((sum, m) => sum + m.fault_count, 0),
  };
}

/** Kurztext zur Doku-Spalte: "6 Dokumente", "2 von 6 fertig", "keine". */
export function docsLabel(m: MachineListItem): string {
  if (!m.source_id || m.document_count === 0) return "keine";
  if (m.ready_document_count < m.document_count) return `${m.ready_document_count} von ${m.document_count} fertig`;
  return `${m.document_count} Dokument${m.document_count === 1 ? "" : "e"}`;
}
