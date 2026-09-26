import { describe, expect, it } from "vitest";

import { citationLabel, parseCitations, refOf, splitSections } from "./answer";

describe("parseCitations", () => {
  it("replaces markers with numbered cite links and dedupes", () => {
    const { markdown, citations } = parseCitations(
      "-F2 ausgelöst [[01_Stromlaufplan_FB-01.pdf|/3.2]], siehe auch [[01_Stromlaufplan_FB-01.pdf|/3.2]] und [[06_Betriebsanleitung_FB-01.md|Kap. 6]].",
    );
    expect(citations).toEqual([
      { index: 0, filename: "01_Stromlaufplan_FB-01.pdf", loc: "/3.2" },
      { index: 1, filename: "06_Betriebsanleitung_FB-01.md", loc: "Kap. 6" },
    ]);
    expect(markdown).toBe("-F2 ausgelöst [/3.2](cite:0), siehe auch [/3.2](cite:0) und [Kap. 6](cite:1).");
  });

  it("keeps an unfinished marker while streaming as plain text", () => {
    const { markdown, citations } = parseCitations("Prüfe -X4 [[03_Klemmen");
    expect(citations).toEqual([]);
    expect(markdown).toBe("Prüfe -X4 [[03_Klemmen");
  });

  it("trims whitespace inside markers", () => {
    expect(parseCitations("[[ a.pdf | S. 3 ]]").citations).toEqual([{ index: 0, filename: "a.pdf", loc: "S. 3" }]);
  });
});

describe("splitSections", () => {
  it("splits the four known headings", () => {
    const md = "## Kurzantwort\nPhase fehlt.\n\n## Pruefen\n1. -F2 prüfen\n\n## Details\n| a | b |\n\n## Sicherheit\nFreischalten.";
    const s = splitSections(md);
    expect(s.kurz).toBe("Phase fehlt.");
    expect(s.pruefen).toBe("1. -F2 prüfen");
    expect(s.details).toBe("| a | b |");
    expect(s.sicherheit).toBe("Freischalten.");
    expect(s.frei).toBe("");
  });

  it("accepts the umlaut spelling Prüfen", () => {
    expect(splitSections("## Prüfen\n1. x").pruefen).toBe("1. x");
  });

  it("returns unstructured answers unchanged as frei", () => {
    const md = "Die Klemme -X1:5 führt 24 V.\n\n### Tabelle\n| a |";
    expect(splitSections(md)).toEqual({ frei: md });
  });

  it("keeps text before the first known heading in frei", () => {
    const s = splitSections("Vorab.\n## Kurzantwort\nKurz.");
    expect(s.frei).toBe("Vorab.");
    expect(s.kurz).toBe("Kurz.");
  });
});

describe("citationLabel and refOf", () => {
  it("uses the document type as short name", () => {
    expect(citationLabel({ index: 0, filename: "01_Stromlaufplan_FB-01.pdf", loc: "/3.8" }, "schematic")).toBe("Stromlaufplan /3.8");
  });

  it("falls back to the file name without extension and number prefix", () => {
    expect(citationLabel({ index: 0, filename: "07_Wartung.md", loc: "Kap. 2" })).toBe("Wartung Kap. 2");
  });

  it("detects sheet references and pages", () => {
    expect(refOf("/3.8")).toEqual({ ref: "/3.8" });
    expect(refOf("S. 12")).toEqual({ ref: "S. 12", page: 12 });
    expect(refOf("FB 10 NW 3")).toEqual({});
  });
});
