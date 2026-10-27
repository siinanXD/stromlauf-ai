import { describe, expect, it } from "vitest";
import { dauerText, flowOf, haengt, statusKlasse, zuPollen } from "./knoten";

const step = (key: string, status = "wartet", extra = {}) => ({ key, label: key, status, started_at: null, finished_at: null, input: "", output: "", trace_url: null, error: null, ...extra });

describe("knoten", () => {
  it("baut acht Knoten in einer Reihe mit sieben Kanten", () => {
    const steps = ["hochladen","lesen","maschine","steckbrief","modell","zusammenfassung","lernen","fertig"].map((k) => step(k));
    const { nodes, edges } = flowOf(steps as never);
    expect(nodes.map((n) => n.id)).toEqual(steps.map((s) => s.key));
    expect(nodes[3].position).toEqual({ x: 660, y: 0 });
    expect(edges.map((e) => `${e.source}>${e.target}`)).toEqual(["hochladen>lesen","lesen>maschine","maschine>steckbrief","steckbrief>modell","modell>zusammenfassung","zusammenfassung>lernen","lernen>fertig"]);
  });
  it("färbt nach Status nur über Tokens", () => {
    expect(statusKlasse("fertig")).toContain("border-ok");
    expect(statusKlasse("laeuft")).toContain("motion-safe:animate-pulse");
    expect(statusKlasse("fehler")).toContain("border-error");
  });
  it("erkennt einen hängenden Lauf nach 10 Minuten", () => {
    const run = { status: "laeuft", steps: [step("lesen", "laeuft", { started_at: "2026-10-26T10:00:00+00:00" })] } as never;
    expect(haengt(run, new Date("2026-10-26T10:05:00+00:00"))).toBe(false);
    expect(haengt(run, new Date("2026-10-26T10:11:00+00:00"))).toBe(true);
  });
  it("erkennt einen Lauf, der zwischen den Schritten stehen blieb", () => {
    const fertig = step("hochladen", "fertig", { started_at: "2026-10-26T10:00:00+00:00", finished_at: "2026-10-26T10:01:00+00:00" });
    const run = { status: "laeuft", created_at: "2026-10-26T09:59:00+00:00", steps: [fertig, step("lesen")] } as never;
    expect(haengt(run, new Date("2026-10-26T10:05:00+00:00"))).toBe(false);
    expect(haengt(run, new Date("2026-10-26T10:12:00+00:00"))).toBe(true);
    const ohne = { status: "laeuft", created_at: "2026-10-26T10:00:00+00:00", steps: [step("hochladen")] } as never;
    expect(haengt(ohne, new Date("2026-10-26T10:12:00+00:00"))).toBe(true);
  });
  it("fragt auch scheinbar hängende laufende Läufe weiter ab", () => {
    const haengend = { id: "a", status: "laeuft", created_at: "2026-10-26T09:00:00+00:00", steps: [step("lesen", "laeuft", { started_at: "2026-10-26T09:00:00+00:00" })] };
    const fertig = { id: "b", status: "fertig", created_at: "2026-10-26T09:00:00+00:00", steps: [] };
    expect(haengt(haengend as never, new Date("2026-10-26T10:00:00+00:00"))).toBe(true);
    expect(zuPollen([haengend, fertig] as never).map((r) => r.id)).toEqual(["a"]);
  });
  it("formatiert die Dauer deutsch", () => {
    expect(dauerText(step("x", "fertig", { started_at: "2026-10-26T10:00:00+00:00", finished_at: "2026-10-26T10:00:12.300+00:00" }) as never)).toBe("12,3 s");
    expect(dauerText(step("x") as never)).toBe("");
  });
});
