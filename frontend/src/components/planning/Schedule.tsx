"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import type { CalcResult, CalcStation } from "@/lib/api";
import { minutesText, whenText } from "@/lib/format";
import { timeAxis } from "@/lib/timeline";

const ROW_H = 26;
const TOP = 24;
const BAR_H = 14;

const ms = (iso: string) => new Date(iso).getTime();

/** Zeilen: je Buero-Station eine, Rohpapier eine, je Linie eine, Verladung eine (Reihenfolge wie berechnet). */
function rowsOf(stations: CalcStation[]) {
  const rows: { key: string; label: string; stations: CalcStation[] }[] = [];
  for (const station of stations) {
    const key = station.group === "Büro" ? station.key : `${station.group}|${station.label}`;
    const label = station.group === "Rohpapier" ? "PM1 Rohpapier" : station.label;
    const row = rows.find((r) => r.key === key);
    if (row) row.stations.push(station);
    else rows.push({ key, label, stations: [station] });
  }
  return rows;
}

/** Zeitplan je Station: Balken ueber Kalenderzeit, geschlossene Zeiten schraffiert, Leerlauf gestaucht. */
export function Schedule({ result }: { result: CalcResult }) {
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(640);
  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    const observer = new ResizeObserver(([entry]) => setWidth(Math.max(240, Math.round(entry.contentRect.width))));
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  const labelW = width < 520 ? 104 : 136;
  const plotW = width - labelW - 10;
  const rows = useMemo(() => rowsOf(result.stations), [result.stations]);
  const axis = useMemo(
    () => timeAxis(result.stations.map((s) => ({ start: ms(s.start), end: ms(s.end) })), plotW),
    [result.stations, plotW],
  );
  const X = (iso: string) => labelW + axis.x(ms(iso));
  const height = TOP + rows.length * ROW_H + 6;
  const ready = X(result.ready_at);
  const bottleneck = result.summary.bottleneck;
  const [clock] = useState(() => Date.now());
  const now = clock >= axis.start && clock <= axis.end ? labelW + axis.x(clock) : null;

  return (
    <div ref={ref} className="w-full overflow-x-auto">
      <svg width={width} height={height} className="block border border-line bg-card" role="img" aria-label="Zeitplan je Station">
        <defs>
          <pattern id="closed-hatch" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <path d="M0 0V5" stroke="var(--border)" strokeWidth="1.2" />
          </pattern>
        </defs>

        {axis.breaks.map((b) => (
          <g key={b.x}>
            <rect x={labelW + b.x} y={0} width={b.w} height={height} fill="url(#closed-hatch)" />
            <text x={labelW + b.x + b.w / 2} y={12} textAnchor="middle" fontSize={11} className="fill-muted-foreground font-mono">
              {Math.round(b.minutes / 60)}h
            </text>
          </g>
        ))}
        {axis.ticks.map((tick) => (
          <g key={`${tick.x}-${tick.day}`}>
            <line x1={labelW + tick.x} x2={labelW + tick.x} y1={TOP - 6} y2={height} stroke={tick.day ? "#cdd5df" : "var(--grid)"} />
            {tick.label && (
              <text x={labelW + tick.x + 3} y={12} fontSize={11} className={tick.day ? "fill-foreground font-mono font-semibold" : "fill-muted-foreground font-mono"}>
                {tick.label}
              </text>
            )}
          </g>
        ))}
        <line x1={4} x2={width - 4} y1={TOP - 2} y2={TOP - 2} stroke="var(--border)" />

        {rows.map((row, index) => {
          const y = TOP + index * ROW_H;
          const calendar = row.stations[0].calendar;
          const closed = result.closed[calendar] ?? [];
          const max = labelW < 120 ? 14 : 19;
          return (
            <g key={row.key}>
              <line x1={4} x2={width - 4} y1={y + ROW_H} y2={y + ROW_H} stroke="var(--grid)" />
              <text x={6} y={y + 16} fontSize={11} className="fill-foreground">
                {row.label.length > max ? `${row.label.slice(0, max - 1)}…` : row.label}
              </text>
              {closed.map(([a, b]) => (
                <rect key={a} x={X(a)} y={y + 2} width={Math.max(0, X(b) - X(a))} height={ROW_H - 4} fill="url(#closed-hatch)" />
              ))}
              {row.stations.map((station) => {
                const x = X(station.start);
                const w = Math.max(2, X(station.end) - x);
                const isBottleneck = !!station.bottleneck && station.bottleneck === bottleneck;
                const short = station.bottleneck?.split(" ")[0];
                return (
                  <g key={station.key}>
                    <rect
                      x={x}
                      y={y + (ROW_H - BAR_H) / 2}
                      width={w}
                      height={BAR_H}
                      fill={station.group === "Rohpapier" && (station.position ?? 0) % 2 === 1 ? "var(--muted-foreground)" : "var(--primary)"}
                      stroke={isBottleneck ? "var(--line)" : "none"}
                      strokeWidth={1.5}
                    >
                      <title>
                        {`${station.label}: ${whenText(station.start)} – ${whenText(station.end)} (${minutesText(station.work_minutes)})\n${station.basis}`}
                      </title>
                    </rect>
                    {isBottleneck && w > 110 && (
                      <text x={x + 4} y={y + 17} fontSize={11} className="pointer-events-none fill-white font-mono">
                        Engpass {short}
                      </text>
                    )}
                    {!isBottleneck && station.group !== "Büro" && w < width - x - 70 && (
                      <text x={x + w + 4} y={y + 17} fontSize={11} className="pointer-events-none fill-muted-foreground font-mono">
                        {minutesText(station.work_minutes)}
                      </text>
                    )}
                  </g>
                );
              })}
            </g>
          );
        })}

        {now !== null && <line x1={now} x2={now} y1={TOP - 6} y2={height} stroke="var(--muted-foreground)" strokeDasharray="1 3" />}
        <line
          x1={ready}
          x2={ready}
          y1={TOP - 6}
          y2={height}
          stroke={result.meets_due === false ? "var(--foreground)" : "var(--ok)"}
          strokeWidth={1.5}
          strokeDasharray="3 2"
        />
      </svg>
    </div>
  );
}
