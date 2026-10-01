import { describe, expect, it } from "vitest";

import { clampBox, moveBy, nudge, resizeBy, sameBox, toPixels } from "./bbox";

describe("bbox", () => {
  const box = { x: 0.2, y: 0.3, w: 0.1, h: 0.12 };

  it("rechnet relativ nach Pixel", () => {
    expect(toPixels(box, 800, 600)).toEqual({ left: 160, top: 180, width: 80, height: 72 });
  });

  it("verschiebt per Pixel-Delta und bleibt im Bild", () => {
    expect(moveBy(box, 80, -60, 800, 600)).toEqual({ x: 0.30000000000000004, y: 0.19999999999999998, w: 0.1, h: 0.12 });
    const edge = moveBy(box, 10_000, 10_000, 800, 600);
    expect(edge).toEqual({ x: 0.9, y: 0.88, w: 0.1, h: 0.12 });
    expect(moveBy(box, 1, 1, 0, 0)).toBe(box);
  });

  it("skaliert an einer Ecke, gegenueberliegende Ecke bleibt", () => {
    const se = resizeBy(box, "se", 80, 60, 800, 600);
    expect(se).toEqual({ x: 0.2, y: 0.3, w: 0.2, h: 0.22 });
    const nw = resizeBy(box, "nw", -80, -60, 800, 600);
    expect(nw.x + nw.w).toBeCloseTo(box.x + box.w);
    expect(nw.y + nw.h).toBeCloseTo(box.y + box.h);
    const tiny = resizeBy(box, "se", -800, -600, 800, 600);
    expect(tiny.w).toBe(0.01);
    expect(tiny.h).toBe(0.01);
  });

  it("clamp haelt Mindestgroesse und Bildrand ein", () => {
    expect(clampBox({ x: -1, y: 2, w: 0, h: 5 })).toEqual({ x: 0, y: 0, w: 0.01, h: 1 });
  });

  it("nudge per Tastatur, Shift skaliert", () => {
    expect(nudge(box, "ArrowRight", false)!.x).toBeCloseTo(0.205);
    expect(nudge(box, "ArrowDown", true)!.h).toBeCloseTo(0.125);
    expect(nudge(box, "Enter", false)).toBeNull();
    expect(sameBox(box, { ...box })).toBe(true);
    expect(sameBox(box, { ...box, x: 0.21 })).toBe(false);
  });
});
