import { describe, expect, it } from "vitest";

import { cn, TEXT_STYLES } from "./utils";

describe("cn mit den Figma-Textstilen", () => {
  it("haelt Textstil und Textfarbe nebeneinander", () => {
    expect(cn("text-footnote", "text-muted-foreground")).toBe("text-footnote text-muted-foreground");
    expect(cn("text-subhead font-semibold", "text-primary-foreground")).toBe("text-subhead font-semibold text-primary-foreground");
  });

  it("ersetzt einen Textstil durch einen anderen, wie Tailwind-Groessen", () => {
    expect(cn("text-footnote", "text-subhead")).toBe("text-subhead");
    expect(cn("text-sm", "text-body")).toBe("text-body");
    expect(cn("text-large-title md:text-title-2", "text-headline")).toBe("md:text-title-2 text-headline");
  });

  it("kennt jeden Textstil aus globals.css", () => {
    for (const style of TEXT_STYLES) expect(cn(`text-${style}`, "text-foreground")).toBe(`text-${style} text-foreground`);
  });

  it("behandelt den Kartenschatten als Schatten, nicht als Schattenfarbe", () => {
    expect(cn("shadow-sm", "shadow-card")).toBe("shadow-card");
  });
});
