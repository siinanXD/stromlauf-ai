/** Testdaten der Hauptweg-Sicht (nur fuer Vitest), angelehnt an FB-01: Taster bis Motor ueber die SPS. */
import type { SignalColumn, SignalMainData, SignalMainEdge, SignalMainNode, SignalVia } from "@/lib/api";

export function mainNode(id: string, kind: SignalMainNode["kind"], column: SignalColumn, order: number, extra: Partial<SignalMainNode> = {}): SignalMainNode {
  return { id, kind, label: "", ref: "", detail: "", main: true, column, order, branches: 0, parent: null, ...extra };
}

export function branchNode(id: string, kind: SignalMainNode["kind"], parent: string, extra: Partial<SignalMainNode> = {}): SignalMainNode {
  return { id, kind, label: "", ref: "", detail: "", main: false, column: null, order: null, branches: 0, parent, ...extra };
}

export function mainEdge(
  source: string,
  target: string,
  via: SignalVia[] = ["klemmenplan"],
  pins: SignalMainEdge["pins"] = { from: null, to: null },
  directed = true,
): SignalMainEdge {
  return { source, target, via, directed, pins };
}

/** Acht Hauptwegknoten, Start -K1 an Position 6, zwei Abzweige an -K1. */
export function conveyor(): SignalMainData {
  return {
    start: "-K1",
    view: "main",
    columns: ["feld", "klemme_vor", "sps_eingang", "programm", "sps_ausgang", "klemme_nach", "schaltgeraet", "verbraucher"],
    nodes: [
      mainNode("-S1", "device", "feld", 0, { label: "Taster Band ein", ref: "/2.1" }),
      mainNode("-X1:3", "terminal", "klemme_vor", 1, { ref: "/2.3" }),
      mainNode("E0.3", "address", "sps_eingang", 2, { label: "Band ein" }),
      mainNode("FC 1/NW2", "network", "programm", 3, { label: "Band schalten", ref: "FC 1 NW 2", detail: "U E 0.3\n= A 4.0" }),
      mainNode("A4.0", "address", "sps_ausgang", 4),
      mainNode("-X3:9", "terminal", "klemme_nach", 5, { ref: "/3.4" }),
      mainNode("-K1", "device", "schaltgeraet", 6, { label: "Schütz Förderband", ref: "/3.5", branches: 2 }),
      mainNode("-M1", "device", "verbraucher", 7, { label: "Motor Förderband", ref: "/4.2" }),
      branchNode("-H1", "device", "-K1", { label: "Meldeleuchte Band läuft" }),
      branchNode("-X3:10", "terminal", "-K1"),
    ],
    edges: [
      mainEdge("-S1", "-X1:3", ["leitung"], { from: "13", to: null }),
      mainEdge("-X1:3", "E0.3"),
      mainEdge("E0.3", "FC 1/NW2", ["awl"]),
      mainEdge("FC 1/NW2", "A4.0", ["awl"]),
      mainEdge("A4.0", "-X3:9", ["symboltabelle", "leitung"]),
      mainEdge("-X3:9", "-K1", ["klemmenplan"], { from: null, to: "A1" }),
      mainEdge("-K1", "-M1", ["lage"], { from: "2", to: null }),
      mainEdge("-K1", "-H1", ["leitung"], { from: "14", to: null }),
      mainEdge("-X3:10", "-K1", ["modell"], { from: null, to: null }, false),
    ],
    schematic: { document_id: "doc-1", filename: "01_Stromlaufplan.pdf" },
  };
}
