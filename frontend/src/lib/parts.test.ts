import { describe, expect, it } from "vitest";

import type { SignalNode, SignalPathData } from "./api";
import { relatedParts } from "./parts";

function node(id: string, kind: SignalNode["kind"], label = ""): SignalNode {
  return { id, kind, label, ref: "", detail: "", level: 0 };
}

function path(start: string, nodes: SignalNode[], edges: [string, string][]): SignalPathData {
  return { start, nodes, edges: edges.map(([source, target]) => ({ source, target })), schematic: null };
}

describe("relatedParts", () => {
  it("findet Betriebsmittel ueber eine Klemme hinweg, nicht sich selbst", () => {
    const data = path(
      "-K1",
      [node("A4.0", "address"), node("-X3:9", "terminal"), node("-K1", "device"), node("-X4:U", "terminal"), node("-M1", "device")],
      [
        ["A4.0", "-X3:9"],
        ["-X3:9", "-K1"],
        ["-K1", "-X4:U"],
        ["-X4:U", "-M1"],
      ],
    );
    expect(relatedParts(data, "-K1")).toEqual([{ tag: "-M1", verb: "hängt an" }]);
  });

  it("nennt das Kennzeichen, nicht die Bezeichnung aus der Stueckliste", () => {
    // Geraeteknoten tragen die Stuecklisten-Bezeichnung als label; der Chip braucht das Kennzeichen, das Verb auch
    const data = path(
      "-K1",
      [
        node("-K1", "device", "Schuetz Foerdermotor vorwaerts"),
        node("-X4:U", "terminal", "Motor Phase U"),
        node("-M1", "device", "Foerdermotor 3~ 1,5 kW"),
        node("-F2", "device", "Motorschutzschalter"),
      ],
      [
        ["-K1", "-X4:U"],
        ["-X4:U", "-M1"],
        ["-F2", "-K1"],
      ],
    );
    expect(relatedParts(data, "-K1")).toEqual([
      { tag: "-M1", verb: "hängt an" },
      { tag: "-F2", verb: "schützt" },
    ]);
  });

  it("zaehlt Anschluesse als ihr Geraet: Spule und Kontakt liegen zwischen Klemme und Schuetz (Issue #98)", () => {
    const data = path(
      "-K1",
      [
        node("-X3:9", "terminal"),
        node("-K1:A1", "pin", "Spule"),
        node("-K1", "device"),
        node("-K1:2", "pin", "Hauptkontakt"),
        node("-X4:U", "terminal"),
        node("-M1", "device"),
      ],
      [
        ["-X3:9", "-K1:A1"],
        ["-K1:A1", "-K1"],
        ["-K1", "-K1:2"],
        ["-K1:2", "-X4:U"],
        ["-X4:U", "-M1"],
      ],
    );
    expect(relatedParts(data, "-K1")).toEqual([{ tag: "-M1", verb: "hängt an" }]);
  });
});
