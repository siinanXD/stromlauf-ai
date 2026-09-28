/** Maschinenmodell "Schema": Datenabbildung fuer die Markierung aus dem meta-Event (ohne React). */

import type { MachineMap, MapZone } from "@/lib/api";
import { sameTag } from "./faults";

export interface Highlight {
  /** Zonen, in denen mindestens ein referenziertes Bauteil sitzt (id). */
  zoneIds: string[];
  /** Referenzierte Kennzeichen, die im Modell vorkommen (Schreibweise des Modells). */
  placed: string[];
  /** Referenzierte Kennzeichen ohne Platz im Modell. */
  unplaced: string[];
}

export function highlightFor(map: Pick<MachineMap, "zones"> | null | undefined, tags: string[]): Highlight {
  const wanted = tags.filter((t) => t.trim());
  if (!map || wanted.length === 0) return { zoneIds: [], placed: [], unplaced: wanted };
  const zoneIds: string[] = [];
  const placed = new Set<string>();
  for (const zone of map.zones) {
    let hit = false;
    for (const part of zone.parts) {
      if (wanted.some((t) => sameTag(t, part.tag))) {
        hit = true;
        placed.add(part.tag);
      }
    }
    if (hit) zoneIds.push(zone.id);
  }
  const unplaced = wanted.filter((t) => ![...placed].some((p) => sameTag(p, t)));
  return { zoneIds, placed: [...placed], unplaced };
}

export function isReferenced(tag: string, tags: string[]): boolean {
  return tags.some((t) => sameTag(t, tag));
}

/** Zone eines Kennzeichens (erste Fundstelle) oder null. */
export function zoneOf(map: Pick<MachineMap, "zones"> | null | undefined, tag: string): MapZone | null {
  return map?.zones.find((z) => z.parts.some((p) => sameTag(p.tag, tag))) ?? null;
}

/** Zonen mit referenzierten Bauteilen zuerst, sonst Reihenfolge des Backends (Einbauorte vor Anlage/Ohne Ort). */
export function orderZones(zones: MapZone[], tags: string[]): MapZone[] {
  if (tags.length === 0) return zones;
  const score = (z: MapZone) => (z.parts.some((p) => isReferenced(p.tag, tags)) ? 0 : 1);
  return [...zones].sort((a, b) => score(a) - score(b));
}

export function zoneTitle(zone: Pick<MapZone, "code" | "name">): string {
  if (zone.code === "?" || zone.code === "anlage") return zone.name;
  return zone.name ? `${zone.code} · ${zone.name}` : zone.code;
}
