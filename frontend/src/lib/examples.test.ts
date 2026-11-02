import { describe, expect, it } from "vitest";

import type { TagSearchHit } from "@/lib/api";

import { exampleQuestions } from "./examples";

const hit = (tag: string, tag_type: string): TagSearchHit => ({ tag, tag_type, occurrences: 1, machines: [] });

const INDEX: Record<string, TagSearchHit[]> = {
  "-K": [hit("-K1", "device")],
  "-X": [hit("-X3", "device"), hit("-X3:5", "terminal")],
  FB: [{ ...hit("FB 1", "plc_block"), occurrences: 2 }, { ...hit("FB 10", "plc_block"), occurrences: 9 }],
  "-M": [hit("-M1", "device")],
};

describe("exampleQuestions", () => {
  it("nimmt nur Kennzeichen aus dem Index", async () => {
    const questions = await exampleQuestions(async (q) => INDEX[q] ?? []);
    expect(questions).toEqual([
      "Wo ist -K1 verbaut und was schaltet es?",
      "Wohin führt Klemme -X3:5 und was hängt daran?",
      "Erkläre mir FB 10 Netzwerk für Netzwerk.",
      "Motor -M1 läuft nicht an: welche Bedingungen müssen erfüllt sein?",
    ]);
  });

  it("lässt Fragen weg, für die der Index nichts hat, auch bei Suchfehlern", async () => {
    const questions = await exampleQuestions(async (q) => {
      if (q === "FB") throw new Error("Backend nicht erreichbar");
      return q === "-K" ? INDEX["-K"] : [];
    });
    expect(questions).toEqual(["Wo ist -K1 verbaut und was schaltet es?"]);
  });
});
