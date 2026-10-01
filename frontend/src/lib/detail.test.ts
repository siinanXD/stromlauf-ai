import { describe, expect, it } from "vitest";

import { detailFromParam, detailToParam, type DetailRef } from "./detail";

const ALL: DetailRef[] = [
  { kind: "signal", tag: "-K1" },
  { kind: "plan", target: { documentId: "d-plan", filename: "01_Stromlaufplan_FB-01.pdf", page: 3, reference: "/3.4", label: "Stromlaufplan Blatt 3 · Spalte 4", tag: "-K1" } },
  { kind: "part", tag: "-X1:5" },
  { kind: "cabinet", cabinetId: "c-1", hotspotId: "hs1" },
  { kind: "fault", faultId: "f1" },
];

describe("detailToParam / detailFromParam", () => {
  it.each(ALL.map((d) => [d.kind, d] as const))("round-trips %s", (_, detail) => {
    expect(detailFromParam(detailToParam(detail))).toEqual(detail);
  });

  it("round-trips through a real query string (URLSearchParams encodes once more)", () => {
    for (const detail of ALL) {
      const params = new URLSearchParams({ fall: "conv-1", detail: detailToParam(detail) });
      const read = new URLSearchParams(params.toString());
      expect(detailFromParam(read.get("detail"))).toEqual(detail);
    }
  });

  it("is stable: the same detail always gives the same parameter", () => {
    expect(detailToParam({ kind: "part", tag: "-K1" })).toBe(detailToParam({ kind: "part", tag: "-K1" }));
  });

  it("keeps the optional hotspot out when it is missing", () => {
    expect(detailFromParam(detailToParam({ kind: "cabinet", cabinetId: "c-1" }))).toEqual({ kind: "cabinet", cabinetId: "c-1" });
  });

  it("rejects empty, broken and unknown parameters", () => {
    expect(detailFromParam(null)).toBeNull();
    expect(detailFromParam("")).toBeNull();
    expect(detailFromParam("%7Bkaputt")).toBeNull();
    expect(detailFromParam(encodeURIComponent(JSON.stringify({ kind: "nope", tag: "-K1" })))).toBeNull();
    expect(detailFromParam(encodeURIComponent(JSON.stringify({ kind: "part" })))).toBeNull();
    expect(detailFromParam(encodeURIComponent(JSON.stringify({ kind: "plan", target: {} })))).toBeNull();
  });
});
