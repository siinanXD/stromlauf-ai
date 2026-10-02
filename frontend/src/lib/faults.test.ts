import { describe, expect, it } from "vitest";

import { faultHits, matchesAny, sameTag } from "./faults";

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
  it("findet Hotspots je Kennzeichen und nennt Unplatzierte", () => {
    const hits = faultHits({ tags: ["-F2", "-M1", "-X3:1", " "] }, cabinets);
    expect(hits.tags).toEqual(["-F2", "-M1", "-X3:1"]);
    expect(hits.hotspotIds).toEqual(["h1", "h3"]);
    expect(hits.unplaced).toEqual(["-X3:1"]);
  });

  it("kommt ohne Schaltschrankbilder aus", () => {
    const hits = faultHits({ tags: ["-K1"] }, []);
    expect(hits.hotspotIds).toEqual([]);
    expect(hits.unplaced).toEqual(["-K1"]);
  });
});
