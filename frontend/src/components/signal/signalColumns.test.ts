import { describe, expect, it } from "vitest";

import type { SignalMainData } from "@/lib/api";

import { COLUMN_LABELS, nodeTitle, orderInColumns, sheetShort, sheetText, visibleColumns } from "./signalColumns";
import { conveyor, mainEdge, mainNode } from "./signalTestData";

const xs = (data: SignalMainData) => Object.fromEntries([...orderInColumns(data)].map(([id, at]) => [id, at.x]));

describe("visibleColumns / orderInColumns: Reihenfolge", () => {
  it("ordnet die Spalten in Vertragsreihenfolge, egal wie die Antwort Spalten und Knoten listet", () => {
    const data = conveyor();
    const shuffled: SignalMainData = { ...data, columns: [...data.columns].reverse(), nodes: [...data.nodes].reverse() };

    expect(visibleColumns(shuffled)).toEqual(["feld", "klemme_vor", "sps_eingang", "programm", "sps_ausgang", "klemme_nach", "schaltgeraet", "verbraucher"]);
    expect(xs(shuffled)).toMatchObject({ "-S1": 0, "-X1:3": 1, "E0.3": 2, "FC 1/NW2": 3, "A4.0": 4, "-X3:9": 5, "-K1": 6, "-M1": 7 });
  });

  it("liefert fuer dieselben Daten immer dieselbe Lage", () => {
    const data = conveyor();
    const shuffled = { ...data, nodes: [data.nodes[9], ...data.nodes.slice(3, 9), ...data.nodes.slice(0, 3)], edges: [...data.edges].reverse() };
    expect([...orderInColumns(shuffled)].sort()).toEqual([...orderInColumns(data)].sort());
  });
});

describe("visibleColumns / orderInColumns: leere Spalten", () => {
  it("laesst Spalten ohne Hauptwegknoten weg, auch wenn die Antwort sie nennt; x laeuft ohne Luecke", () => {
    const data: SignalMainData = {
      start: "-K1",
      view: "main",
      columns: ["feld", "klemme_vor", "sps_eingang", "schaltgeraet", "verbraucher"],
      nodes: [
        mainNode("-S1", "device", "feld", 0),
        mainNode("-X1:1", "terminal", "klemme_vor", 1),
        mainNode("-K1", "device", "schaltgeraet", 2),
        mainNode("-M1", "device", "verbraucher", 3),
      ],
      edges: [mainEdge("-S1", "-X1:1"), mainEdge("-X1:1", "-K1"), mainEdge("-K1", "-M1")],
      schematic: null,
    };

    const columns = visibleColumns(data);
    expect(columns).toEqual(["feld", "klemme_vor", "schaltgeraet", "verbraucher"]);
    expect(columns.map((c) => COLUMN_LABELS[c])).toEqual(["Feld", "Klemme", "Schaltgerät", "Verbraucher"]);
    expect(xs(data)).toEqual({ "-S1": 0, "-X1:1": 1, "-K1": 2, "-M1": 3 });
  });
});

describe("orderInColumns: Baryzentrum", () => {
  it("setzt einen Knoten auf die mittlere Hoehe seiner Nachbarn", () => {
    // E0.0 -> drei Netzwerke untereinander -> A4.0, das von allen drei Netzwerken geschrieben wird
    const data: SignalMainData = {
      start: "E0.0",
      view: "main",
      columns: ["sps_eingang", "programm", "sps_ausgang"],
      nodes: [
        mainNode("E0.0", "address", "sps_eingang", 0),
        mainNode("FC 1/NW1", "network", "programm", 1),
        mainNode("FC 1/NW2", "network", "programm", 2),
        mainNode("FC 1/NW3", "network", "programm", 3),
        mainNode("A4.0", "address", "sps_ausgang", 4),
      ],
      edges: [
        mainEdge("E0.0", "FC 1/NW1", ["awl"]),
        mainEdge("FC 1/NW1", "FC 1/NW2", ["awl"]),
        mainEdge("FC 1/NW2", "FC 1/NW3", ["awl"]),
        mainEdge("FC 1/NW3", "A4.0", ["awl"]),
        mainEdge("FC 1/NW1", "A4.0", ["awl"]),
        mainEdge("FC 1/NW2", "A4.0", ["awl"]),
      ],
      schematic: null,
    };

    const at = orderInColumns(data);
    expect(at.get("E0.0")).toEqual({ x: 0, y: 0 });
    // Die Netzwerke stapeln sich in ihrer Spalte in Wegfolge
    expect([at.get("FC 1/NW1"), at.get("FC 1/NW2"), at.get("FC 1/NW3")]).toEqual([
      { x: 1, y: 0 },
      { x: 1, y: 1 },
      { x: 1, y: 2 },
    ]);
    // Nachbarn auf 0, 1 und 2: A4.0 steht auf 1, nicht oben und nicht beim letzten Netzwerk
    expect(at.get("A4.0")).toEqual({ x: 2, y: 1 });
  });

  it("stellt Abzweige in die Spalte ihres Hauptwegknotens, auf die naechsten freien Zeilen darunter", () => {
    const at = orderInColumns(conveyor());
    expect(at.get("-K1")).toEqual({ x: 6, y: 0 });
    expect(at.get("-H1")).toEqual({ x: 6, y: 1 });
    expect(at.get("-X3:10")).toEqual({ x: 6, y: 2 });
  });
});

describe("Texte", () => {
  it("nennt Blatt und Spalte nur bei Blattverweisen", () => {
    expect(sheetText("/3.5")).toBe("Blatt 3 · Spalte 5");
    expect(sheetShort("/3.5")).toBe("Blatt 3 · Sp. 5");
    expect(sheetText("FC 1 NW 2")).toBeNull();
    expect(sheetText("")).toBeNull();
  });

  it("nennt Netzwerke nach Baustein und Variablen ohne Baustein", () => {
    expect(nodeTitle({ id: "FC 1/NW2", kind: "network", ref: "FC 1 NW 2" })).toBe("FC 1 NW 2");
    expect(nodeTitle({ id: "FB 2#Start", kind: "variable", ref: "" })).toBe("Start");
    expect(nodeTitle({ id: "-K1", kind: "device", ref: "/3.5" })).toBe("-K1");
  });
});
