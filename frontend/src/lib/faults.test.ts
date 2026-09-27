import { describe, expect, it } from "vitest";

import type { Layout } from "./api";
import { faultHits, matchesAny, sameTag } from "./faults";

const layout = {
  parts: [
    { id: "p1", tag: "-F2" },
    { id: "p2", tag: "-M1" },
    { id: "p3", tag: "" },
  ],
} as unknown as Layout;
const cabinets = [{ hotspots: [{ id: "h1", tag: "F2" }, { id: "h2", tag: "-K1" }] }, { hotspots: [{ id: "h3", tag: "-m1" }] }] as never;

describe("sameTag", () => {
  it("ignoriert Minus, Gross/Klein und Leerzeichen, aber nicht leere Werte", () => {
    expect(sameTag("-K12", "k12")).toBe(true);
    expect(sameTag(" -K12 ", "-K12")).toBe(true);
    expect(sameTag("-K12", "-K1")).toBe(false);
    expect(sameTag("", "")).toBe(false);
    expect(matchesAny("-M1", ["-F2", "M1"])).toBe(true);
  });
});

describe("faultHits", () => {
  it("findet Teile und Hotspots je Kennzeichen und nennt Unplatzierte", () => {
    const hits = faultHits({ tags: ["-F2", "-M1", "-X3:1", " "] }, layout, cabinets);
    expect(hits.tags).toEqual(["-F2", "-M1", "-X3:1"]);
    expect(hits.partIds).toEqual(["p1", "p2"]);
    expect(hits.hotspotIds).toEqual(["h1", "h3"]);
    expect(hits.unplaced).toEqual(["-X3:1"]);
  });

  it("kommt ohne Draufsicht aus", () => {
    const hits = faultHits({ tags: ["-K1"] }, null, cabinets);
    expect(hits.partIds).toEqual([]);
    expect(hits.hotspotIds).toEqual(["h2"]);
    expect(hits.unplaced).toEqual([]);
  });
});
