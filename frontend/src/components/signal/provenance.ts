import type { SignalMainData, SignalMainEdge, SignalVia } from "@/lib/api";

/**
 * Drei Herkunftsstufen einer Verbindung, von belegt bis vermutet. Sie unterscheiden sich in der Strichart, nicht
 * nur in der Farbe (ISA-101): durchgezogen, lang gestrichelt, gepunktet.
 */
export type Provenance = "beleg" | "leitung" | "lage";

export const PROVENANCE_ORDER: readonly Provenance[] = ["beleg", "leitung", "lage"];

export const PROVENANCE_LABELS: Record<Provenance, string> = {
  beleg: "Tabelle oder Programm",
  leitung: "Leitung im Plan",
  lage: "Lage im Plan oder Modell",
};

/** SVG-Strichmuster je Stufe; gepunktet braucht runde Linienenden. */
export const PROVENANCE_DASH: Record<Provenance, string | undefined> = {
  beleg: undefined,
  leitung: "9 5",
  lage: "0.5 5",
};

export const PROVENANCE_CAP: Record<Provenance, "butt" | "round"> = { beleg: "butt", leitung: "butt", lage: "round" };

export const VIA_LABELS: Record<SignalVia, string> = {
  klemmenplan: "Klemmenplan",
  awl: "SPS-Programm",
  symboltabelle: "Symboltabelle",
  stueckliste: "Stückliste",
  leitung: "Leitung im Plan",
  lage: "Lage im Plan",
  modell: "Modell",
};

const PROVEN: ReadonlySet<SignalVia> = new Set(["klemmenplan", "awl", "symboltabelle", "stueckliste"]);

/** Die staerkste Herkunft gewinnt: eine Tabelle belegt auch eine Kante, die der Plan zusaetzlich zeigt. */
export function provenanceOf(via: readonly SignalVia[] | undefined): Provenance {
  const list = via ?? [];
  if (list.some((v) => PROVEN.has(v))) return "beleg";
  if (list.includes("leitung")) return "leitung";
  return "lage";
}

/** "Klemmenplan, SPS-Programm"; ohne Angabe "Herkunft unbekannt". */
export function viaText(via: readonly SignalVia[] | undefined): string {
  const list = via ?? [];
  return list.length ? list.map((v) => VIA_LABELS[v] ?? v).join(", ") : "Herkunft unbekannt";
}

/** Anschlussnummern an der Kante: "von 14 an A1", "an A1", "von 2" oder "". */
export function pinText(pins: SignalMainEdge["pins"] | undefined): string {
  if (!pins) return "";
  return [pins.from ? `von ${pins.from}` : "", pins.to ? `an ${pins.to}` : ""].filter(Boolean).join(" ");
}

/** Herkunft und Anschluesse einer Kante als ein Satzteil: "Klemmenplan · an A1". */
export function edgeText(edge: SignalMainEdge): string {
  return [viaText(edge.via), pinText(edge.pins)].filter(Boolean).join(" · ");
}

/**
 * Schalter "nur Belegtes": nur Kanten aus Tabelle oder Programm bleiben, dazu die Knoten an ihnen und der Start.
 * Was nur der Plan oder ein Modell zeigt, verschwindet, auch vom Hauptweg.
 */
export function onlyProven(data: SignalMainData): SignalMainData {
  const edges = data.edges.filter((edge) => provenanceOf(edge.via) === "beleg");
  const keep = new Set([data.start, ...edges.flatMap((edge) => [edge.source, edge.target])]);
  return { ...data, edges, nodes: data.nodes.filter((node) => keep.has(node.id)) };
}
