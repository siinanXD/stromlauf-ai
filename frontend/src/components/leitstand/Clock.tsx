"use client";

import { Pause, Play, RotateCcw } from "lucide-react";

import { whenText } from "@/lib/format";
import { dayLabel } from "@/lib/timeline";

export const SPEEDS = [
  { label: "1 h/s", value: 3_600_000 },
  { label: "6 h/s", value: 6 * 3_600_000 },
  { label: "1 Tag/s", value: 24 * 3_600_000 },
];

const DAY = 86_400_000;

/** Simulationsuhr: Zeit, Abspielen/Pause, Tempo, Schieberegler mit Tagesmarken und Auftragseingaengen. */
export function Clock({
  start,
  end,
  time,
  playing,
  speed,
  arrivals,
  onTime,
  onPlaying,
  onSpeed,
}: {
  start: number;
  end: number;
  time: number;
  playing: boolean;
  speed: number;
  arrivals: { key: string; t: number }[];
  onTime: (t: number) => void;
  onPlaying: (playing: boolean) => void;
  onSpeed: (speed: number) => void;
}) {
  const span = Math.max(1, end - start);
  const first = new Date(start);
  first.setHours(0, 0, 0, 0);
  const days: number[] = [];
  for (let d = first.getTime() + DAY; d < end; d += DAY) days.push(d);
  const pct = (t: number) => `${((t - start) / span) * 100}%`;

  return (
    <div className="space-y-1.5 border-b border-border bg-card px-4 py-2.5">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <span className="font-mono text-xl font-semibold uppercase">{whenText(toLocalIso(time))}</span>
        <div className="ml-auto flex items-center gap-1.5">
          <button
            type="button"
            aria-label={playing ? "Pause" : "Abspielen"}
            onClick={() => {
              if (!playing && time >= end) onTime(start);
              onPlaying(!playing);
            }}
            className="grid size-8 place-items-center border border-line bg-primary text-primary-foreground hover:bg-primary/90"
          >
            {playing ? <Pause className="size-4" /> : <Play className="size-4" />}
          </button>
          <button
            type="button"
            aria-label="Zum Anfang"
            onClick={() => onTime(start)}
            className="grid size-8 place-items-center border border-line bg-card hover:border-primary"
          >
            <RotateCcw className="size-3.5" />
          </button>
          <select
            aria-label="Tempo"
            value={speed}
            onChange={(e) => onSpeed(Number(e.target.value))}
            className="h-8 border border-border bg-background px-1.5 text-sm"
          >
            {SPEEDS.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </div>
      </div>
      <div className="relative pt-2">
        {arrivals.map((a) => (
          <span key={a.key} className="absolute top-0 h-1.5 w-px bg-muted-foreground" style={{ left: pct(a.t) }} />
        ))}
        <input
          type="range"
          aria-label="Simulationszeit"
          aria-valuetext={whenText(toLocalIso(time))}
          min={start}
          max={end}
          step={60_000}
          value={time}
          onChange={(e) => {
            onPlaying(false);
            onTime(Number(e.target.value));
          }}
          className="w-full accent-[var(--primary)]"
        />
        <div className="relative h-4 font-mono text-[11px] text-muted-foreground">
          {days.map((d) => (
            <span key={d} className="absolute -translate-x-1/2 whitespace-nowrap" style={{ left: pct(d) }}>
              {dayLabel(new Date(d)).slice(0, 5)}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

/** ms -> lokale ISO-Zeit "YYYY-MM-DDTHH:MM" (whenText erwartet Ortszeit). */
export function toLocalIso(t: number): string {
  const d = new Date(t);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
