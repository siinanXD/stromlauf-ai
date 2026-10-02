import { describe, expect, it } from "vitest";

import { costText, eur, num } from "./format";

describe("format", () => {
  it("formatiert Zahlen deutsch", () => {
    expect(num(10000)).toBe("10.000");
    expect(num(8.407, 1)).toBe("8,4");
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
});
