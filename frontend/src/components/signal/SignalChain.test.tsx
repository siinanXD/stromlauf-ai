import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { onlyProven, provenanceOf } from "./provenance";
import { SignalChain, chainModel } from "./SignalChain";
import { conveyor } from "./signalTestData";

const noop = () => {};
const count = (html: string, attribute: string) => html.split(attribute).length - 1;
/** Sichtbarer Text ohne Tags, Leerraum zusammengefasst. */
const text = (html: string) => html.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ");

describe("chainModel", () => {
  it("haengt Abzweige an ihren Hauptwegknoten und die Kante davor an jeden Schritt", () => {
    const model = chainModel(conveyor());

    expect(model.steps.map((s) => s.node.id)).toEqual(["-S1", "-X1:3", "E0.3", "FC 1/NW2", "A4.0", "-X3:9", "-K1", "-M1"]);
    expect(model.steps[0].incoming).toBeNull();
    expect(model.steps[6].incoming).toMatchObject({ source: "-X3:9", target: "-K1", pins: { to: "A1" } });
    const k1 = model.steps[6];
    expect(k1.branches.map((b) => b.node.id)).toEqual(["-H1", "-X3:10"]);
    expect(k1.branches[1].edge).toMatchObject({ directed: false, via: ["modell"] });
    expect(model.steps.filter((s) => s.node.id !== "-K1").every((s) => s.branches.length === 0)).toBe(true);
  });

  it("zeigt mit limit einen Ausschnitt um den Start und zaehlt den Rest", () => {
    const model = chainModel(conveyor(), 5);
    expect(model.steps.map((s) => s.node.id)).toEqual(["FC 1/NW2", "A4.0", "-X3:9", "-K1", "-M1"]);
    expect([model.hiddenBefore, model.hiddenAfter]).toEqual([3, 0]);

    const atStart = chainModel({ ...conveyor(), start: "-S1" }, 5);
    expect(atStart.steps.map((s) => s.node.id)).toEqual(["-S1", "-X1:3", "E0.3", "FC 1/NW2", "A4.0"]);
    expect([atStart.hiddenBefore, atStart.hiddenAfter]).toEqual([0, 3]);
  });
});

describe("SignalChain: Abzweige aufklappen", () => {
  it("zeigt zugeklappt nur den Zaehler", () => {
    const html = renderToStaticMarkup(<SignalChain data={conveyor()} onOpenPart={noop} />);

    expect(count(html, "data-signal-step=")).toBe(8);
    expect(text(html)).toContain("2 Abzweige");
    expect(html).toContain('aria-expanded="false"');
    expect(count(html, "data-signal-branch=")).toBe(0);
  });

  it("zeigt aufgeklappt die Abzweige unter ihrem Knoten, mit Richtung und Herkunft", () => {
    const html = renderToStaticMarkup(<SignalChain data={conveyor()} onOpenPart={noop} defaultOpen={["-K1"]} />);
    const plain = text(html);

    expect(html).toContain('aria-expanded="true"');
    expect(count(html, "data-signal-branch=")).toBe(2);
    expect(plain).toContain("Meldeleuchte Band läuft");
    expect(plain).toContain("kommt von -K1 · Leitung im Plan · von 14");
    expect(plain).toContain("verbunden mit -K1, Richtung offen · Modell");
    // Die Abzweige stehen im Schritt von -K1, nicht danach
    const k1 = html.indexOf('data-signal-step="-K1"');
    const m1 = html.indexOf('data-signal-step="-M1"');
    expect(html.indexOf('data-signal-branch="-H1"')).toBeGreaterThan(k1);
    expect(html.indexOf('data-signal-branch="-H1"')).toBeLessThan(m1);
  });

  it("meldet Abzweige ohne Angaben, wenn der Zaehler mehr nennt als geliefert", () => {
    const data = conveyor();
    data.nodes = data.nodes.map((n) => (n.id === "-S1" ? { ...n, branches: 1 } : n));
    const html = renderToStaticMarkup(<SignalChain data={data} onOpenPart={noop} defaultOpen={["-S1"]} />);
    expect(text(html)).toContain("1 Abzweig ohne weitere Angaben");
  });
});

describe("SignalChain: Herkunft als Text", () => {
  it("nennt je Verbindung die Herkunft und die Anschluesse, nicht nur ein Linienmuster", () => {
    const plain = text(renderToStaticMarkup(<SignalChain data={conveyor()} onOpenPart={noop} />));

    expect(plain).toContain("Herkunft: Leitung im Plan · von 13");
    expect(plain).toContain("Herkunft: Klemmenplan");
    expect(plain).toContain("Herkunft: SPS-Programm");
    expect(plain).toContain("Herkunft: Symboltabelle, Leitung im Plan");
    expect(plain).toContain("Herkunft: Klemmenplan · an A1");
    expect(plain).toContain("Herkunft: Lage im Plan · von 2");
  });

  it("zeigt Kennzeichen, Klartext, Spalte und Blatt je Zeile", () => {
    const plain = text(renderToStaticMarkup(<SignalChain data={conveyor()} onOpenPart={noop} />));
    expect(plain).toContain("-K1 Schaltgerät Start Schütz Förderband Blatt 3 · Spalte 5");
    expect(plain).toContain("FC 1 NW 2 Programm Band schalten");
  });

  it("bietet „Von hier weiter verfolgen“ nur mit onFollow und nicht am Start", () => {
    const without = renderToStaticMarkup(<SignalChain data={conveyor()} onOpenPart={noop} />);
    expect(without).not.toContain("weiter verfolgen");

    const html = renderToStaticMarkup(<SignalChain data={conveyor()} onOpenPart={noop} onFollow={noop} />);
    expect(html).toContain('aria-label="Von -S1 weiter verfolgen"');
    expect(html).not.toContain('aria-label="Von -K1 weiter verfolgen"');
  });
});

describe("Herkunftsstufen", () => {
  it("stuft nach der staerksten Herkunft ein", () => {
    expect(provenanceOf(["symboltabelle", "leitung"])).toBe("beleg");
    expect(provenanceOf(["leitung", "modell"])).toBe("leitung");
    expect(provenanceOf(["lage"])).toBe("lage");
    expect(provenanceOf(["modell"])).toBe("lage");
    expect(provenanceOf([])).toBe("lage");
  });

  it("nur Belegtes: behaelt Tabellen- und Programmkanten, ihre Knoten und den Start", () => {
    const proven = onlyProven(conveyor());
    expect(proven.edges.map((e) => `${e.source}>${e.target}`)).toEqual([
      "-X1:3>E0.3",
      "E0.3>FC 1/NW2",
      "FC 1/NW2>A4.0",
      "A4.0>-X3:9",
      "-X3:9>-K1",
    ]);
    expect(proven.nodes.map((n) => n.id).sort()).toEqual(["-K1", "-X1:3", "-X3:9", "A4.0", "E0.3", "FC 1/NW2"].sort());
  });
});
