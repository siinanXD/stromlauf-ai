import { describe, expect, it } from "vitest";

import { friendlyError, olderBefore, olderPage } from "./history";
import { partHref, remarkPartTags, splitBlocks, tagFromHref, tagPattern, type MdNode } from "./markdownText";

describe("splitBlocks", () => {
  it("splits paragraphs at blank lines", () => {
    expect(splitBlocks("Erster Absatz.\n\nZweiter\nAbsatz.\n\n\nDritter.")).toEqual(["Erster Absatz.", "Zweiter\nAbsatz.", "Dritter."]);
  });

  it("keeps fenced code with blank lines in one block", () => {
    const md = "Vorher.\n\n```awl\nU E 0.0\n\n= A 0.1\n```\n\nNachher.";
    expect(splitBlocks(md)).toEqual(["Vorher.", "```awl\nU E 0.0\n\n= A 0.1\n```", "Nachher."]);
  });

  it("keeps a loose list together so numbering stays intact", () => {
    const md = "1. -F2 zurücksetzen.\n\n2. Spule messen.\n\n   Wert notieren.\n\nDanach testen.";
    expect(splitBlocks(md)).toEqual(["1. -F2 zurücksetzen.\n\n2. Spule messen.\n\n   Wert notieren.", "Danach testen."]);
  });

  it("returns the growing last paragraph separately while streaming", () => {
    expect(splitBlocks("Fertig.\n\nNoch nicht fert")).toEqual(["Fertig.", "Noch nicht fert"]);
    expect(splitBlocks("")).toEqual([]);
  });
});

function run(tree: MdNode, tags: string[]) {
  remarkPartTags({ tags })(tree);
  return tree;
}

const paragraph = (...children: MdNode[]): MdNode => ({ type: "root", children: [{ type: "paragraph", children }] });

describe("remarkPartTags", () => {
  it("links known tags in text, longest first, keeping the document spelling", () => {
    const tree = run(paragraph({ type: "text", value: "Schütz -K1 und -k12 an -X1:5." }), ["-K1", "-K12", "-X1:5"]);
    const nodes = tree.children![0].children!;
    expect(nodes.map((n) => (n.type === "link" ? `[${n.children![0].value}](${n.url})` : n.value))).toEqual([
      "Schütz ",
      `[-K1](${partHref("-K1")})`,
      " und ",
      `[-k12](${partHref("-K12")})`,
      " an ",
      `[-X1:5](${partHref("-X1:5")})`,
      ".",
    ]);
  });

  it("does not link parts of other tags or words", () => {
    const pattern = tagPattern(["-K1", "-X1", "E0"])!;
    expect("-K12 -X1:5 E0.3 FB-K1".match(pattern)).toBeNull();
    expect("an -K1: Spule".match(pattern)).toEqual(["-K1"]);
  });

  it("leaves code, links (citations) and empty tag lists alone", () => {
    const tree = run(
      paragraph({ type: "inlineCode", value: "-K1" }, { type: "link", url: "cite:0", children: [{ type: "text", value: "-K1" }] }),
      ["-K1"],
    );
    expect(tree.children![0].children!.map((n) => n.type)).toEqual(["inlineCode", "link"]);
    expect(tree.children![0].children![1].url).toBe("cite:0");
    const untouched = paragraph({ type: "text", value: "-K1" });
    expect(run(untouched, []).children![0].children).toEqual([{ type: "text", value: "-K1" }]);
  });

  it("reads the tag back from the link", () => {
    expect(tagFromHref(partHref("-X1:5"))).toBe("-X1:5");
    expect(tagFromHref("cite:1")).toBeNull();
    expect(tagFromHref(undefined)).toBeNull();
  });
});

describe("history pages", () => {
  it("knows whether older messages exist from the index of the first one", () => {
    expect(olderBefore([{ index: 30 }, { index: 31 }])).toBe(30);
    expect(olderBefore([{ index: 0 }])).toBeNull();
    // Server ohne Seiten: kein index, der Verlauf ist vollstaendig
    expect(olderBefore([{}, {}])).toBeNull();
    expect(olderBefore([])).toBeNull();
  });

  it("prepends only older, unknown messages (also when the server ignores before)", () => {
    const current = [{ index: 2 }, { index: 3 }];
    expect(olderPage(current, [{ index: 0 }, { index: 1 }])).toEqual([{ index: 0 }, { index: 1 }]);
    expect(olderPage(current, [{ index: 0 }, { index: 1 }, { index: 2 }, { index: 3 }])).toEqual([{ index: 0 }, { index: 1 }]);
    expect(olderPage([{ index: 0 }], [{ index: 0 }])).toEqual([]);
  });
});

describe("friendlyError", () => {
  it("hides developer texts like ports, paths and HTTP codes", () => {
    expect(friendlyError("Failed to fetch")).toBe("Die Antwort konnte nicht geladen werden.");
    expect(friendlyError("500 Internal Server Error")).toBe("Die Antwort konnte nicht geladen werden.");
    expect(friendlyError("Backend nicht erreichbar unter http://localhost:8010/api/chat")).toBe("Die Antwort konnte nicht geladen werden.");
    expect(friendlyError("")).toBe("Die Antwort konnte nicht geladen werden.");
  });

  it("keeps readable server messages", () => {
    expect(friendlyError("KI-Monatslimit erreicht.")).toBe("KI-Monatslimit erreicht.");
  });
});
