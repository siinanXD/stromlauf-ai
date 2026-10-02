import { describe, expect, it } from "vitest";

import { sourceLink } from "./specs";

describe("sourceLink", () => {
  it("macht aus einer URL einen Link mit Hostnamen", () => {
    expect(sourceLink("https://www.valmet.com/tissue/x")).toEqual({ href: "https://www.valmet.com/tissue/x", host: "valmet.com" });
  });
  it("laesst Text und kaputte URLs als Text stehen", () => {
    expect(sourceLink("Richtwert (keine Herstellerangabe)")).toBeNull();
    expect(sourceLink("https://")).toBeNull();
    expect(sourceLink("https://foo bar")).toBeNull();
  });
});
