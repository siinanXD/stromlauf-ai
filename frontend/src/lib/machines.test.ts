import { describe, expect, it } from "vitest";

import type { MachineListItem } from "./api";
import { docsLabel, filterMachines, summarizeMachines } from "./machines";

const machine = (over: Partial<MachineListItem>): MachineListItem => ({
  id: "m",
  name: "L1-UR Umroller",
  machine_type: "main",
  line: "L1 Toilettenpapier",
  hall_id: "h",
  hall_name: "Verarbeitung",
  source_id: "s",
  source_name: "Umroller UR-01",
  document_count: 6,
  ready_document_count: 6,
  fault_count: 3,
  open_diagnoses: 0,
  cabinet_count: 1,
  has_layout: true,
  key_figure: "1.200 m/min",
  ...over,
});

describe("filterMachines", () => {
  const list = [
    machine({ id: "a" }),
    machine({ id: "b", name: "L2-PAL Palettierer", machine_type: "robot", line: "L2 Küchenrolle", source_name: "Palettierer PAL-02" }),
    machine({ id: "c", name: "PM1 Sektor 3", line: "", hall_name: "Grundstoff", source_id: null, source_name: null }),
  ];

  it("liefert alles ohne Suchbegriff", () => {
    expect(filterMachines(list, "  ")).toHaveLength(3);
  });

  it("sucht in Name, Linie, Halle, Typlabel und Quelle, Wörter UND-verknüpft", () => {
    expect(filterMachines(list, "palettierer").map((m) => m.id)).toEqual(["b"]);
    expect(filterMachines(list, "roboter").map((m) => m.id)).toEqual(["b"]);
    expect(filterMachines(list, "grundstoff").map((m) => m.id)).toEqual(["c"]);
    expect(filterMachines(list, "ur-01").map((m) => m.id)).toEqual(["a"]);
    expect(filterMachines(list, "L2 Verarbeitung").map((m) => m.id)).toEqual(["b"]);
    expect(filterMachines(list, "L2 Grundstoff")).toEqual([]);
  });
});

describe("summarizeMachines", () => {
  it("zaehlt Maschinen ohne fertige Doku, offene Diagnosen und Fehler", () => {
    const summary = summarizeMachines([
      machine({ ready_document_count: 0, document_count: 2, open_diagnoses: 2 }),
      machine({ source_id: null, document_count: 0, ready_document_count: 0, fault_count: 0 }),
      machine({ open_diagnoses: 1 }),
    ]);
    expect(summary).toEqual({ total: 3, withoutDocs: 2, openDiagnoses: 3, faults: 6 });
  });
});

describe("docsLabel", () => {
  it("unterscheidet keine, teilweise und fertige Doku", () => {
    expect(docsLabel(machine({ source_id: null, document_count: 0 }))).toBe("keine");
    expect(docsLabel(machine({ document_count: 0, ready_document_count: 0 }))).toBe("keine");
    expect(docsLabel(machine({ document_count: 6, ready_document_count: 2 }))).toBe("2 von 6 fertig");
    expect(docsLabel(machine({ document_count: 1, ready_document_count: 1 }))).toBe("1 Dokument");
    expect(docsLabel(machine({}))).toBe("6 Dokumente");
  });
});
