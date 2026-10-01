import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { SignalMainResult } from "@/lib/api";

import { emptyNextText, emptyReasonText, usdText } from "./SignalEmpty";
import { COMPACT_STEPS, SignalViewBody, type SignalLoad } from "./SignalView";
import { conveyor, mainEdge, mainNode } from "./signalTestData";

const noop = () => {};
const count = (html: string, attribute: string) => html.split(attribute).length - 1;
const text = (html: string) => html.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ");

function render(load: SignalLoad, options: { variant?: "compact" | "auto"; wide?: boolean; tag?: string } = {}) {
  return renderToStaticMarkup(
    <SignalViewBody
      sourceId="src-1"
      tag={options.tag ?? "-K1"}
      variant={options.variant ?? "auto"}
      wide={options.wide ?? false}
      load={load}
      onOpenDetail={noop}
      onFollow={noop}
      onRetry={noop}
    />,
  );
}

const done = (result: SignalMainResult): SignalLoad => ({ status: "done", result });
/** Rot nur fuer Fehler und Not-Halt: der leere Zustand nutzt keine dieser Klassen. */
const RED = /destructive|danger|text-red|bg-red|border-red/;

describe("SignalView: leerer Zustand", () => {
  it("nennt bei unknown_tag den Grund als Satz, ohne 404-Text und ohne Rot", () => {
    const html = render(done({ ok: false, reason: "unknown_tag", message: "404: -Q1 kommt im Klemmenplan nicht vor" }), { tag: "-Q1" });

    expect(html).toContain('data-signal-empty="unknown_tag"');
    expect(text(html)).toContain("-Q1 kommt im Signalweg nicht vor.");
    expect(html).not.toContain("404");
    expect(html).not.toMatch(RED);
    expect(count(html, "data-signal-step=")).toBe(0);
  });

  it("nennt bei no_sources, dass weder Tabellen noch Leitungen da sind", () => {
    const html = render(done({ ok: false, reason: "no_sources", message: "" }), { variant: "compact", tag: "-Q1" });
    expect(text(html)).toContain("Keine Tabellen und keine Leitungen im Plan gefunden.");
    expect(html).not.toMatch(RED);
  });

  it("zeigt auch einen Hauptweg ohne Knoten als leeren Zustand", () => {
    const empty = { ...conveyor(), nodes: [], edges: [] };
    const html = render(done({ ok: true, data: empty }), { tag: "-Q1" });
    expect(text(html)).toContain("-Q1 kommt im Signalweg nicht vor.");
  });

  it("schlaegt die naechste Aktion nach Grund und Planseite vor", () => {
    const plan = { documentId: "doc-1", filename: "plan.pdf", page: 1 };
    expect(emptyNextText("unknown_tag", undefined)).toBeNull();
    expect(emptyNextText("unknown_tag", plan)).toBe("Im Stromlaufplan nachsehen, wo es steht.");
    expect(emptyNextText("no_sources", null)).toContain("Klemmenplan, ein SPS-Programm oder ein Stromlaufplan mit Leitungen");
    expect(emptyReasonText("unknown_tag", "-Q1")).toBe("-Q1 kommt im Signalweg nicht vor.");
  });

  it("schreibt Kosten in USD deutsch und rundet nichts auf null", () => {
    expect(usdText(0.123)).toBe("0,12");
    expect(usdText(1.5)).toBe("1,50");
    expect(usdText(0.004)).toBe("unter 0,01");
  });
});

describe("SignalView: compact", () => {
  it(`zeigt hoechstens ${COMPACT_STEPS} Hauptwegknoten und den Link „ganz zeigen“`, () => {
    const html = render(done({ ok: true, data: conveyor() }), { variant: "compact" });

    expect(COMPACT_STEPS).toBe(5);
    expect(count(html, "data-signal-step=")).toBe(5);
    expect(html).toContain('data-signal-step="-K1"');
    expect(text(html)).toContain("… 3 Schritte davor");
    expect(text(html)).toContain("ganz zeigen");
    expect(html).not.toContain("weiter verfolgen");
  });

  it("zeigt einen kurzen Hauptweg ganz", () => {
    const data = {
      ...conveyor(),
      start: "-S1",
      nodes: [mainNode("-S1", "device", "feld", 0), mainNode("-X1:1", "terminal", "klemme_vor", 1), mainNode("E0.0", "address", "sps_eingang", 2)],
      edges: [mainEdge("-S1", "-X1:1"), mainEdge("-X1:1", "E0.0")],
    };
    const html = render(done({ ok: true, data }), { variant: "compact", tag: "-S1" });
    expect(count(html, "data-signal-step=")).toBe(3);
    expect(text(html)).not.toContain("davor");
  });
});

describe("SignalView: auto", () => {
  it("zeigt unter 1024 px die ganze Kette mit Legende und Weiterverfolgen", () => {
    const html = render(done({ ok: true, data: conveyor() }), { wide: false });

    expect(count(html, "data-signal-step=")).toBe(8);
    expect(text(html)).toContain("Lage im Plan oder Modell");
    expect(html).toContain("weiter verfolgen");
    expect(text(html)).not.toContain("ganz zeigen");
  });

  it("laedt ab 1024 px die Grafik erst im Browser und zeigt bis dahin einen Platzhalter, keine Kette", () => {
    const html = render(done({ ok: true, data: conveyor() }), { wide: true });

    expect(html).toContain("Grafik wird geladen");
    expect(count(html, "data-signal-step=")).toBe(0);
  });

  it("bietet beim Ladefehler „Erneut versuchen“ ohne Entwicklertext", () => {
    const html = render({ status: "error" });
    expect(text(html)).toContain("Signalweg konnte nicht geladen werden.");
    expect(text(html)).toContain("Erneut versuchen");
  });

  it("zeigt beim Laden Platzhalter in Blockform", () => {
    const html = render({ status: "loading" });
    expect(html).toContain('aria-busy="true"');
  });
});
