/** Rahmen auf Schaltschrankfotos: relative Koordinaten (0..1) <-> Pixel, Verschieben/Skalieren mit Grenzen. */

export interface Box {
  x: number;
  y: number;
  w: number;
  h: number;
}

export const MIN_SIZE = 0.01;

/** In den Bildbereich einpassen: Groesse mindestens MIN_SIZE, nie ueber den Rand hinaus. */
export function clampBox(box: Box): Box {
  const w = Math.min(1, Math.max(MIN_SIZE, box.w));
  const h = Math.min(1, Math.max(MIN_SIZE, box.h));
  const x = Math.min(1 - w, Math.max(0, box.x));
  const y = Math.min(1 - h, Math.max(0, box.y));
  return { x, y, w, h };
}

/** Relativ -> Pixel im gerenderten Bild. */
export function toPixels(box: Box, width: number, height: number): { left: number; top: number; width: number; height: number } {
  return { left: box.x * width, top: box.y * height, width: box.w * width, height: box.h * height };
}

/** Pixel (z. B. aus einem Pointer-Delta) -> relative Verschiebung. */
export function moveBy(box: Box, dxPx: number, dyPx: number, width: number, height: number): Box {
  if (width <= 0 || height <= 0) return box;
  return clampBox({ ...box, x: box.x + dxPx / width, y: box.y + dyPx / height });
}

export type Handle = "nw" | "ne" | "sw" | "se";

/** Ecke ziehen: die gegenueberliegende Ecke bleibt stehen. */
export function resizeBy(box: Box, handle: Handle, dxPx: number, dyPx: number, width: number, height: number): Box {
  if (width <= 0 || height <= 0) return box;
  const dx = dxPx / width;
  const dy = dyPx / height;
  let { x, y, w, h } = box;
  if (handle.includes("w")) {
    x += dx;
    w -= dx;
  } else w += dx;
  if (handle.includes("n")) {
    y += dy;
    h -= dy;
  } else h += dy;
  if (w < MIN_SIZE) {
    if (handle.includes("w")) x = box.x + box.w - MIN_SIZE;
    w = MIN_SIZE;
  }
  if (h < MIN_SIZE) {
    if (handle.includes("n")) y = box.y + box.h - MIN_SIZE;
    h = MIN_SIZE;
  }
  return clampBox({ x, y, w, h });
}

/** Tastatur: Pfeile verschieben um `step` (relativ), mit Shift skalieren. */
export function nudge(box: Box, key: string, shift: boolean, step = 0.005): Box | null {
  const delta: Record<string, [number, number]> = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] };
  const d = delta[key];
  if (!d) return null;
  if (shift) return clampBox({ ...box, w: box.w + d[0], h: box.h + d[1] });
  return clampBox({ ...box, x: box.x + d[0], y: box.y + d[1] });
}

export function sameBox(a: Box, b: Box, epsilon = 1e-6): boolean {
  return Math.abs(a.x - b.x) < epsilon && Math.abs(a.y - b.y) < epsilon && Math.abs(a.w - b.w) < epsilon && Math.abs(a.h - b.h) < epsilon;
}
