import { describe, expect, it } from "vitest";
import type { MachineNote } from "@/lib/api";
import { belegText, QUELLE_LABELS, sortiert } from "./wissen";

const note = (id: string, gesperrt: boolean, created_at: string): MachineNote =>
  ({ id, machine_id: "m1", text: id, quelle: "lauf", belege: [], gesperrt, run_id: null, conversation_id: null, created_at });

describe("wissen", () => {
  it("sortiert gesperrte zuerst, dann neueste", () => {
    const list = [note("alt", false, "2026-10-26T10:00:00Z"), note("neu", false, "2026-10-27T10:00:00Z"), note("fix", true, "2026-10-25T10:00:00Z")];
    expect(sortiert(list).map((n) => n.id)).toEqual(["fix", "neu", "alt"]);
    expect(list[0].id).toBe("alt");
  });
  it("beschriftet Belege und Quellen", () => {
    expect(belegText({ document_id: "d", filename: "01_Plan.pdf", page: 3 })).toBe("01_Plan.pdf S. 3");
    expect(belegText({ document_id: "d", filename: "06_Anleitung.md", page: null })).toBe("06_Anleitung.md");
    expect(QUELLE_LABELS.mensch).toBe("Mensch");
  });
});
