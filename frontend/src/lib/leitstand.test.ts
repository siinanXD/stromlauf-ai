import { describe, expect, it } from "vitest";

import type { SimResult } from "./api";
import { stateAt } from "./leitstand";

const t = (hhmm: string, day = "2026-09-28") => `${day}T${hhmm}`;
const ms = (hhmm: string, day = "2026-09-28") => new Date(t(hhmm, day)).getTime();
const stage = (stageKey: string, label: string, resource: string, arrive: string, start: string, end: string, slot: number | null = 0) => ({
  stage: stageKey,
  label,
  resource,
  slot,
  arrive: t(arrive),
  start: t(start),
  end: t(end),
});

const RESULT: SimResult = {
  start: t("08:00"),
  end: t("12:45"),
  resources: [
    { key: "office:ks", label: "Kundenservice", kind: "office", capacity: 2 },
    { key: "office:fin", label: "Finanzen", kind: "office", capacity: 1 },
    { key: "line:L1", label: "L1", kind: "line", capacity: 1 },
    { key: "docks", label: "Verladetore", kind: "dock", capacity: 2 },
  ],
  orders: [
    {
      id: "1", number: "A1", customer: "K1", value: 100, pallets: 1, due: "2026-09-29", received_at: t("08:00"),
      ready_at: t("12:00"), shipped_at: t("12:45"), days_delta: 1, on_time: true,
      positions: [{ code: "TP", units: 84, from_stock: 0, produced: 84 }],
      stages: [
        stage("office:ks", "Kundenservice", "office:ks", "08:00", "08:00", "08:30"),
        stage("office:fin", "Finanzen", "office:fin", "08:30", "09:00", "10:00"),
        stage("line:0:0", "L1", "line:L1", "10:00", "10:00", "12:00"),
        stage("ship", "Verladung", "docks", "12:00", "12:00", "12:45", null),
      ],
      trucks: [{ truck: 1, dock: 1, start: t("12:00"), end: t("12:45") }],
    },
    {
      id: "2", number: "A2", customer: "K2", value: 50, pallets: 1, due: null, received_at: t("08:00"),
      ready_at: null, shipped_at: null, days_delta: null, on_time: null,
      positions: [{ code: "TP", units: 84, from_stock: 84, produced: 0 }],
      stages: [
        stage("office:ks", "Kundenservice", "office:ks", "08:00", "08:00", "08:30", 1),
        stage("office:fin", "Finanzen", "office:fin", "08:30", "08:30", "09:00"),
        stage("credit", "Kreditklärung", "Finanzen (Klärung)", "09:00", "09:00", "11:00", null),
      ],
      trucks: [],
    },
  ],
  stock: { TP: { name: "Toilettenpapier", units_per_pallet: 84, points: [[t("08:00"), 84], [t("12:00"), 168], [t("12:45"), 84]] } },
  closed: { office: [[t("16:00"), t("07:00", "2026-09-29")]] },
  kpis: { on_time_rate: 1, avg_lead_hours: 4.75, utilization: {}, avg_wait_hours: {} },
  warnings: [],
};

describe("stateAt", () => {
  it("zeigt belegte Personen, Fortschritt und Warteschlange", () => {
    const state = stateAt(RESULT, ms("08:45"));
    const fin = state.resources["office:fin"];
    expect(fin.busy).toEqual([{ slot: 0, order: "A2", stage: "office:fin", progress: 0.5 }]);
    expect(fin.queue).toEqual(["A1"]);
    expect(state.orders.A1.status).toBe("wartet Finanzen");
    expect(state.orders.A2.status).toBe("Finanzen");
  });

  it("zeigt Kreditklärung als Halt bei Finanzen", () => {
    const state = stateAt(RESULT, ms("09:30"));
    expect(state.resources["office:fin"].hold).toEqual(["A2"]);
    expect(state.orders.A2.status).toBe("Kreditklärung");
  });

  it("zeigt LKW am Tor und was heute raus geht", () => {
    const state = stateAt(RESULT, ms("12:15"));
    expect(state.docks).toEqual([{ order: "A1", truck: 1, progress: 1 / 3 }, null]);
    expect(state.todayOut).toEqual([{ order: "A1", trucks: 1 }]);
    expect(state.stock[0]).toMatchObject({ code: "TP", units: 168, pallets: 2 });
  });

  it("markiert verladene und noch nicht eingegangene Aufträge", () => {
    expect(stateAt(RESULT, ms("13:00")).orders.A1).toMatchObject({ status: "verladen", done: true });
    expect(stateAt(RESULT, ms("07:00")).orders.A1.status).toBe("noch nicht eingegangen");
  });

  it("erkennt geschlossene Zeiten", () => {
    expect(stateAt(RESULT, ms("17:00")).closed.office).toBe(true);
    expect(stateAt(RESULT, ms("10:00")).closed.office).toBe(false);
  });
});
