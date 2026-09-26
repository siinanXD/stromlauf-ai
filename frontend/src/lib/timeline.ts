/** Zeitachse fuer den Zeitplan: linear, lange Leerlaeufe (z. B. Wochenende) als schmaler Bruch. */

const HOUR = 3_600_000;
const WEEKDAYS = ["So", "Mo", "Di", "Mi", "Do", "Fr", "Sa"];

export interface AxisBreak {
  x: number;
  w: number;
  minutes: number;
}
export interface AxisTick {
  x: number;
  label: string;
  day: boolean;
}
export interface TimeAxis {
  x: (t: number) => number;
  breaks: AxisBreak[];
  ticks: AxisTick[];
  start: number;
  end: number;
}

type Segment = { start: number; end: number; x0: number; w: number; compressed: boolean };

const pad = (n: number) => String(n).padStart(2, "0");
export const dayLabel = (d: Date) => `${WEEKDAYS[d.getDay()]} ${pad(d.getDate())}.${pad(d.getMonth() + 1)}.`;

/**
 * Zeit (ms) -> x (px) ueber `width`. Luecken ohne Aktivitaet ueber `gapMin` Minuten werden auf
 * `breakPx` gestaucht; innerhalb eines Bruchs bleibt die Abbildung monoton.
 */
export function timeAxis(
  spans: { start: number; end: number }[],
  width: number,
  opts: { gapMin?: number; breakPx?: number } = {},
): TimeAxis {
  const gap = (opts.gapMin ?? 360) * 60_000;
  const breakPx = opts.breakPx ?? 22;
  const sorted = spans.filter((s) => s.end >= s.start).sort((a, b) => a.start - b.start);
  if (sorted.length === 0) return { x: () => 0, breaks: [], ticks: [], start: 0, end: 0 };

  // Aktive Zeitraeume zusammenfassen, lange Luecken merken
  const active: { start: number; end: number }[] = [];
  for (const span of sorted) {
    const last = active[active.length - 1];
    if (last && span.start - last.end <= gap) last.end = Math.max(last.end, span.end);
    else active.push({ ...span });
  }
  const activeMs = active.reduce((sum, a) => sum + (a.end - a.start), 0) || 1;
  const breakCount = active.length - 1;
  const scale = Math.max(0, width - breakCount * breakPx) / activeMs;

  const segments: Segment[] = [];
  let x0 = 0;
  active.forEach((a, index) => {
    if (index > 0) {
      const previous = active[index - 1];
      segments.push({ start: previous.end, end: a.start, x0, w: breakPx, compressed: true });
      x0 += breakPx;
    }
    const w = (a.end - a.start) * scale;
    segments.push({ start: a.start, end: a.end, x0, w, compressed: false });
    x0 += w;
  });

  const x = (t: number) => {
    if (t <= segments[0].start) return 0;
    for (const segment of segments) {
      if (t <= segment.end) {
        const span = segment.end - segment.start || 1;
        return segment.x0 + ((t - segment.start) / span) * segment.w;
      }
    }
    return x0;
  };

  const ticks: AxisTick[] = [];
  const hourStep = 4 * HOUR * scale >= 28 ? 4 : 0;
  for (const segment of segments.filter((s) => !s.compressed)) {
    const first = new Date(segment.start);
    first.setMinutes(0, 0, 0);
    for (let t = first.getTime(); t <= segment.end; t += HOUR) {
      if (t < segment.start) continue;
      const d = new Date(t);
      if (d.getHours() === 0) ticks.push({ x: x(t), label: dayLabel(d), day: true });
      else if (hourStep && d.getHours() % hourStep === 0) ticks.push({ x: x(t), label: pad(d.getHours()), day: false });
    }
  }
  return {
    x,
    breaks: segments.filter((s) => s.compressed).map((s) => ({ x: s.x0, w: s.w, minutes: Math.round((s.end - s.start) / 60_000) })),
    ticks,
    start: sorted[0].start,
    end: Math.max(...sorted.map((s) => s.end)),
  };
}
