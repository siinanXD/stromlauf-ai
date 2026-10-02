import { describe, expect, it } from "vitest";

import { levelOf, parentView, STOERFAELLE, viewFromParams, viewToQuery, type MachineView } from "./view";

const read = (query: string) => viewFromParams(new URLSearchParams(query));

describe("page routing (viewFromParams)", () => {
  it("opens Störfälle by default and with ?bereich=stoerfaelle", () => {
    expect(read("")).toEqual(STOERFAELLE);
    expect(read("bereich=stoerfaelle").area).toBe("stoerfaelle");
  });

  it("opens Aufbau with that tab for an old link ?tab=… without bereich", () => {
    expect(read("tab=schaltschrank")).toMatchObject({ area: "aufbau", tab: "schaltschrank" });
    expect(read("tab=fehler")).toMatchObject({ area: "aufbau", tab: "fehler" });
    // Befundkarte: ?tag=…&tab=signalweg
    expect(read("tag=-K1&tab=signalweg")).toMatchObject({ area: "aufbau", tab: "signalweg", tag: "-K1" });
  });

  it("sends the former chat tab to Störfälle", () => {
    expect(read("tab=chat")).toEqual(STOERFAELLE);
  });

  it("opens Aufbau for ?tag=… from search or 'im Werk zeigen', tab left to the page", () => {
    expect(read("tag=-M1")).toEqual({ area: "aufbau", tab: null, tag: "-M1", fall: null, detail: null });
  });

  it("reads ?bereich=aufbau&tab=… and ignores unknown tabs", () => {
    expect(read("bereich=aufbau&tab=kennzahlen")).toMatchObject({ area: "aufbau", tab: "kennzahlen" });
    expect(read("bereich=aufbau&tab=quatsch")).toMatchObject({ area: "aufbau", tab: null });
    expect(read("tab=quatsch")).toEqual(STOERFAELLE);
  });

  it("reads fall and detail only in Störfälle", () => {
    const detail = encodeURIComponent(JSON.stringify({ kind: "part", tag: "-K1" }));
    expect(read(`fall=conv-1&detail=${detail}`)).toMatchObject({ area: "stoerfaelle", fall: "conv-1", detail: { kind: "part", tag: "-K1" } });
    expect(read(`bereich=aufbau&fall=conv-1&detail=${detail}`)).toMatchObject({ area: "aufbau", fall: null, detail: null });
  });
});

describe("viewToQuery", () => {
  const views: MachineView[] = [
    STOERFAELLE,
    { ...STOERFAELLE, fall: "conv-1" },
    { ...STOERFAELLE, fall: "conv-1", detail: { kind: "signal", tag: "-K1" } },
    { ...STOERFAELLE, fall: "tmp-abc-1", detail: { kind: "plan", target: { documentId: "d", filename: "a.pdf", page: 2, reference: "/2.3" } } },
    { area: "aufbau", tab: "schaltschrank", tag: "-M1", fall: null, detail: null },
    { area: "aufbau", tab: null, tag: null, fall: null, detail: null },
  ];

  it.each(views.map((v) => [viewToQuery(v) || "(leer)", v] as const))("round-trips %s", (_, view) => {
    expect(read(viewToQuery(view).replace(/^\?/, ""))).toEqual(view);
  });

  it("leaves the default area out of the URL", () => {
    expect(viewToQuery(STOERFAELLE)).toBe("");
    expect(viewToQuery({ ...STOERFAELLE, fall: "conv-1" })).toBe("?fall=conv-1");
  });
});

describe("levels and back", () => {
  it("shows one level at a time below 1024 px", () => {
    expect(levelOf(STOERFAELLE)).toBe("list");
    expect(levelOf({ ...STOERFAELLE, fall: "conv-1" })).toBe("chat");
    expect(levelOf({ ...STOERFAELLE, fall: "conv-1", detail: { kind: "fault", faultId: "f1" } })).toBe("detail");
  });

  it("goes back one level: detail -> chat -> list; Aufbau -> Störfälle", () => {
    const detail: MachineView = { ...STOERFAELLE, fall: "conv-1", detail: { kind: "fault", faultId: "f1" } };
    expect(parentView(detail)).toEqual({ ...STOERFAELLE, fall: "conv-1" });
    expect(parentView(parentView(detail))).toEqual(STOERFAELLE);
    expect(parentView({ area: "aufbau", tab: "fehler", tag: null, fall: null, detail: null })).toEqual(STOERFAELLE);
  });
});
