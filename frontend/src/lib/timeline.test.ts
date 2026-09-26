import { describe, expect, it } from "vitest";

import { timeAxis } from "./timeline";

const at = (d: number, h: number, m = 0) => new Date(2026, 8, d, h, m).getTime();

describe("timeAxis", () => {
  it("bildet ohne Luecke linear ab", () => {
    const axis = timeAxis([{ start: at(28, 8), end: at(28, 9) }], 600);
    expect(axis.x(at(28, 8))).toBe(0);
    expect(axis.x(at(28, 8, 30))).toBeCloseTo(300);
    expect(axis.x(at(28, 9))).toBeCloseTo(600);
    expect(axis.breaks).toEqual([]);
  });

  it("staucht eine Leerlauf-Luecke (Wochenende) auf eine feste Breite", () => {
    const axis = timeAxis(
      [
        { start: at(25, 15, 30), end: at(25, 16) },
        { start: at(28, 7), end: at(28, 9, 15) },
      ],
      500,
      { breakPx: 22 },
    );
    expect(axis.breaks).toHaveLength(1);
    expect(axis.breaks[0].w).toBe(22);
    expect(axis.breaks[0].minutes).toBe(63 * 60);
    expect(axis.x(at(28, 7)) - axis.x(at(25, 16))).toBeCloseTo(22);
    expect(axis.x(at(28, 9, 15))).toBeCloseTo(500);
  });

  it("bleibt monoton steigend", () => {
    const axis = timeAxis(
      [
        { start: at(25, 15), end: at(25, 16) },
        { start: at(28, 7), end: at(28, 17) },
      ],
      400,
    );
    let last = -Infinity;
    for (let t = at(25, 15); t <= at(28, 17); t += 15 * 60_000) {
      const x = axis.x(t);
      expect(x).toBeGreaterThanOrEqual(last);
      last = x;
    }
  });

  it("setzt Tagesmarken an Mitternacht und Stundenmarken alle 4 h", () => {
    const axis = timeAxis([{ start: at(28, 20), end: at(29, 4) }], 800);
    const day = axis.ticks.find((tick) => tick.day);
    expect(day?.label).toBe("Di 29.09.");
    expect(day?.x).toBeCloseTo(axis.x(at(29, 0)));
    expect(axis.ticks.filter((tick) => !tick.day).map((tick) => tick.label)).toEqual(["20", "04"]);
  });

  it("beschriftet bei langen Zeitraeumen nur so viele Tage, dass sich nichts ueberlappt", () => {
    const axis = timeAxis([{ start: at(28, 0), end: at(28, 0) + 33 * 24 * 3_600_000 }], 800);
    const labeled = axis.ticks.filter((tick) => tick.day && tick.label);
    expect(labeled.length).toBeGreaterThan(3);
    labeled.slice(1).forEach((tick, i) => expect(tick.x - labeled[i].x).toBeGreaterThanOrEqual(64));
  });
});
