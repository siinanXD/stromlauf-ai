/**
 * Ansicht der Maschinenseite aus der URL und zurueck: Bereich (Stoerfaelle oder Aufbau), Aufbau-Tab, offener
 * Stoerfall (?fall=) und offenes Detail (?detail=). Rein, damit Routing und Zurueck-Geste testbar sind.
 */
import { detailFromParam, detailToParam, type DetailRef } from "@/lib/detail";

export type Area = "stoerfaelle" | "aufbau";

export type AufbauTab = "schema" | "schaltschrank" | "signalweg" | "dokumente" | "ablauf" | "fehler" | "kennzahlen";

/** Haupt-Tabs des Bereichs Aufbau; "Mehr" buendelt die Nebenansichten. */
export const MAIN_TABS: { id: AufbauTab; label: string }[] = [
  { id: "schema", label: "Modell" },
  { id: "schaltschrank", label: "Schaltschrank" },
  { id: "signalweg", label: "Signalweg" },
  { id: "dokumente", label: "Dokumente" },
];
export const MORE_TABS: { id: AufbauTab; label: string }[] = [
  { id: "fehler", label: "Fehlerliste" },
  { id: "kennzahlen", label: "Kennzahlen" },
  { id: "ablauf", label: "Ablauf" },
];
const TAB_IDS = new Set<string>([...MAIN_TABS, ...MORE_TABS].map((t) => t.id));

export function isAufbauTab(value: string | null | undefined): value is AufbauTab {
  return Boolean(value && TAB_IDS.has(value));
}

export interface MachineView {
  area: Area;
  /** Nur im Aufbau; null = Standard (Modell, oder die beste Ansicht fuer ?tag=). */
  tab: AufbauTab | null;
  /** Kennzeichen aus Suche oder Befundkarte (?tag=), nur im Aufbau. */
  tag: string | null;
  /** Offener Stoerfall (Konversations-ID oder vorlaeufige ID). */
  fall: string | null;
  detail: DetailRef | null;
}

/** Ebene am Handy: immer nur eine sichtbar, die URL haelt sie fest. */
export type Level = "list" | "chat" | "detail";

interface ParamReader {
  get(name: string): string | null;
}

/**
 * Regeln:
 * - ?bereich=aufbau&tab=… oeffnet den Aufbau mit dem Tab; ?bereich=stoerfaelle oder nichts die Stoerfaelle.
 * - Alter Link ?tab=… ohne bereich oeffnet den Aufbau mit diesem Tab (auch ?tab=signalweg aus der Befundkarte).
 * - ?tab=chat war der fruehere Chat-Tab und fuehrt zu den Stoerfaellen.
 * - ?tag=… ohne bereich ("im Werk zeigen") oeffnet den Aufbau und markiert das Bauteil.
 */
export function viewFromParams(params: ParamReader): MachineView {
  const bereich = params.get("bereich");
  const rawTab = params.get("tab");
  const tag = params.get("tag") || null;
  const tab = isAufbauTab(rawTab) ? rawTab : null;
  let area: Area;
  if (bereich === "aufbau") area = "aufbau";
  else if (bereich === "stoerfaelle") area = "stoerfaelle";
  else if (rawTab === "chat") area = "stoerfaelle";
  else if (tab || tag) area = "aufbau";
  else area = "stoerfaelle";
  return {
    area,
    tab: area === "aufbau" ? tab : null,
    tag: area === "aufbau" ? tag : null,
    fall: area === "stoerfaelle" ? params.get("fall") || null : null,
    detail: area === "stoerfaelle" ? detailFromParam(params.get("detail")) : null,
  };
}

/** Query-String ("?…" oder "") zur Ansicht; der Standardbereich Stoerfaelle steht nicht in der URL. */
export function viewToQuery(view: MachineView): string {
  const params = new URLSearchParams();
  if (view.area === "aufbau") {
    params.set("bereich", "aufbau");
    if (view.tab) params.set("tab", view.tab);
    if (view.tag) params.set("tag", view.tag);
  } else {
    if (view.fall) params.set("fall", view.fall);
    if (view.detail) params.set("detail", detailToParam(view.detail));
  }
  const query = params.toString();
  return query ? `?${query}` : "";
}

export function levelOf(view: MachineView): Level {
  if (view.detail) return "detail";
  if (view.fall) return "chat";
  return "list";
}

/** Eine Ebene zurueck: Detail -> Stoerfall -> Liste; der Aufbau fuehrt zu den Stoerfaellen. */
export function parentView(view: MachineView): MachineView {
  if (view.area === "aufbau") return STOERFAELLE;
  if (view.detail) return { ...view, detail: null };
  return { ...view, fall: null };
}

export const STOERFAELLE: MachineView = { area: "stoerfaelle", tab: null, tag: null, fall: null, detail: null };
