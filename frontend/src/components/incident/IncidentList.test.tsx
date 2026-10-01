import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import type { Conversation } from "@/lib/api";

import { handleComposerKey, IncidentList } from "./IncidentList";
import { addPending, confirmPending, countByOutcome, isTempId, markRetry, mergeServer, newTempId, outcomeOf, settleSend, visibleIncidents, type Incident } from "./incidents";

const SOURCE = "s-fb01";
const OLD: Conversation = { id: "conv-1", title: "Band steht nach Not-Halt", source_ids: [SOURCE], updated_at: "2026-09-29T10:00:00Z" };
const DONE: Conversation = { id: "conv-2", title: "Lichtschranke verschmutzt", source_ids: [SOURCE], updated_at: "2026-09-30T08:00:00Z", outcome: "resolved", finding: "Reflektor gereinigt" };

function key(k: string, shiftKey = false) {
  return { key: k, shiftKey, preventDefault: vi.fn() };
}

function render(incidents: Incident[], filter: "open" | "resolved" = "open", activeId: string | null = null) {
  return renderToStaticMarkup(
    <IncidentList
      incidents={incidents}
      loading={false}
      failed={false}
      onRetry={() => {}}
      activeId={activeId}
      filter={filter}
      onFilter={() => {}}
      onCreate={() => {}}
      onSelect={() => {}}
      onRetryIncident={() => {}}
    />,
  );
}

/** HTML des Listeneintrags mit dieser ID (li bis zum naechsten li). */
function itemHtml(html: string, id: string) {
  const start = html.lastIndexOf("<li>", html.indexOf(`data-incident="${id}"`));
  return html.slice(start, html.indexOf("</li>", start) + 5);
}

describe("IncidentList: Enter legt sofort an", () => {
  it("creates the incident synchronously on Enter, at the top and marked pending, before any server answer", () => {
    let list: Incident[] = [OLD];
    const create = vi.fn((text: string) => {
      list = addPending(list, { id: newTempId(), title: text, sourceId: SOURCE });
    });
    const event = key("Enter");

    expect(handleComposerKey(event, "  Störung Motorschutz Förderband ", create)).toBe(true);

    expect(event.preventDefault).toHaveBeenCalled();
    expect(create).toHaveBeenCalledWith("Störung Motorschutz Förderband");
    const shown = visibleIncidents(list, "open");
    expect(shown.map((i) => i.title)).toEqual(["Störung Motorschutz Förderband", OLD.title]);
    expect(isTempId(shown[0].id)).toBe(true);
    expect(shown[0]).toMatchObject({ pending: true, outcome: "open", source_ids: [SOURCE] });

    const html = render(list, "open", shown[0].id);
    expect(html).toContain('data-pending="true"');
    expect(html).toContain("wird angelegt");
    expect(html.indexOf("Störung Motorschutz Förderband")).toBeLessThan(html.indexOf(OLD.title));
    expect(html).toContain('aria-current="true"');
  });

  it("does not create on Shift+Enter, other keys, while composing or for empty text", () => {
    const create = vi.fn();
    expect(handleComposerKey(key("Enter", true), "Meldung", create)).toBe(false);
    expect(handleComposerKey(key("a"), "Meldung", create)).toBe(false);
    expect(handleComposerKey({ ...key("Enter"), nativeEvent: { isComposing: true } }, "Meldung", create)).toBe(false);
    expect(handleComposerKey(key("Enter"), "   ", create)).toBe(false);
    expect(create).not.toHaveBeenCalled();
  });

  it("replaces the preliminary id with the id from the conversation event and keeps the position", () => {
    const temp = newTempId();
    const list = addPending([OLD], { id: temp, title: "Band steht", sourceId: SOURCE });
    const confirmed = confirmPending(list, temp, { id: "conv-9", title: "Band steht (Server)" });
    expect(confirmed.map((i) => i.id)).toEqual(["conv-9", "conv-1"]);
    expect(confirmed[0]).toMatchObject({ title: "Band steht (Server)", pending: false });
    expect(confirmPending(list, "tmp-unbekannt", { id: "x" })).toBe(list);
  });

  it("keeps entries created in this session when an older server list does not know them yet", () => {
    const temp = newTempId();
    const list = addPending([OLD], { id: temp, title: "Neu", sourceId: SOURCE });
    expect(mergeServer(list, [OLD, DONE]).map((i) => i.id)).toEqual([temp, "conv-1", "conv-2"]);
    const confirmed = confirmPending(list, temp, { id: "conv-9" });
    expect(mergeServer(confirmed, [{ ...OLD }, { id: "conv-9", title: "Neu", source_ids: [SOURCE], updated_at: "2026-10-01T09:00:00Z" }]).map((i) => i.id)).toEqual(["conv-1", "conv-9"]);
  });
});

describe("filter, order and old servers", () => {
  it("treats a missing outcome (server before the incident fields) as open", () => {
    expect(outcomeOf(OLD)).toBe("open");
    expect(outcomeOf(DONE)).toBe("resolved");
    expect(countByOutcome([OLD, DONE])).toEqual({ open: 1, resolved: 1 });
  });

  it("filters open and resolved, newest state first, and searches title and finding", () => {
    const newer: Conversation = { ...OLD, id: "conv-3", title: "Motor brummt", updated_at: "2026-09-30T12:00:00Z" };
    expect(visibleIncidents([OLD, newer, DONE], "open").map((i) => i.id)).toEqual(["conv-3", "conv-1"]);
    expect(visibleIncidents([OLD, newer, DONE], "resolved").map((i) => i.id)).toEqual(["conv-2"]);
    expect(visibleIncidents([OLD, DONE], "resolved", "reflektor").map((i) => i.id)).toEqual(["conv-2"]);
    expect(visibleIncidents([OLD, DONE], "resolved", "motor")).toEqual([]);
  });

  it("shows the finding of resolved incidents and an empty state with the next action", () => {
    expect(render([DONE], "resolved")).toContain("Befund: Reflektor gereinigt");
    const empty = render([], "open");
    expect(empty).toContain("Keine offenen Störfälle");
    expect(empty).toContain("drücke Enter");
    // Leer ist nie rot
    const emptyClass = empty.match(/<p class="([^"]*)" data-testid="incidents-empty"/)?.[1] ?? "";
    expect(emptyClass).toContain("text-muted-foreground");
    expect(emptyClass).not.toMatch(/danger|destructive/);
  });
});

describe("Stoerfall nicht angelegt (Fehler vor dem Ereignis conversation)", () => {
  const temp = "tmp-test-1";
  const pending = addPending([OLD], { id: temp, title: "Störung Motorschutz Förderband", sourceId: SOURCE });

  it("stops the spinner and marks the entry 'nicht angelegt', keeping its text", () => {
    const failed = settleSend(pending, temp, null);
    expect(failed[0]).toMatchObject({ id: temp, title: "Störung Motorschutz Förderband", pending: false, failed: true });

    const item = itemHtml(render(failed), temp);
    expect(item).toContain("nicht angelegt");
    expect(item).toContain("Störung Motorschutz Förderband");
    expect(item).not.toContain("animate-spin");
    expect(item).not.toContain("wird angelegt");
    expect(item).toContain("Erneut versuchen");
    // nicht als Ganzes rot: nur die Statuszeile
    const button = item.match(/<button type="button"[^>]*data-incident[^>]*class="([^"]*)"/)?.[1] ?? "";
    expect(button).not.toMatch(/danger|destructive/);
    expect(item).toMatch(/<span class="block text-xs text-danger">nicht angelegt<\/span>/);
  });

  it("leaves created incidents and follow-up errors alone", () => {
    expect(settleSend(pending, temp, "conv-9")).toBe(pending);
    expect(settleSend([OLD], "conv-1", null)).toEqual([OLD]);
  });

  it("goes back to 'wird angelegt' on retry and stays in the list until the server knows it", () => {
    const failed = settleSend(pending, temp, null);
    expect(markRetry(failed, temp)[0]).toMatchObject({ pending: true, failed: false });
    expect(mergeServer(failed, [OLD]).map((i) => i.id)).toEqual([temp, "conv-1"]);
  });
});
