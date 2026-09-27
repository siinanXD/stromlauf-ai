import type { Cabinet, Fault, Layout } from "@/lib/api";

/** Kennzeichen vergleichen, Schreibweise egal: "-K12", "K12", " -k12 " sind gleich. */
export function sameTag(a: string, b: string): boolean {
  const norm = (s: string) => s.replace(/\s+/g, "").toUpperCase().replace(/^-/, "");
  const x = norm(a);
  const y = norm(b);
  return x.length > 0 && x === y;
}

export function matchesAny(tag: string, tags: string[]): boolean {
  return tags.some((t) => sameTag(t, tag));
}

export interface FaultHits {
  tags: string[];
  /** Teile der Draufsicht mit einem der Kennzeichen */
  partIds: string[];
  /** Hotspots in Schaltschrankbildern */
  hotspotIds: string[];
  /** Kennzeichen, die weder Draufsicht noch Schaltschrank kennen */
  unplaced: string[];
}

/** Wo ein Fehlereintrag sichtbar wird: Teile in der Draufsicht, Bauteile in Schaltschrankfotos. */
export function faultHits(fault: Pick<Fault, "tags">, layout: Layout | null | undefined, cabinets: Pick<Cabinet, "hotspots">[]): FaultHits {
  const tags = fault.tags.filter((t) => t.trim());
  const partIds = (layout?.parts ?? []).filter((p) => matchesAny(p.tag, tags)).map((p) => p.id);
  const hotspotIds = cabinets.flatMap((c) => c.hotspots.filter((h) => matchesAny(h.tag, tags)).map((h) => h.id));
  const placed = new Set<string>();
  for (const p of layout?.parts ?? []) if (matchesAny(p.tag, tags)) placed.add(tags.find((t) => sameTag(t, p.tag))!);
  for (const c of cabinets) for (const h of c.hotspots) if (matchesAny(h.tag, tags)) placed.add(tags.find((t) => sameTag(t, h.tag))!);
  return { tags, partIds, hotspotIds, unplaced: tags.filter((t) => !placed.has(t)) };
}
