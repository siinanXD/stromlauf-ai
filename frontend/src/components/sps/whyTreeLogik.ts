import type { WhyData, WhyInput, WhyNetwork } from "@/lib/api";

/** Ein Netzwerk im Bedingungsbaum; seine Eingaenge tragen die Netzwerke, die sie schreiben, als Kinder. */
export interface WhyNode {
  network: WhyNetwork;
  inputs: { input: WhyInput; writers: WhyNode[] }[];
}

/**
 * Macht aus der flachen Liste von `GET /api/awl/why` einen Baum: Wurzeln sind die Netzwerke, die den Ausgang
 * schreiben (Tiefe 0), darunter je Eingang die Netzwerke aus `written_by`. Jedes Netzwerk steht nur einmal im Pfad,
 * ein Zyklus (Merker, der sich selbst haelt) endet ohne Kinder.
 */
export function buildWhyTree(data: WhyData): WhyNode[] {
  const byId = new Map(data.networks.map((n) => [n.id, n]));

  function node(network: WhyNetwork, path: Set<string>): WhyNode {
    const next = new Set(path).add(network.id);
    return {
      network,
      inputs: network.inputs.map((input) => ({
        input,
        writers: input.written_by
          .filter((id) => byId.has(id) && !next.has(id))
          .map((id) => node(byId.get(id)!, next)),
      })),
    };
  }

  return data.networks.filter((n) => n.depth === 0).map((n) => node(n, new Set()));
}
