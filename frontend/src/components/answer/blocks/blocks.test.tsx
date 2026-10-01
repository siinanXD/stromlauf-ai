import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it } from "vitest";

import { AnswerView, type AnswerBlocksContext } from "@/components/chat/AnswerView";
import type { AnswerMeta, ChatMessage, FaultHits } from "@/lib/api";

import { BLOCK_ORDER, metaBlockData } from "../blockData";
import { clearFaultHits, seedFaultHits } from "../faultHitsStore";

const MACHINE = "m-fb01";
const SOURCE = "s-fb01";
const QUESTION = "Störung Motorschutz Förderband";

const SOURCES = [{ document_id: "d-plan", filename: "01_Stromlaufplan_FB-01.pdf", doc_type: "schematic", page: 3, section: "" }];
const TEXT = "## Kurzantwort\n\nSchütz -K1 fällt ab, wenn der Motorschutz -F2 auslöst [[01_Stromlaufplan_FB-01.pdf|/3.4]].\n\n## Prüfen\n\n1. -F2 zurücksetzen.\n2. Spule von -K1 messen.";

const OLD_META: AnswerMeta = {
  referenced_tags: ["-K1", "-F2"],
  citations: SOURCES,
  evidence: [
    { kind: "cabinet", cabinet_id: "c-1", cabinet_title: "Schaltschrank +ST1", hotspot_id: "hs1", tag: "-K1", label: "Hauptschütz", box: { x: 0.2, y: 0.3, w: 0.1, h: 0.12 }, confirmed: true },
    { kind: "page", document_id: "d-plan", filename: "01_Stromlaufplan_FB-01.pdf", doc_type: "schematic", page: 3, label: "S. 3" },
  ],
  citation_checks: [{ text: "[[01_Stromlaufplan_FB-01.pdf|/3.4]]", file: "01_Stromlaufplan_FB-01.pdf", locator: "/3.4", valid: true, checked: true, reason: "" }],
  citations_valid: { valid: 1, checked: 1, total: 1 },
};

const NEW_META: AnswerMeta = {
  ...OLD_META,
  part_kinds: { "-K1": "Schütz", "-F2": "Motorschutz" },
  signal_start: "-K1",
  plan_spots: [{ tag: "-K1", document_id: "d-plan", filename: "01_Stromlaufplan_FB-01.pdf", page: 3, sheet: 3, title: "Motor Förderband", column: 4 }],
};

const HITS: FaultHits = {
  faults: [{ id: "f1", machine_id: MACHINE, code: "E03", symptom: "Motorschutz ausgelöst", cause: "Überlast", fix: "-F2 zurücksetzen", doc_ref: "", tags: ["-F2"] }],
  experience: [{ machine_id: "m-2", machine_name: "Förderband FB-02", fault: { id: "f9", machine_id: "m-2", code: "", symptom: "Motorschutz fällt", cause: "", fix: "", doc_ref: "", tags: [] } }],
  incidents: [],
};

const blocks: AnswerBlocksContext = { machineId: MACHINE, sourceId: SOURCE, onOpenDetail: () => {} };

function answer(meta: AnswerMeta | undefined, extra: Partial<ChatMessage> = {}): ChatMessage {
  return { role: "assistant", content: TEXT, tool_calls: [], sources: SOURCES, meta, ...extra };
}

function render(message: ChatMessage, { streaming = false, question = QUESTION } = {}) {
  return renderToStaticMarkup(
    <AnswerView message={message} question={question} streaming={streaming} sourceIds={[SOURCE]} activeReference={null} onOpen={() => {}} blocks={blocks} />,
  );
}

/** Reihenfolge der Bloecke im HTML, wie data-block sie nennt. */
function order(html: string): string[] {
  return [...html.matchAll(/data-block="([a-z]+)"/g)].map((m) => m[1]);
}

beforeEach(() => clearFaultHits());

describe("answer blocks: order and omission", () => {
  it("renders all blocks in the fixed order of the spec", () => {
    seedFaultHits(MACHINE, QUESTION, HITS);
    const html = render(answer(NEW_META));
    expect(order(html)).toEqual(BLOCK_ORDER);
    expect(html).toContain("Fehlerliste");
    expect(html).toContain("Erfahrung");
    expect(html).toContain("kein Beleg für diese Maschine");
  });

  it("drops blocks without content: no fault hits, no plan spots, no cabinet evidence", () => {
    seedFaultHits(MACHINE, QUESTION, { faults: [], experience: [], incidents: [] });
    const html = render(answer({ ...NEW_META, plan_spots: [], evidence: [] }));
    expect(order(html)).toEqual(["text", "parts", "signal", "citations"]);
  });

  it("shows no fault block when the fault-hits request failed (old server, network)", () => {
    seedFaultHits(MACHINE, QUESTION, null);
    expect(order(render(answer(NEW_META)))[0]).toBe("text");
  });

  it("shows a block-shaped placeholder while fault hits load, the text right after it", () => {
    const html = render(answer(undefined, { content: "" }), { streaming: true });
    expect(order(html)).toEqual(["faults", "text"]);
    expect(html).toContain('aria-busy="true"');
  });

  it("shows only the fault block and the text while streaming", () => {
    seedFaultHits(MACHINE, QUESTION, HITS);
    expect(order(render(answer(NEW_META), { streaming: true }))).toEqual(["faults", "text"]);
  });

  it("names the source of each block", () => {
    seedFaultHits(MACHINE, QUESTION, HITS);
    const html = render(answer(NEW_META));
    expect(html).toContain("1 Eintrag dieser Maschine");
    expect(html).toContain("Kennzeichen-Index");
    expect(html).toContain("ab -K1");
    expect(html).toContain("01_Stromlaufplan_FB-01.pdf");
    expect(html).toContain("Schaltschrank +ST1");
    expect(html).toContain("Zitat-Prüfung");
  });
});

describe("old conversation without the new meta fields", () => {
  it("renders the answer without the new blocks and does not crash", () => {
    seedFaultHits(MACHINE, QUESTION, null);
    const html = render(answer(OLD_META));
    expect(order(html)).toEqual(["text", "cabinet", "citations"]);
    expect(html).toContain("Schütz");
    expect(html).not.toContain('data-block="parts"');
    expect(html).not.toContain('data-block="signal"');
    expect(html).not.toContain('data-block="plan"');
  });

  it("survives a meta object with missing or broken fields", () => {
    const broken = { referenced_tags: undefined, citations: [], evidence: undefined, plan_spots: [{ tag: "-K1" }], signal_start: 3 } as unknown as AnswerMeta;
    expect(() => render(answer(broken), { question: "" })).not.toThrow();
    expect(metaBlockData(broken, SOURCE)).toEqual({ parts: null, signal: null, plan: null, cabinet: null });
  });

  it("has no blocks at all without meta", () => {
    expect(metaBlockData(undefined, SOURCE)).toEqual({ parts: null, signal: null, plan: null, cabinet: null });
  });
});

describe("metaBlockData", () => {
  it("needs a source for the signal block and caps plan spots at 4", () => {
    const spots = Array.from({ length: 6 }, (_, i) => ({ ...NEW_META.plan_spots![0], tag: `-K${i}` }));
    const data = metaBlockData({ ...NEW_META, plan_spots: spots }, null);
    expect(data.signal).toBeNull();
    expect(data.plan).toHaveLength(4);
    expect(data.parts).toEqual({ tags: ["-K1", "-F2"], kinds: NEW_META.part_kinds });
    expect(data.cabinet).toHaveLength(1);
  });
});

describe("answer text", () => {
  it("turns referenced tags in the text into part buttons, but not inside citations", () => {
    seedFaultHits(MACHINE, QUESTION, null);
    const html = render(answer(NEW_META));
    expect(html).toContain('data-part-link="-K1"');
    expect(html).toContain('data-part-link="-F2"');
    expect(html).toContain("Stromlaufplan /3.4");
  });

  it("does not show the fact card in the machine chat any more", () => {
    seedFaultHits(MACHINE, QUESTION, null);
    expect(render(answer(NEW_META), { question: "-K1 zieht nicht an" })).not.toContain("BEFUNDKARTE");
  });
});
