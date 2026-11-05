import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { GruppenVorschlag } from "./GruppenVorschlag";
import type { Abgelegt, Gruppierung } from "./ordner";
import type { Vorschlaege } from "./vorschlag";

const ab = (pfad: string): Abgelegt => ({ file: new File([new Uint8Array(0)], pfad), pfad });
const g: Gruppierung = {
  gruppen: [{ id: "g1", name: "FB-01", quelle: "kennung", dateien: [ab("FB-01_Plan.pdf")] }],
  unzugeordnet: [ab("Lose.pdf"), ab("Andere.pdf")],
};

function render(vorschlaege: Vorschlaege, hinweis: string | null = null) {
  const onChange = vi.fn();
  const html = renderToStaticMarkup(
    <GruppenVorschlag gruppierung={g} vorschlaege={vorschlaege} vorschlagHinweis={hinweis} onChange={onChange} onStart={() => {}} onAbbrechen={() => {}} />,
  );
  return { html, onChange };
}

describe("GruppenVorschlag mit Ähnlichkeit", () => {
  it("zeigt Herkunft und Übernehmen, ordnet aber nichts von selbst zu", () => {
    const { html, onChange } = render({ "Lose.pdf": { gruppeId: "g1", wert: 0.83 } });
    expect(html).toContain("Ähnlichkeit 0,83");
    expect(html).toContain("FB-01");
    expect(html).toContain('aria-label="Lose.pdf nach FB-01 übernehmen"');
    expect(html).toContain("2 Dateien sind noch unzugeordnet.");
    expect(onChange).not.toHaveBeenCalled();
  });

  it("zeigt nur bei Dateien mit Vorschlag einen Knopf; die andere fragt wie bisher per Auswahl", () => {
    const { html } = render({ "Lose.pdf": { gruppeId: "g1", wert: 0.83 } });
    expect(html.match(/>Übernehmen</g)).toHaveLength(1);
    expect(html).toContain('aria-label="Andere.pdf verschieben nach"');
  });

  it("zeigt ohne Vorschlag keinen Knopf, die Auswahl bleibt", () => {
    const { html } = render({});
    expect(html).not.toContain(">Übernehmen<");
    expect(html).toContain('aria-label="Lose.pdf verschieben nach"');
  });

  it("ignoriert einen Vorschlag für eine Anlage, die es nicht mehr gibt", () => {
    expect(render({ "Lose.pdf": { gruppeId: "g9", wert: 0.9 } }).html).not.toContain(">Übernehmen<");
  });

  it("zeigt den Hinweis zur Prüfung", () => {
    expect(render({}, "Ähnlichkeit wird geprüft …").html).toContain("Ähnlichkeit wird geprüft …");
  });
});
