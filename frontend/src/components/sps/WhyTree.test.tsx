import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { WhyData } from "@/lib/api";

import { WhyTree } from "./WhyTree";
import { buildWhyTree } from "./whyTreeLogik";

const data: WhyData = {
  target: { id: "A4.0", label: "A4.0", terminal: "-X3:1", device: "-K1" },
  networks: [
    {
      id: "FB10/NW2",
      ref: "FB 10 NW 2",
      title: "Motor",
      klartext: ["A4.0 ist an, wenn E0.0 und M1.0."],
      depth: 0,
      inputs: [
        { id: "E0.0", kind: "address", label: "E0.0", terminal: "-X1:5", device: "-S1", written_by: [] },
        { id: "M1.0", kind: "variable", label: "M1.0", terminal: null, device: null, written_by: ["FB10/NW1"] },
      ],
    },
    {
      id: "FB10/NW1",
      ref: "FB 10 NW 1",
      title: "Freigabe",
      klartext: [],
      depth: 1,
      inputs: [{ id: "M1.0", kind: "variable", label: "M1.0", terminal: null, device: null, written_by: ["FB10/NW2"] }],
    },
  ],
};

describe("buildWhyTree", () => {
  it("haengt schreibende Netzwerke unter den Eingang und bricht Zyklen ab", () => {
    const tree = buildWhyTree(data);

    expect(tree).toHaveLength(1);
    const merker = tree[0].inputs[1];
    expect(merker.writers.map((w) => w.network.id)).toEqual(["FB10/NW1"]);
    // NW 1 liest M1.0 von NW 2, das schon im Pfad steht
    expect(merker.writers[0].inputs[0].writers).toEqual([]);
  });
});

describe("WhyTree", () => {
  it("zeigt Eingaenge mit Klemme und Betriebsmittel als Schaltflaechen", () => {
    const html = renderToStaticMarkup(<WhyTree data={data} onOpenDetail={() => {}} />);

    expect(html).toContain('data-why-network="FB10/NW2"');
    expect(html).toContain('data-why-network="FB10/NW1"');
    expect(html).toContain("-X1:5");
    expect(html).toContain("-S1");
    expect(html).toContain("-X3:1");
    expect(html.split("<button").length - 1).toBe(4);
  });

  it("nennt einen Eingang ohne Klemme", () => {
    const lone: WhyData = {
      ...data,
      networks: [{ ...data.networks[0], inputs: [{ id: "E9.9", kind: "address", label: "E9.9", terminal: null, device: null, written_by: [] }] }],
    };
    expect(renderToStaticMarkup(<WhyTree data={lone} onOpenDetail={() => {}} />)).toContain("Keine Klemme im Plan gefunden");
  });
});
