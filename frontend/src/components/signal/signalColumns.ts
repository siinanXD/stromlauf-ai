import type { SignalColumn, SignalMainData, SignalMainNode, SignalNodeKind } from "@/lib/api";

/** Feste Spalten der Hauptweg-Sicht von links nach rechts (Vertrag Signalweg-API). */
export const COLUMN_ORDER: readonly SignalColumn[] = [
  "feld",
  "klemme_vor",
  "sps_eingang",
  "programm",
  "sps_ausgang",
  "klemme_nach",
  "schaltgeraet",
  "verbraucher",
];

export const COLUMN_LABELS: Record<SignalColumn, string> = {
  feld: "Feld",
  klemme_vor: "Klemme",
  sps_eingang: "SPS-Eingang",
  programm: "Programm",
  sps_ausgang: "SPS-Ausgang",
  klemme_nach: "Klemme",
  schaltgeraet: "Schaltgerät",
  verbraucher: "Verbraucher",
};

export const KIND_LABELS: Record<SignalNodeKind, string> = {
  device: "Betriebsmittel",
  pin: "Anschluss",
  terminal: "Klemme",
  address: "SPS-Adresse",
  network: "Netzwerk",
  variable: "Variable",
};

/** Kurzname eines Knotens: Netzwerke heissen wie ihr Baustein ("FC 1 NW 3"), Variablen ohne Baustein-Praefix. */
export function nodeTitle(node: Pick<SignalMainNode, "id" | "kind" | "ref">): string {
  if (node.kind === "network") return node.ref || node.id;
  if (node.kind === "variable") return node.id.split("#").pop() ?? node.id;
  return node.id;
}

const SHEET_REF = /^\/(\d+)\.(\d+)$/;

/** "/3.5" -> "Blatt 3, Spalte 5"; andere Verweise haben kein Blatt. */
export function sheetText(ref: string): string | null {
  const match = SHEET_REF.exec(ref.trim());
  return match ? `Blatt ${match[1]}, Spalte ${match[2]}` : null;
}

export function isSheetRef(ref: string): boolean {
  return SHEET_REF.test(ref.trim());
}

/** Hauptwegknoten in Wegfolge. */
export function mainPath(data: Pick<SignalMainData, "nodes">): SignalMainNode[] {
  return data.nodes
    .filter((node) => node.main)
    .sort((a, b) => (a.order ?? Number.MAX_SAFE_INTEGER) - (b.order ?? Number.MAX_SAFE_INTEGER) || a.id.localeCompare(b.id));
}

/** Belegte Spalten in Vertragsreihenfolge; Spalten ohne Hauptwegknoten fallen weg. */
export function visibleColumns(data: Pick<SignalMainData, "nodes">): SignalColumn[] {
  const used = new Set(data.nodes.filter((node) => node.main && node.column).map((node) => node.column));
  return COLUMN_ORDER.filter((column) => used.has(column));
}

export interface GridPosition {
  /** Index der Spalte unter den belegten. */
  x: number;
  /** Zeile in der Spalte, ab 0. */
  y: number;
}

/** Naechste freie Zeile zum Wunschwert; bei gleichem Abstand gewinnt die untere. */
function nearestFree(used: Set<number>, desired: number): number {
  const start = Math.max(0, Math.round(desired));
  for (let distance = 0; ; distance += 1) {
    if (!used.has(start + distance)) return start + distance;
    if (start - distance >= 0 && !used.has(start - distance)) return start - distance;
  }
}

/**
 * Lage jedes Knotens im Raster. Die Spalte bestimmt x; Abzweige stehen in der Spalte ihres Hauptwegknotens.
 * y ist das Baryzentrum der schon gesetzten Nachbarn, auf die naechste freie Zeile der Spalte gerundet. Gesetzt
 * werden erst die Hauptwegknoten in Wegfolge, dann die Abzweige nach ihrem Hauptwegknoten und ihrer ID, damit
 * dieselben Daten immer dasselbe Bild ergeben.
 */
export function orderInColumns(data: SignalMainData): Map<string, GridPosition> {
  const columnIndex = new Map(visibleColumns(data).map((column, index) => [column, index]));
  const neighbors = new Map<string, string[]>();
  for (const edge of data.edges) {
    neighbors.set(edge.source, [...(neighbors.get(edge.source) ?? []), edge.target]);
    neighbors.set(edge.target, [...(neighbors.get(edge.target) ?? []), edge.source]);
  }
  const positions = new Map<string, GridPosition>();
  const rows = new Map<number, Set<number>>();

  const place = (id: string, x: number) => {
    const ys = (neighbors.get(id) ?? []).flatMap((other) => {
      const at = positions.get(other);
      return at ? [at.y] : [];
    });
    const desired = ys.length ? ys.reduce((sum, y) => sum + y, 0) / ys.length : 0;
    const used = rows.get(x) ?? new Set<number>();
    const y = nearestFree(used, desired);
    used.add(y);
    rows.set(x, used);
    positions.set(id, { x, y });
  };

  const path = mainPath(data);
  let previousX = 0;
  for (const node of path) {
    // Ohne Spalte (Vertrag verletzt) bleibt der Knoten in der Spalte seines Vorgaengers
    const x = (node.column ? columnIndex.get(node.column) : undefined) ?? previousX;
    place(node.id, x);
    previousX = x;
  }

  const order = new Map(path.map((node, index) => [node.id, index]));
  const branches = data.nodes
    .filter((node) => !node.main && !positions.has(node.id))
    .sort(
      (a, b) =>
        (order.get(a.parent ?? "") ?? Number.MAX_SAFE_INTEGER) - (order.get(b.parent ?? "") ?? Number.MAX_SAFE_INTEGER) ||
        a.id.localeCompare(b.id),
    );
  for (const node of branches) place(node.id, positions.get(node.parent ?? "")?.x ?? 0);
  return positions;
}
