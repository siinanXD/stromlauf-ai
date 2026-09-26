/** Geometrie fuer Standortplan und Hallen-Baukasten: Linienbaender und verkleinertes Hallenlayout. */

import { HALL_KIND_LABELS, type HallKind, type SiteMachine } from "./api";

/** Groesse einer Maschinenkachel im Hallen-Baukasten (px). */
export const TILE = { w: 184, h: 96 };
/** Groesster Massstab im Mini-Plan, damit eine einzelne Maschine nicht die ganze Halle fuellt. */
export const MAX_MINI_SCALE = 0.6;

export interface Rect {
  x: number;
  y: number;
  w: number;
  h: number;
}
export interface Lane extends Rect {
  line: string;
}
export interface MiniTile extends Rect {
  id: string;
  line: string;
}

/** Huellrechteck je Linie (Reihenfolge des ersten Auftretens); oben Platz fuer die Beschriftung. */
export function laneBoxes(
  items: { line: string; x: number; y: number }[],
  tile: { w: number; h: number },
  pad = 16,
  header = 22,
): Lane[] {
  const bounds = new Map<string, { x0: number; y0: number; x1: number; y1: number }>();
  for (const { line, x, y } of items) {
    if (!line) continue;
    const box = bounds.get(line);
    if (!box) bounds.set(line, { x0: x, y0: y, x1: x + tile.w, y1: y + tile.h });
    else Object.assign(box, { x0: Math.min(box.x0, x), y0: Math.min(box.y0, y), x1: Math.max(box.x1, x + tile.w), y1: Math.max(box.y1, y + tile.h) });
  }
  return [...bounds].map(([line, b]) => ({
    line,
    x: b.x0 - pad,
    y: b.y0 - pad - header,
    w: b.x1 - b.x0 + 2 * pad,
    h: b.y1 - b.y0 + 2 * pad + header,
  }));
}

/** Hallenlayout verkleinert und zentriert in eine Flaeche `size` (Innenraum eines Hallenblocks). */
export function miniPlan(machines: SiteMachine[], size: { w: number; h: number }, inset = 8) {
  if (machines.length === 0) return { scale: 0, tiles: [] as MiniTile[], lanes: [] as Lane[] };
  const lanes = laneBoxes(machines.map((m) => ({ line: m.line, x: m.pos_x, y: m.pos_y })), TILE);
  const rects: Rect[] = [...lanes, ...machines.map((m) => ({ x: m.pos_x, y: m.pos_y, ...TILE }))];
  const x0 = Math.min(...rects.map((r) => r.x));
  const y0 = Math.min(...rects.map((r) => r.y));
  const bw = Math.max(...rects.map((r) => r.x + r.w)) - x0;
  const bh = Math.max(...rects.map((r) => r.y + r.h)) - y0;
  const scale = Math.max(0, Math.min((size.w - 2 * inset) / bw, (size.h - 2 * inset) / bh, MAX_MINI_SCALE));
  const ox = inset + (size.w - 2 * inset - bw * scale) / 2 - x0 * scale;
  const oy = inset + (size.h - 2 * inset - bh * scale) / 2 - y0 * scale;
  const place = (r: Rect): Rect => ({ x: ox + r.x * scale, y: oy + r.y * scale, w: r.w * scale, h: r.h * scale });
  return {
    scale,
    tiles: machines.map((m): MiniTile => ({ id: m.id, line: m.line, ...place({ x: m.pos_x, y: m.pos_y, ...TILE }) })),
    lanes: lanes.map((lane): Lane => ({ line: lane.line, ...place(lane) })),
  };
}

/**
 * Punkt auf dem Rand eines Blocks (Mittelpunkt x/y, Groesse w/h) in Richtung eines Zielpunkts.
 * Fuer Pfeile zwischen Hallen, die immer die naechste Wand treffen statt fester Griffe.
 */
export function borderPoint(box: Rect, toward: { x: number; y: number }): { x: number; y: number } {
  const dx = toward.x - box.x;
  const dy = toward.y - box.y;
  if (dx === 0 && dy === 0) return { x: box.x, y: box.y };
  const scale = Math.min(dx === 0 ? Infinity : box.w / 2 / Math.abs(dx), dy === 0 ? Infinity : box.h / 2 / Math.abs(dy));
  return { x: box.x + dx * scale, y: box.y + dy * scale };
}

/** Quelle einer Kennzahl als Link (nur gueltige http(s)-URL), sonst null fuer Klartext wie "Richtwert". */
export function sourceLink(source: string): { href: string; host: string } | null {
  if (!/^https?:\/\//.test(source)) return null;
  try {
    const url = new URL(source);
    if (!url.hostname) return null;
    return { href: source, host: url.hostname.replace(/^www\./, "") };
  } catch {
    return null;
  }
}

/** Kopfzeile eines Hallenblocks: "Art · Name", ohne doppelte Art und ohne Art bei allgemeiner Halle. */
export function hallTitle(hall: { kind: HallKind; name: string }): string {
  if (hall.kind === "generic") return hall.name;
  const kind = HALL_KIND_LABELS[hall.kind];
  return hall.name.toLowerCase().startsWith(kind.toLowerCase()) ? hall.name : `${kind} · ${hall.name}`;
}
