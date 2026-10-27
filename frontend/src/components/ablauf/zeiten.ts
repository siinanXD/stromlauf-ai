import type { Zeiten, ZeitenKennzahl } from "@/lib/api";

export interface ZeitZeile {
  key: string;
  label: string;
  kennzahl: ZeitenKennzahl;
}

const SCHRITTE: [string, string][] = [
  ["hochladen", "Hochladen"],
  ["lesen", "Lesen"],
  ["maschine", "Maschine anlegen"],
  ["steckbrief", "Steckbrief"],
  ["modell", "Maschinenmodell"],
  ["zusammenfassung", "Zusammenfassung"],
  ["fertig", "Fertig"],
];

/** Sieben Schritte in Ablaufreihenfolge, dann Gesamtdauer und Dauer je Frage. */
export function zeilen(z: Zeiten): ZeitZeile[] {
  return [
    ...SCHRITTE.map(([key, label]) => ({ key, label, kennzahl: z.schritte[key] })),
    { key: "gesamt", label: "Gesamt je Lauf", kennzahl: z.gesamt },
    { key: "fragen", label: "Je Frage (Schritt 6)", kennzahl: z.fragen },
  ];
}

export const sekunden = (x: number | null): string => (x === null ? "–" : `${x.toFixed(1).replace(".", ",")} s`);

export const zellenKlasse = (ueberZiel: boolean): string => (ueberZiel ? "bg-error-soft text-error" : "");

/** Ein Satz über dem Schritt mit dem höchsten Median (bei Gleichstand der erste). */
export function satz(z: Zeiten): string {
  if (z.laeufe === 0) return "Noch keine Läufe";
  let langsamster: ZeitZeile | null = null;
  for (const zeile of zeilen(z).slice(0, SCHRITTE.length)) {
    const median = zeile.kennzahl.median_s;
    if (median !== null && (langsamster === null || median > (langsamster.kennzahl.median_s ?? 0))) langsamster = zeile;
  }
  if (!langsamster) return `Noch keine Zeiten aus den letzten ${z.laeufe} Läufen`;
  return `Langsamster Schritt der letzten ${z.laeufe} Läufe: ${langsamster.label}, im Median ${sekunden(langsamster.kennzahl.median_s)}`;
}
