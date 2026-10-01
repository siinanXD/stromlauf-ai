import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { Conversation } from "@/lib/api";

import { addPending, settleSend } from "./incidents";
import { IncidentRail, listColumnLayout, railInitials } from "./IncidentRail";

const SOURCE = "s-fb01";
const OPEN: Conversation = { id: "conv-1", title: "-K1 zieht nicht an", source_ids: [SOURCE], updated_at: "2026-09-29T10:00:00Z", outcome: "open" };
const OTHER: Conversation = { id: "conv-3", title: "Störung Motorschutz Förderband", source_ids: [SOURCE], updated_at: "2026-09-30T10:00:00Z" };

describe("list column below 1280 px with the detail open", () => {
  it("collapses to a narrow rail between 1024 and 1279 px and keeps the full list from 1280 px", () => {
    const open = listColumnLayout("detail", true);
    expect(open.rail).toBe(true);
    expect(open.column).toContain("lg:w-[68px]");
    expect(open.column).toContain("xl:w-[260px]");
    expect(open.railClass).toContain("lg:flex");
    expect(open.railClass).toContain("xl:hidden");
    expect(open.listClass).toContain("lg:hidden");
    expect(open.listClass).toContain("xl:flex");
  });

  it("expands again when the detail closes", () => {
    const closed = listColumnLayout("chat", false);
    expect(closed.rail).toBe(false);
    expect(closed.column).toContain("lg:w-[260px]");
    expect(closed.column).not.toContain("lg:w-[68px]");
    expect(closed.listClass).not.toContain("lg:hidden");
  });

  it("shows only one level below 1024 px", () => {
    expect(listColumnLayout("list", false).column).toMatch(/(^| )flex( |$)/);
    expect(listColumnLayout("detail", true).column).toMatch(/(^| )hidden( |$)/);
  });
});

describe("IncidentRail", () => {
  it("names each incident with title and state, shows initials and a state symbol, 44 px targets", () => {
    const list = settleSend(addPending([OPEN, OTHER], { id: "tmp-r-1", title: "Band steht", sourceId: SOURCE }), "tmp-r-1", null);
    const html = renderToStaticMarkup(<IncidentRail incidents={list} filter="open" activeId="conv-1" onSelect={() => {}} onExpand={() => {}} />);
    expect(html).toContain('aria-label="-K1 zieht nicht an, Offen"');
    expect(html).toContain('title="-K1 zieht nicht an"');
    expect(html).toContain('aria-label="Band steht, nicht angelegt"');
    expect(html).toMatch(/aria-current="true"[^>]*data-incident="conv-1"/);
    expect(html).toContain(">-K<");
    expect(html).toContain(">ST<");
    const buttons = [...html.matchAll(/<button [^>]*class="([^"]*)"/g)].map((m) => m[1]);
    expect(buttons.length).toBe(4);
    for (const cls of buttons) expect(cls).toContain("size-11");
    expect(html).toContain("Störfall-Liste zeigen");
  });

  it("builds initials from the first two visible characters", () => {
    expect(railInitials("-K1 zieht nicht an")).toBe("-K");
    expect(railInitials("  störung")).toBe("ST");
    expect(railInitials("")).toBe("?");
  });
});
