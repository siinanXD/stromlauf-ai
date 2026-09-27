import { describe, expect, it } from "vitest";

import { costText, eur, minutesText, num, parseAmount, qtyText, whenText } from "./format";

describe("format", () => {
  it("formatiert Zahlen deutsch", () => {
    expect(num(10000)).toBe("10.000");
    expect(num(8.407, 1)).toBe("8,4");
  });

  it("zeigt Mengen mit passender Genauigkeit je Einheit", () => {
    expect(qtyText(8.407, "t")).toBe("8,41 t");
    expect(qtyText(87680, "Stk")).toBe("87.680 Stk");
    expect(qtyText(84.068, "kg")).toBe("84,1 kg");
  });

  it("zeigt Euro mit zwei Nachkommastellen", () => {
    expect(eur(1.4531)).toBe("1,45 €");
    expect(eur(17168.68)).toBe("17.168,68 €");
  });

  it("zeigt KI-Kosten aus Cent als ungefaehren Eurobetrag", () => {
    expect(costText(0)).toBe("0,00 €");
    expect(costText(0.3)).toBe("< 0,01 €");
    expect(costText(1.87)).toBe("≈ 0,02 €");
    expect(costText(243)).toBe("≈ 2,43 €");
  });

  it("zeigt Zeitpunkte mit Wochentag", () => {
    expect(whenText("2026-09-28T17:06")).toBe("Mo 28.09. 17:06");
  });

  it("zeigt Dauern in Stunden und Minuten", () => {
    expect(minutesText(45)).toBe("45 min");
    expect(minutesText(305.7)).toBe("5 h 06 min");
    expect(minutesText(4416.8)).toBe("3 d 1 h");
  });

  it("liest Mengen deutsch: Punkt als Tausender, Komma als Dezimal", () => {
    expect(parseAmount("10.000")).toBe(10000);
    expect(parseAmount("1.000.000")).toBe(1000000);
    expect(parseAmount("10000")).toBe(10000);
    expect(parseAmount("2,5")).toBe(2.5);
    expect(parseAmount("1.250,5")).toBe(1250.5);
    expect(parseAmount("2.5")).toBe(2.5);
    expect(parseAmount("")).toBeNull();
    expect(parseAmount("zehn")).toBeNull();
  });
});
