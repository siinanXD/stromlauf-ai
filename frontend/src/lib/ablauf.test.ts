import { describe, expect, it } from "vitest";

import example from "../../public/ablauf/example.json";
import { DWELL_MS, initialState, isActive, setInput, stepOnce, tick } from "../../public/ablauf/sim.js";

const flow = example;

interface SimState {
  stepId: string | null;
  inputs: Record<string, number>;
  outputs: Record<string, number>;
  log: { from: string | null; to: string; via: string }[];
}
const start = (): SimState => initialState(flow) as unknown as SimState;

describe("Ablauf-Simulation", () => {
  it("startet in der Grundstellung mit Eingaengen in Ruhe und Ausgaengen aus", () => {
    const state = start();
    expect(state.stepId).toBe("S0");
    expect(state.inputs).toMatchObject({ "E0.0": 0, "E0.1": 1, "E0.2": 1, "E0.3": 1, "E0.4": 0 }); // Oeffner ruhen auf 1
    expect(state.outputs).toMatchObject({ "A4.0": 0, "A4.1": 0, "A4.2": 0, "A4.3": 0 });
  });

  it("laeuft automatisch S0 -> S1 -> S2 und setzt die Aktoren", () => {
    const state = start();
    tick(flow, state, DWELL_MS); // S0 -> S1 (Not-Halt ok, Motorschutz ok sind Ruhepegel)
    expect(state.stepId).toBe("S1");
    tick(flow, state, DWELL_MS); // Start-Flanke -> S2, Taster faellt danach zurueck
    expect(state.stepId).toBe("S2");
    expect(state.inputs["E0.0"]).toBe(0);
    expect(state.outputs["A4.0"]).toBe(1);
    expect(state.outputs["A4.2"]).toBe(1);
    const k1 = flow.io_points.find((p) => p.address === "A4.0")!;
    expect(isActive(state, k1)).toBe(true);
    expect(state.log.at(-1)).toEqual({ from: "S1", to: "S2", via: "Start-Flanke UND NICHT Stop" });
  });

  it("Einzelschritt und Handeingriff: Motorschutz loest Stoerung aus, Reset fuehrt zurueck", () => {
    const state = start();
    stepOnce(flow, state);
    stepOnce(flow, state);
    expect(state.stepId).toBe("S2");
    setInput(flow, state, "E0.2", 0); // Motorschutz ausgeloest -> S3 Stoerung
    expect(state.stepId).toBe("S3");
    expect(state.outputs).toMatchObject({ "A4.0": 0, "A4.3": 1 });
    setInput(flow, state, "E0.2", 1);
    expect(state.stepId).toBe("S0");
  });

  it("Taster fallen nach einer Transition zurueck, Sensoren bleiben", () => {
    const state = start();
    stepOnce(flow, state);
    stepOnce(flow, state); // S2, Start (Flanke) ist zurueck auf 0
    setInput(flow, state, "E0.1", 0); // Stop gedrueckt -> S0, Stop faellt zurueck auf 1 (Oeffner)
    expect(state.stepId).toBe("S0");
    expect(state.inputs["E0.1"]).toBe(1);
    setInput(flow, state, "E0.4", 1); // Lichtschranke: keine Transition, Pegel bleibt
    expect(state.inputs["E0.4"]).toBe(1);
  });

  it("wartet ohne Automatik auf Eingaben und ignoriert Zeit", () => {
    const state = start();
    tick(flow, state, 10 * DWELL_MS, false);
    expect(state.stepId).toBe("S1"); // Ruhepegel erfuellen S0 -> S1 auch von Hand
    tick(flow, state, 10 * DWELL_MS, false);
    expect(state.stepId).toBe("S1");
  });
});
