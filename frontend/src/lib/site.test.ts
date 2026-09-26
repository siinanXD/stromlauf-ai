import { describe, expect, it } from "vitest";

import { borderPoint, laneBoxes, miniPlan, TILE } from "./site";

const machine = (id: string, line: string, pos_x: number, pos_y: number) => ({
  id,
  name: id,
  machine_type: "main" as const,
  line,
  pos_x,
  pos_y,
});

describe("laneBoxes", () => {
  it("umhuellt die Kacheln je Linie und laesst Maschinen ohne Linie weg", () => {
    const lanes = laneBoxes(
      [
        { line: "A", x: 0, y: 0 },
        { line: "A", x: 240, y: 0 },
        { line: "", x: 0, y: 200 },
        { line: "B", x: 0, y: 400 },
      ],
      TILE,
    );
    expect(lanes).toEqual([
      { line: "A", x: -16, y: -38, w: 240 + 184 + 32, h: 96 + 32 + 22 },
      { line: "B", x: -16, y: 362, w: 184 + 32, h: 96 + 32 + 22 },
    ]);
  });
});

describe("miniPlan", () => {
  it("liefert fuer eine leere Halle nichts", () => {
    expect(miniPlan([], { w: 300, h: 200 })).toEqual({ scale: 0, tiles: [], lanes: [] });
  });

  it("legt alle Kacheln und Baender in die Blockflaeche", () => {
    const size = { w: 300, h: 200 };
    const plan = miniPlan(
      [machine("a", "L1", 48, 48), machine("b", "L1", 288, 48), machine("c", "L2", 48, 216), machine("d", "", 900, 600)],
      size,
    );
    for (const rect of [...plan.tiles, ...plan.lanes]) {
      expect(rect.x).toBeGreaterThanOrEqual(-1e-9);
      expect(rect.y).toBeGreaterThanOrEqual(-1e-9);
      expect(rect.x + rect.w).toBeLessThanOrEqual(size.w + 1e-9);
      expect(rect.y + rect.h).toBeLessThanOrEqual(size.h + 1e-9);
    }
    expect(plan.tiles.map((t) => t.id)).toEqual(["a", "b", "c", "d"]);
    expect(plan.lanes.map((l) => l.line)).toEqual(["L1", "L2"]);
  });

  it("vergroessert eine einzelne Maschine hoechstens auf 60 %", () => {
    expect(miniPlan([machine("a", "", 0, 0)], { w: 2000, h: 2000 }).scale).toBe(0.6);
  });
});

describe("borderPoint", () => {
  const box = { x: 0, y: 0, w: 100, h: 50 };
  it("trifft die Seitenwand bei waagrechter Richtung", () => {
    expect(borderPoint(box, { x: 200, y: 0 })).toEqual({ x: 50, y: 0 });
  });
  it("trifft Boden oder Decke bei senkrechter Richtung", () => {
    expect(borderPoint(box, { x: 0, y: -300 })).toEqual({ x: 0, y: -25 });
  });
  it("trifft bei schraeger Richtung die naehere Kante", () => {
    expect(borderPoint(box, { x: 100, y: 100 })).toEqual({ x: 25, y: 25 });
  });
  it("bleibt in der Mitte, wenn beide Mittelpunkte gleich sind", () => {
    expect(borderPoint(box, { x: 0, y: 0 })).toEqual({ x: 0, y: 0 });
  });
});
