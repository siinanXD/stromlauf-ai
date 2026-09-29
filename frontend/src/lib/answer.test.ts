import { describe, expect, it } from "vitest";

import { citationCheckFor, citationLabel, citationsValidLabel, deviceTagOf, parseCitations, refOf, splitSections } from "./answer";

const CHECKS = [
  { text: "[[01_Stromlaufplan_FB-01.pdf|/3.2]]", file: "01_Stromlaufplan_FB-01.pdf", locator: "/3.2", valid: true, checked: true, reason: "" },
  { text: "[[02_Stueckliste_FB-01.xlsx|-X3:3]]", file: "02_Stueckliste_FB-01.xlsx", locator: "-X3:3", valid: false, checked: true, reason: "Kennzeichen -X3:3 nicht in 02_Stueckliste_FB-01.xlsx" },
];

describe("citationCheckFor", () => {
  it("finds the check of a parsed citation by file and locator, case-insensitive on the file", () => {
    const { citations } = parseCitations("[[02_stueckliste_fb-01.XLSX|-X3:3]] [[01_Stromlaufplan_FB-01.pdf|/3.2]]");
    expect(citationCheckFor(CHECKS, citations[0])?.valid).toBe(false);
    expect(citationCheckFor(CHECKS, citations[1])?.valid).toBe(true);
  });

  it("returns undefined without checks or for an unknown citation", () => {
    const citation = { index: 0, filename: "x.pdf", loc: "S. 1" };
    expect(citationCheckFor(undefined, citation)).toBeUndefined();
    expect(citationCheckFor(CHECKS, citation)).toBeUndefined();
  });
});

describe("citationsValidLabel", () => {
  it("counts valid among checked citations and names the unverifiable ones separately", () => {
    expect(citationsValidLabel({ valid: 5, checked: 6, total: 6 })).toBe("Belege: 5 von 6 gültig");
    // 6 valid = 4 geprueft gueltig + 2 ungeprueft (die zaehlen als gueltig, sind aber nicht belegt)
    expect(citationsValidLabel({ valid: 6, checked: 4, total: 6 })).toBe("Belege: 4 von 4 geprüft gültig, 2 nicht prüfbar");
    expect(citationsValidLabel({ valid: 1, checked: 3, total: 3 })).toBe("Belege: 1 von 3 gültig");
    expect(citationsValidLabel({ valid: 0, checked: 0, total: 0 })).toBe("");
    expect(citationsValidLabel(undefined)).toBe("");
  });
});

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

describe("deviceTagOf", () => {
  it("finds the first device tag, not terminals", () => {
    expect(deviceTagOf("-K1 zieht an, Motor -M1 brummt")).toBe("-K1");
    expect(deviceTagOf("was liegt an -x1:5?")).toBeNull();
    expect(deviceTagOf("wo ist k12")).toBeNull();
    expect(deviceTagOf("Motor -m1 läuft nicht")).toBe("-M1");
  });
});
