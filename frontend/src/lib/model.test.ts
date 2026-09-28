import { describe, expect, it } from "vitest";

import type { MachineMap } from "./api";
import { highlightFor, isReferenced, orderZones, zoneOf, zoneTitle } from "./model";

const MAP: MachineMap = {
  machine_id: "m1",
  source_id: "s1",
  part_count: 4,
  connectors: [{ source: "+ST1", target: "+FE1", label: "-W3" }],
  zones: [
    { id: "+ST1", code: "+ST1", name: "Schaltschrank", parts: [{ tag: "-K1", label: "Schütz", kind: "Schuetz/Relais", source: "bom" }, { tag: "-F2", label: "", kind: "Schutz", source: "bom" }] },
    { id: "+FE1", code: "+FE1", name: "Feld", parts: [{ tag: "-M1", label: "Motor", kind: "Motor", source: "bom" }] },
    { id: "?", code: "?", name: "Ohne Einbauort", parts: [{ tag: "-B7", label: "", kind: "Sensor", source: "index" }] },
  ],
};

describe("model", () => {
  it("markiert Zonen und Bauteile aus dem meta-Event, Schreibweise egal", () => {
    const h = highlightFor(MAP, ["k1", "-M1", "-Q9"]);
    expect(h.zoneIds).toEqual(["+ST1", "+FE1"]);
    expect(h.placed).toEqual(["-K1", "-M1"]);
    expect(h.unplaced).toEqual(["-Q9"]);
  });

  it("ohne Modell oder ohne Kennzeichen keine Markierung", () => {
    expect(highlightFor(null, ["-K1"])).toEqual({ zoneIds: [], placed: [], unplaced: ["-K1"] });
    expect(highlightFor(MAP, [])).toEqual({ zoneIds: [], placed: [], unplaced: [] });
  });

  it("findet die Zone eines Bauteils und sortiert markierte Zonen nach vorn", () => {
    expect(zoneOf(MAP, "-m1")?.code).toBe("+FE1");
    expect(zoneOf(MAP, "-Z1")).toBeNull();
    expect(orderZones(MAP.zones, ["-B7"]).map((z) => z.code)).toEqual(["?", "+ST1", "+FE1"]);
    expect(orderZones(MAP.zones, []).map((z) => z.code)).toEqual(["+ST1", "+FE1", "?"]);
    expect(isReferenced("-K1", ["K1"])).toBe(true);
  });

  it("betitelt Zonen mit Code und Klartext", () => {
    expect(zoneTitle({ code: "+ST1", name: "Schaltschrank" })).toBe("+ST1 · Schaltschrank");
    expect(zoneTitle({ code: "+FE2", name: "" })).toBe("+FE2");
    expect(zoneTitle({ code: "?", name: "Ohne Einbauort" })).toBe("Ohne Einbauort");
  });
});
