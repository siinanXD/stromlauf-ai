import type { GruppenVorschlag } from "@/lib/api";

/** Eine eingesammelte Datei samt Pfad relativ zum gewählten bzw. abgelegten Wurzelordner. */
export type Abgelegt = { file: File; pfad: string };

export type Gruppierung = {
  gruppen: { id: string; name: string; quelle: "ordner" | "kennung" | "mensch"; dateien: Abgelegt[] }[];
  unzugeordnet: Abgelegt[];
};

const MAX_DATEIEN = 200;
const MAX_MB = 500;

/** Dateien aus <input webkitdirectory>: Pfad ohne den Namen des gewählten Ordners, sonst der Dateiname. */
export function ausInput(files: FileList | File[]): Abgelegt[] {
  return Array.from(files).map((file) => {
    const rel = file.webkitRelativePath;
    return { file, pfad: rel ? rel.split("/").slice(1).join("/") || file.name : file.name };
  });
}

// Nur die benötigten Teile der (nicht standardisierten) FileSystem-Entry-API.
type Eintrag = {
  isFile: boolean;
  isDirectory: boolean;
  name: string;
  file?: (ok: (f: File) => void, fehler?: (e: unknown) => void) => void;
  createReader?: () => { readEntries: (ok: (e: Eintrag[]) => void, fehler?: (e: unknown) => void) => void };
};

const alsDatei = (e: Eintrag) => new Promise<File>((ok, fehler) => e.file!(ok, fehler));

async function kinder(ordner: Eintrag): Promise<Eintrag[]> {
  const reader = ordner.createReader!();
  const alle: Eintrag[] = [];
  for (;;) {
    const stapel = await new Promise<Eintrag[]>((ok, fehler) => reader.readEntries(ok, fehler));
    if (stapel.length === 0) return alle;
    alle.push(...stapel);
  }
}

async function geheDurch(e: Eintrag, praefix: string): Promise<Abgelegt[]> {
  if (e.isFile) return [{ file: await alsDatei(e), pfad: praefix + e.name }];
  if (!e.isDirectory) return [];
  const teile = await Promise.all((await kinder(e)).map((k) => geheDurch(k, `${praefix}${e.name}/`)));
  return teile.flat();
}

/** Drag-and-drop: Ordner rekursiv ablaufen; Pfade relativ zum abgelegten Ordner ohne dessen Namen. */
export async function ausDrop(items: DataTransferItemList): Promise<Abgelegt[]> {
  const eintraege = Array.from(items)
    .map((i) => i.webkitGetAsEntry() as Eintrag | null)
    .filter((e): e is Eintrag => e !== null);
  // Nur bei genau einem abgelegten Ordner entfällt dessen Name; sonst bleibt er erstes Pfadsegment.
  if (eintraege.length === 1 && eintraege[0].isDirectory) {
    const unter = await Promise.all((await kinder(eintraege[0])).map((k) => geheDurch(k, "")));
    return unter.flat();
  }
  const teile = await Promise.all(eintraege.map((e) => geheDurch(e, "")));
  return teile.flat();
}

/** Erste verletzte Regel als Text, sonst null. 1 MB = 1 000 000 Byte. */
export function pruefeLimits(abgelegt: Abgelegt[]): string | null {
  if (abgelegt.length > MAX_DATEIEN) return `Höchstens ${MAX_DATEIEN} Dateien je Ablage (es sind ${abgelegt.length}).`;
  const bytes = abgelegt.reduce((summe, a) => summe + a.file.size, 0);
  if (bytes > MAX_MB * 1_000_000) return `Höchstens ${MAX_MB} MB je Ablage (es sind ${Math.ceil(bytes / 1_000_000)} MB).`;
  const gesehen = new Set<string>();
  for (const a of abgelegt) {
    if (gesehen.has(a.pfad)) return `Doppelte Pfade in der Ablage: ${a.pfad}`;
    gesehen.add(a.pfad);
  }
  return null;
}

/** Backend-Vorschlag (Pfade) auf die echten Dateien abbilden. Ignoriertes entfällt, Unbekanntes landet in "unzugeordnet". */
export function wendeAn(vorschlag: GruppenVorschlag, abgelegt: Abgelegt[]): Gruppierung {
  const nachPfad = new Map(abgelegt.map((a) => [a.pfad, a]));
  const ignoriert = new Set(vorschlag.ignoriert);
  const benutzt = new Set<string>();
  const nimm = (pfade: string[]) =>
    pfade.flatMap((p) => {
      const a = nachPfad.get(p);
      if (!a || ignoriert.has(p) || benutzt.has(p)) return [];
      benutzt.add(p);
      return [a];
    });
  const gruppen = vorschlag.gruppen.map((g, i) => ({ id: `g${i + 1}`, name: g.name, quelle: g.quelle, dateien: nimm(g.dateien) }));
  const unzugeordnet = nimm(vorschlag.unzugeordnet);
  for (const a of abgelegt) if (!benutzt.has(a.pfad) && !ignoriert.has(a.pfad)) unzugeordnet.push(a);
  return { gruppen, unzugeordnet };
}

/** Datei in eine Gruppe, eine neue Gruppe ("neu") oder zu "unzugeordnet" ("ohne") verschieben; gibt ein neues Objekt zurück. */
export function verschiebe(g: Gruppierung, pfad: string, zielId: string | "neu" | "ohne"): Gruppierung {
  const quelle = g.gruppen.find((x) => x.dateien.some((d) => d.pfad === pfad));
  const datei = quelle?.dateien.find((d) => d.pfad === pfad) ?? g.unzugeordnet.find((d) => d.pfad === pfad);
  if (!datei) return g;
  if (zielId === "ohne" ? !quelle : quelle?.id === zielId) return g;
  if (zielId !== "neu" && zielId !== "ohne" && !g.gruppen.some((x) => x.id === zielId)) return g;

  const gruppen = g.gruppen.map((x) => ({ ...x, dateien: x.dateien.filter((d) => d.pfad !== pfad) }));
  let unzugeordnet = g.unzugeordnet.filter((d) => d.pfad !== pfad);
  if (zielId === "ohne") unzugeordnet = [...unzugeordnet, datei];
  else if (zielId === "neu") {
    let n = gruppen.length + 1;
    while (g.gruppen.some((x) => x.id === `g${n}`)) n++;
    gruppen.push({ id: `g${n}`, name: `Anlage ${g.gruppen.length + 1}`, quelle: "mensch", dateien: [datei] });
  } else gruppen.find((x) => x.id === zielId)!.dateien.push(datei);
  return { gruppen: gruppen.filter((x) => x.dateien.length > 0), unzugeordnet };
}

/** "Alle starten" ist erst frei, wenn nichts mehr unzugeordnet ist und jede Anlage einen Namen hat. */
export function kannStarten(g: Gruppierung): boolean {
  return g.gruppen.length > 0 && g.unzugeordnet.length === 0 && g.gruppen.every((x) => x.name.trim() !== "");
}

/** Vorschlag ohne die bereits gestarteten Gruppen. */
export function ohneGestartete(g: Gruppierung, ids: string[]): Gruppierung {
  return { ...g, gruppen: g.gruppen.filter((x) => !ids.includes(x.id)) };
}
