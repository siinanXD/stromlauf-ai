import { describe, expect, it } from "vitest";
import { ausDrop, ausInput, pruefeLimits, verschiebe, wendeAn, type Abgelegt } from "./ordner";

const datei = (name: string, rel?: string, size?: number) => {
  const f = new File([new Uint8Array(0)], name);
  if (rel !== undefined) Object.defineProperty(f, "webkitRelativePath", { value: rel });
  if (size !== undefined) Object.defineProperty(f, "size", { value: size });
  return f;
};
const ab = (pfad: string): Abgelegt => ({ file: datei(pfad.split("/").pop()!), pfad });

describe("ausInput", () => {
  it("entfernt den Wurzelordner aus webkitRelativePath", () => {
    const r = ausInput([datei("01.pdf", "root/fb01/01.pdf"), datei("README.md", "root/README.md"), datei("x.pdf")]);
    expect(r.map((a) => a.pfad)).toEqual(["fb01/01.pdf", "README.md", "x.pdf"]);
  });
});

describe("pruefeLimits", () => {
  it("meldet mehr als 200 Dateien", () => {
    const viele = Array.from({ length: 201 }, (_, i) => ab(`${i}.pdf`));
    expect(pruefeLimits(viele)).toBe("Höchstens 200 Dateien je Ablage (es sind 201).");
  });
  it("meldet mehr als 500 MB", () => {
    const gross = [{ file: datei("a.pdf", undefined, 501_000_000), pfad: "a.pdf" }];
    expect(pruefeLimits(gross)).toBe("Höchstens 500 MB je Ablage (es sind 501 MB).");
  });
  it("rundet MB auf", () => {
    expect(pruefeLimits([{ file: datei("a.pdf", undefined, 500_000_001), pfad: "a.pdf" }])).toBe("Höchstens 500 MB je Ablage (es sind 501 MB).");
  });
  it("meldet doppelte Pfade", () => {
    expect(pruefeLimits([ab("a/1.pdf"), ab("b/1.pdf"), ab("a/1.pdf")])).toBe("Doppelte Pfade in der Ablage: a/1.pdf");
  });
  it("lässt Zulässiges durch", () => {
    expect(pruefeLimits([ab("a.pdf")])).toBeNull();
  });
});

describe("wendeAn und verschiebe", () => {
  const dateien = ["a/1.pdf", "a/2.pdf", "b/3.pdf", "lose.pdf", "x.tmp"].map(ab);
  const vorschlag = {
    gruppen: [
      { name: "A", quelle: "ordner" as const, dateien: ["a/1.pdf", "a/2.pdf"] },
      { name: "B", quelle: "kennung" as const, dateien: ["b/3.pdf"] },
    ],
    unzugeordnet: ["lose.pdf"],
    ignoriert: ["x.tmp"],
  };
  const pfade = (l: Abgelegt[]) => l.map((a) => a.pfad);

  it("übernimmt Gruppen, verwirft Ignoriertes, sammelt Unbekanntes", () => {
    const g = wendeAn({ ...vorschlag, unzugeordnet: [] }, dateien);
    expect(g.gruppen.map((x) => x.id)).toEqual(["g1", "g2"]);
    expect(pfade(g.unzugeordnet)).toEqual(["lose.pdf"]);
    expect(g.gruppen.flatMap((x) => pfade(x.dateien))).not.toContain("x.tmp");
  });
  it("verschiebt in vorhandene Gruppe, neue Gruppe und ohne", () => {
    const g = wendeAn(vorschlag, dateien);
    const g2 = verschiebe(g, "lose.pdf", "g2");
    expect(pfade(g2.gruppen[1].dateien)).toEqual(["b/3.pdf", "lose.pdf"]);
    expect(g.unzugeordnet).toHaveLength(1);
    const g3 = verschiebe(g, "a/1.pdf", "neu");
    expect(g3.gruppen[2]).toMatchObject({ id: "g3", name: "Anlage 3", quelle: "mensch" });
    expect(pfade(g3.gruppen[2].dateien)).toEqual(["a/1.pdf"]);
    const g4 = verschiebe(g, "a/1.pdf", "ohne");
    expect(pfade(g4.unzugeordnet)).toEqual(["lose.pdf", "a/1.pdf"]);
  });
  it("entfernt leere Gruppen, ignoriert Unbekanntes und gleiche Gruppe", () => {
    const g = wendeAn(vorschlag, dateien);
    const leer = verschiebe(g, "b/3.pdf", "ohne");
    expect(leer.gruppen.map((x) => x.name)).toEqual(["A"]);
    expect(verschiebe(g, "nix.pdf", "g1")).toEqual(g);
    expect(verschiebe(g, "a/1.pdf", "g1")).toEqual(g);
  });
});

describe("ausDrop", () => {
  const dateiEntry = (name: string) => ({ isFile: true, isDirectory: false, name, file: (cb: (f: File) => void) => cb(datei(name)) });
  const ordnerEntry = (name: string, batches: unknown[][]) => ({
    isFile: false,
    isDirectory: true,
    name,
    createReader: () => {
      let i = 0;
      return { readEntries: (cb: (e: unknown[]) => void) => cb(batches[i++] ?? []) };
    },
  });
  const items = (...entries: unknown[]) =>
    entries.map((e) => ({ webkitGetAsEntry: () => e })) as unknown as DataTransferItemList;

  it("läuft rekursiv, liest Reader bis zum leeren Stapel, ohne Wurzelnamen", async () => {
    const tief = ordnerEntry("fb01", [[dateiEntry("01.pdf")], [dateiEntry("02.pdf")]]);
    const wurzel = ordnerEntry("root", [[tief, dateiEntry("README.md")]]);
    const r = await ausDrop(items(wurzel));
    expect(r.map((a) => a.pfad).sort()).toEqual(["README.md", "fb01/01.pdf", "fb01/02.pdf"]);
  });
  it("behält Ordnernamen bei mehreren Ordnern", async () => {
    const r = await ausDrop(items(ordnerEntry("fb01", [[dateiEntry("01.pdf")]]), ordnerEntry("ur01", [[dateiEntry("01.pdf")]])));
    expect(r.map((a) => a.pfad).sort()).toEqual(["fb01/01.pdf", "ur01/01.pdf"]);
  });
  it("behält den Namen einer einzelnen Datei", async () => {
    expect((await ausDrop(items(dateiEntry("a.pdf")))).map((a) => a.pfad)).toEqual(["a.pdf"]);
  });
});
