import { beforeEach, describe, expect, it, vi } from "vitest";

import { ablauf, api, type SourceDocument } from "@/lib/api";

import type { Abgelegt, Gruppierung } from "./ordner";
import { ermittleVorschlaege, formatWert, loescheQuellen } from "./vorschlag";

vi.mock("@/lib/api", () => ({
  ablauf: { lesen: vi.fn(), aehnlichkeit: vi.fn() },
  api: { listDocuments: vi.fn(), deleteSource: vi.fn() },
}));

const lesen = vi.mocked(ablauf.lesen);
const aehnlichkeit = vi.mocked(ablauf.aehnlichkeit);
const listDocuments = vi.mocked(api.listDocuments);
const deleteSource = vi.mocked(api.deleteSource);

const ab = (pfad: string): Abgelegt => ({ file: new File([new Uint8Array(0)], pfad.split("/").pop()!), pfad });
const g: Gruppierung = {
  gruppen: [
    { id: "g1", name: "FB-01", quelle: "kennung", dateien: [ab("FB-01_Plan.pdf")] },
    { id: "g2", name: "UR-01", quelle: "kennung", dateien: [ab("UR-01_Plan.pdf")] },
  ],
  unzugeordnet: [ab("Lose.pdf")],
};
const docs = (status: SourceDocument["status"]) => [{ status }] as SourceDocument[];
const opt = () => ({ merke: vi.fn(), abgebrochen: () => false, warte: async () => {} });

beforeEach(() => {
  vi.resetAllMocks();
  lesen.mockImplementation(async (dateien) => ({
    source_id: `q-${dateien[0].pfad}`,
    dateien: dateien.map((d) => ({ pfad: d.pfad, document_id: `d-${d.pfad}` })),
  }));
  listDocuments.mockResolvedValue(docs("ready"));
  deleteSource.mockResolvedValue(undefined);
});

describe("ermittleVorschlaege", () => {
  it("liest die Unzugeordneten und jede Anlage, vergleicht erst danach und bildet Namen auf Gruppen-IDs ab", async () => {
    // erster Stand: noch nicht gelesen; Ähnlichkeit darf da nicht gefragt werden
    listDocuments.mockResolvedValueOnce(docs("processing")).mockResolvedValue(docs("ready"));
    aehnlichkeit.mockResolvedValue([{ pfad: "Lose.pdf", vorschlag: "UR-01", wert: 0.83, herkunft: "aehnlichkeit" }]);
    const o = opt();
    const warte = vi.fn(async () => expect(aehnlichkeit).not.toHaveBeenCalled());
    const r = await ermittleVorschlaege(g, { ...o, warte });
    expect(r).toEqual({ "Lose.pdf": { gruppeId: "g2", wert: 0.83 } });
    expect(warte).toHaveBeenCalledTimes(1);
    expect(lesen).toHaveBeenCalledTimes(3);
    expect(o.merke.mock.calls.map((c) => c[0]).sort()).toEqual(["q-FB-01_Plan.pdf", "q-Lose.pdf", "q-UR-01_Plan.pdf"]);
    expect(aehnlichkeit).toHaveBeenCalledWith(
      [
        { name: "FB-01", source_ids: ["q-FB-01_Plan.pdf"] },
        { name: "UR-01", source_ids: ["q-UR-01_Plan.pdf"] },
      ],
      [{ pfad: "Lose.pdf", document_id: "d-Lose.pdf" }],
    );
  });

  it("lässt eine Datei ohne Vorschlag (null) aus, damit die Seite nachfragt", async () => {
    aehnlichkeit.mockResolvedValue([{ pfad: "Lose.pdf", vorschlag: null, wert: 0.4, herkunft: "aehnlichkeit" }]);
    expect(await ermittleVorschlaege(g, opt())).toEqual({});
  });

  it("fragt nichts, wenn nichts unzugeordnet ist", async () => {
    expect(await ermittleVorschlaege({ ...g, unzugeordnet: [] }, opt())).toEqual({});
    expect(lesen).not.toHaveBeenCalled();
  });

  it("wirft bei einem Lesefehler, meldet aber die schon angelegten Quellen zum Aufräumen", async () => {
    lesen.mockImplementation(async (dateien) => {
      if (dateien[0].pfad === "UR-01_Plan.pdf") throw new Error("Dateityp .xyz nicht unterstuetzt");
      return { source_id: `q-${dateien[0].pfad}`, dateien: [] };
    });
    const o = opt();
    await expect(ermittleVorschlaege(g, o)).rejects.toThrow("nicht unterstuetzt");
    expect(o.merke).toHaveBeenCalledTimes(2);
    expect(aehnlichkeit).not.toHaveBeenCalled();
  });

  it("wirft, wenn die Abfrage des Lesestands scheitert", async () => {
    listDocuments.mockRejectedValue(new Error("502"));
    await expect(ermittleVorschlaege(g, opt())).rejects.toThrow("502");
    expect(aehnlichkeit).not.toHaveBeenCalled();
  });

  it("wirft, wenn die Ähnlichkeitsroute scheitert", async () => {
    aehnlichkeit.mockRejectedValue(new Error("Gruppennamen müssen verschieden sein"));
    await expect(ermittleVorschlaege(g, opt())).rejects.toThrow("verschieden");
  });

  it("gibt nach zu vielen Abfragen auf", async () => {
    listDocuments.mockResolvedValue(docs("processing"));
    await expect(ermittleVorschlaege(g, { ...opt(), maxAbfragen: 2 })).rejects.toThrow("dauert zu lange");
    expect(aehnlichkeit).not.toHaveBeenCalled();
  });

  it("zählt ein fehlgeschlagenes Dokument als gelesen (es hat dann keinen Vorschlag)", async () => {
    listDocuments.mockResolvedValue(docs("failed"));
    aehnlichkeit.mockResolvedValue([{ pfad: "Lose.pdf", vorschlag: null, wert: 0, herkunft: "aehnlichkeit" }]);
    expect(await ermittleVorschlaege(g, opt())).toEqual({});
    expect(aehnlichkeit).toHaveBeenCalledTimes(1);
  });

  it("fragt nach einem Abbruch (neue Ablage, Start) nicht mehr", async () => {
    listDocuments.mockResolvedValue(docs("processing"));
    let abgebrochen = false;
    const warte = async () => {
      abgebrochen = true;
    };
    expect(await ermittleVorschlaege(g, { merke: vi.fn(), abgebrochen: () => abgebrochen, warte })).toEqual({});
    expect(aehnlichkeit).not.toHaveBeenCalled();
  });
});

describe("loescheQuellen", () => {
  it("ruft DELETE je Vorschau-Quelle auf", async () => {
    await loescheQuellen(["a", "b"]);
    expect(deleteSource.mock.calls).toEqual([["a"], ["b"]]);
  });

  it("übersteht einen Fehlschlag und löscht die übrigen", async () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    deleteSource.mockRejectedValueOnce(new Error("500"));
    await loescheQuellen(["a", "b"]);
    expect(deleteSource).toHaveBeenCalledTimes(2);
    expect(warn).toHaveBeenCalledTimes(1);
    warn.mockRestore();
  });
});

describe("formatWert", () => {
  it("schreibt zwei Nachkommastellen mit Komma", () => {
    expect(formatWert(0.83)).toBe("0,83");
    expect(formatWert(0.9)).toBe("0,90");
  });
});
