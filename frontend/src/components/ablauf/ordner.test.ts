import { describe, expect, it } from "vitest";
import { ausDrop, ausInput, kannStarten, ohneGestartete, pruefeLimits, startHindernis, verschiebe, wendeAn, type Abgelegt } from "./ordner";

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

describe("ausInput bei einem einzelnen Ordner", () => {
  it("behält den Ordnernamen, wenn nur Dateien direkt darin liegen", () => {
    const r = ausInput([datei("Schaltplan.pdf", "Förderband FB-01/Schaltplan.pdf"), datei("Liste.xlsx", "Förderband FB-01/Liste.xlsx")]);
    expect(r.map((a) => a.pfad)).toEqual(["Förderband FB-01/Schaltplan.pdf", "Förderband FB-01/Liste.xlsx"]);
  });
  it("entfernt den Ordnernamen, wenn Unterordner darunter liegen", () => {
    const r = ausInput([datei("a.pdf", "root/x/a.pdf"), datei("b.pdf", "root/b.pdf")]);
    expect(r.map((a) => a.pfad)).toEqual(["x/a.pdf", "b.pdf"]);
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
  it("behält den Namen eines einzelnen Ordners ohne Unterordner", async () => {
    const r = await ausDrop(items(ordnerEntry("Förderband FB-01", [[dateiEntry("Schaltplan.pdf"), dateiEntry("Liste.xlsx")]])));
    expect(r.map((a) => a.pfad).sort()).toEqual(["Förderband FB-01/Liste.xlsx", "Förderband FB-01/Schaltplan.pdf"]);
  });
  it("behält den Namen einer einzelnen Datei", async () => {
    expect((await ausDrop(items(dateiEntry("a.pdf")))).map((a) => a.pfad)).toEqual(["a.pdf"]);
  });
});

describe("wendeAn ohne erkannte Gruppen", () => {
  it("fasst lose Dateien ohne Kennung zu einer Anlage zusammen", () => {
    const g = wendeAn({ gruppen: [], unzugeordnet: ["a.pdf", "b.pdf"], ignoriert: [] }, [ab("a.pdf"), ab("b.pdf")]);
    expect(g.gruppen).toHaveLength(1);
    expect(g.gruppen[0]).toMatchObject({ name: "Anlage 1", quelle: "mensch" });
    expect(g.gruppen[0].dateien.map((a) => a.pfad)).toEqual(["a.pdf", "b.pdf"]);
    expect(g.unzugeordnet).toEqual([]);
    expect(kannStarten(g)).toBe(true);
  });
  it("lässt Gemischtes unverändert", () => {
    const g = wendeAn({ gruppen: [{ name: "A", quelle: "ordner", dateien: ["a/1.pdf"] }], unzugeordnet: ["b.pdf"], ignoriert: [] }, [ab("a/1.pdf"), ab("b.pdf")]);
    expect(g.unzugeordnet).toHaveLength(1);
  });
});

describe("kannStarten", () => {
  const d = { file: new File(["x"], "a.pdf"), pfad: "a.pdf" };
  const gruppe = { id: "g1", name: "FB-01", quelle: "ordner" as const, dateien: [d] };
  it("braucht mindestens eine Gruppe", () => {
    expect(kannStarten({ gruppen: [], unzugeordnet: [] })).toBe(false);
  });
  it("sperrt bei Unzugeordnetem", () => {
    expect(kannStarten({ gruppen: [gruppe], unzugeordnet: [d] })).toBe(false);
  });
  it("sperrt bei leerem Namen", () => {
    expect(kannStarten({ gruppen: [{ ...gruppe, name: "  " }], unzugeordnet: [] })).toBe(false);
  });
  it("sperrt bei mehr als 100 Dateien in einer Anlage und nennt den Grund", () => {
    const viele = Array.from({ length: 101 }, (_, i) => ab(`${i}.pdf`));
    const g = { gruppen: [{ ...gruppe, dateien: viele }], unzugeordnet: [] };
    expect(kannStarten(g)).toBe(false);
    expect(startHindernis(g)).toBe("FB-01: 101 Dateien, höchstens 100 je Anlage.");
    expect(kannStarten({ gruppen: [{ ...gruppe, dateien: viele.slice(0, 100) }], unzugeordnet: [] })).toBe(true);
  });
  it("erlaubt vollständig zugeordnete benannte Gruppen", () => {
    expect(kannStarten({ gruppen: [gruppe], unzugeordnet: [] })).toBe(true);
  });
});

describe("ohneGestartete", () => {
  it("entfernt nur die gestarteten Gruppen", () => {
    const g = (id: string) => ({ id, name: id, quelle: "ordner" as const, dateien: [] });
    const r = ohneGestartete({ gruppen: [g("g1"), g("g2")], unzugeordnet: [] }, ["g1"]);
    expect(r.gruppen.map((x) => x.id)).toEqual(["g2"]);
  });
});
