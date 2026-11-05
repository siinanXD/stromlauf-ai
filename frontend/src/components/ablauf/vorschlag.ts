import { ablauf, api } from "@/lib/api";

import type { Gruppierung } from "./ordner";

/** Vorgeschlagene Anlage (`gruppeId` aus der Gruppierung) und Ähnlichkeit 0 bis 1. */
export type Vorschlag = { gruppeId: string; wert: number };

/** Vorschläge je Dateipfad; Dateien ohne Vorschlag fehlen. */
export type Vorschlaege = Record<string, Vorschlag>;

const POLL_MS = 2000;
/** 300 Abfragen im Abstand von 2 s: nach rund 10 Minuten geben wir auf und die Seite fragt wie bisher nach. */
const MAX_ABFRAGEN = 300;

export type VorschlagOptionen = {
  /** Meldet jede angelegte Vorschau-Quelle sofort, damit sie auch bei Abbruch oder Fehler aufgeräumt wird. */
  merke: (sourceId: string) => void;
  abgebrochen: () => boolean;
  warte?: (ms: number) => Promise<void>;
  maxAbfragen?: number;
};

const schlafe = (ms: number) => new Promise<void>((ok) => setTimeout(ok, ms));

/** `0,83` statt `0.83`. */
export const formatWert = (wert: number) =>
  wert.toLocaleString("de-DE", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

/** Räumt Vorschau-Quellen samt Dateien weg; ein Fehlschlag bleibt sichtbar (Konsole), blockiert aber nichts. */
export function loescheQuellen(ids: string[]): Promise<unknown> {
  return Promise.all(
    ids.map((id) =>
      api
        .deleteSource(id)
        .catch((err) =>
          console.warn(`Vorschau-Quelle ${id} nicht gelöscht:`, err),
        ),
    ),
  );
}

/**
 * Liest die unzugeordneten Dateien und je Anlage deren Dateien (POST /api/runs/lesen, je eine Vorschau-Quelle),
 * wartet, bis alles gelesen ist, und fragt erst dann POST /api/runs/aehnlichkeit. Wirft bei jedem Fehler;
 * die Seite fragt dann ohne Vorschlag nach.
 */
export async function ermittleVorschlaege(
  g: Gruppierung,
  opt: VorschlagOptionen,
): Promise<Vorschlaege> {
  if (g.unzugeordnet.length === 0 || g.gruppen.length === 0) return {};
  const lese = async (dateien: Gruppierung["unzugeordnet"]) => {
    const antwort = await ablauf.lesen(dateien);
    opt.merke(antwort.source_id);
    return antwort;
  };
  // allSettled statt all: auch die übrigen Uploads sollen ihre Quelle melden, bevor wir abbrechen.
  const ergebnisse = await Promise.allSettled([
    lese(g.unzugeordnet),
    ...g.gruppen.map((x) => lese(x.dateien)),
  ]);
  const fehler = ergebnisse.find(
    (e): e is PromiseRejectedResult => e.status === "rejected",
  );
  if (fehler) throw fehler.reason;
  const [lose, ...je] = ergebnisse.map(
    (e) =>
      (e as PromiseFulfilledResult<Awaited<ReturnType<typeof lese>>>).value,
  );

  const warte = opt.warte ?? schlafe;
  const quellen = [lose, ...je].map((a) => a.source_id);
  for (let n = 0; ; n++) {
    if (opt.abgebrochen()) return {};
    const stand = (
      await Promise.all(quellen.map((id) => api.listDocuments(id)))
    ).flat();
    if (stand.every((d) => d.status === "ready" || d.status === "failed"))
      break;
    if (n >= (opt.maxAbfragen ?? MAX_ABFRAGEN))
      throw new Error("Das Lesen dauert zu lange.");
    await warte(POLL_MS);
  }
  if (opt.abgebrochen()) return {};

  const antwort = await ablauf.aehnlichkeit(
    g.gruppen.map((x, i) => ({ name: x.name, source_ids: [je[i].source_id] })),
    lose.dateien,
  );
  const idJeName = new Map(g.gruppen.map((x) => [x.name, x.id]));
  const vorschlaege: Vorschlaege = {};
  for (const a of antwort) {
    const gruppeId =
      a.vorschlag === null ? undefined : idJeName.get(a.vorschlag);
    if (gruppeId !== undefined)
      vorschlaege[a.pfad] = { gruppeId, wert: a.wert };
  }
  return vorschlaege;
}
