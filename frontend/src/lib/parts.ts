import type { SignalPathData } from "./api";
import { relationVerb } from "./bbox";
import { sameTag } from "./faults";

/** Verbundene Bauteile: Nachbarn im Signalgraph, die selbst Betriebsmittel sind (ueber Klemmen hinweg eine Stufe).
 * Ein Anschluss wie die Spule -K1:A1 zaehlt als sein Geraet -K1 (Issue #98), sonst laege er zwischen Klemme und
 * Geraet und verdeckte die Nachbarn. Massgeblich ist die Knoten-ID, das Kennzeichen: label ist die Bezeichnung aus
 * der Stueckliste ("Foerdermotor 3~ 1,5 kW") und taugt weder fuer den Chip noch fuer das Verb. */
export function relatedParts(path: SignalPathData | null, tag: string): { tag: string; verb: string }[] {
  if (!path) return [];
  const byId = new Map(path.nodes.map((n) => [n.id, n]));
  const start = path.nodes.find((n) => sameTag(n.id, tag) || n.id === path.start);
  if (!start) return [];
  const owner = (id: string) => (byId.get(id)?.kind === "pin" ? id.split(":")[0] : id);
  const neighbors = (id: string) =>
    path.edges
      .map((e) => [owner(e.source), owner(e.target)])
      .filter(([source, target]) => source !== target && (source === id || target === id))
      .map(([source, target]) => (source === id ? target : source));
  const seen = new Map<string, string>();
  for (const first of neighbors(owner(start.id))) {
    const node = byId.get(first);
    if (!node) continue;
    const candidates = node.kind === "device" ? [node] : neighbors(first).map((n) => byId.get(n)).filter((n) => n && n.kind === "device");
    for (const device of candidates) {
      const id = device!.id;
      if (!sameTag(id, tag) && !seen.has(id)) seen.set(id, relationVerb(id));
    }
  }
  return [...seen.entries()].slice(0, 8).map(([t, verb]) => ({ tag: t, verb }));
}
