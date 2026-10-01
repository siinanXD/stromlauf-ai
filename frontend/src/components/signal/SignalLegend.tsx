import { cn } from "@/lib/utils";

import { PROVENANCE_CAP, PROVENANCE_DASH, PROVENANCE_LABELS, PROVENANCE_ORDER, type Provenance } from "./provenance";

/** Kurzes Linienmuster einer Herkunftsstufe, waagrecht oder senkrecht (Kette). */
export function ProvenanceLine({ provenance, vertical = false, className }: { provenance: Provenance; vertical?: boolean; className?: string }) {
  const [w, h] = vertical ? [8, 28] : [36, 8];
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} aria-hidden className={cn("shrink-0", className)}>
      <line
        x1={vertical ? 4 : 2}
        y1={vertical ? 2 : 4}
        x2={vertical ? 4 : w - 2}
        y2={vertical ? h - 2 : 4}
        stroke="currentColor"
        strokeWidth={2}
        strokeDasharray={PROVENANCE_DASH[provenance]}
        strokeLinecap={PROVENANCE_CAP[provenance]}
      />
    </svg>
  );
}

/**
 * Legende der Herkunft. Mit onOnlyProvenChange gibt es den Schalter "nur Belegtes", der alles ausser Tabelle oder
 * Programm ausblendet.
 */
export function SignalLegend({
  onlyProven,
  onOnlyProvenChange,
  className,
}: {
  onlyProven?: boolean;
  onOnlyProvenChange?: (value: boolean) => void;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-wrap items-center gap-x-4 gap-y-1 border border-line bg-card px-3 py-1.5 text-[11px] text-muted-foreground", className)}>
      <span className="font-mono text-[10px] font-semibold uppercase tracking-[0.06em]">Herkunft</span>
      <ul className="contents">
        {PROVENANCE_ORDER.map((provenance) => (
          <li key={provenance} className="flex items-center gap-1.5 text-foreground">
            <ProvenanceLine provenance={provenance} />
            {PROVENANCE_LABELS[provenance]}
          </li>
        ))}
      </ul>
      {onOnlyProvenChange && (
        <label className="flex min-h-11 cursor-pointer items-center gap-2 text-foreground">
          <input
            type="checkbox"
            className="size-4 accent-[var(--primary)]"
            checked={onlyProven ?? false}
            onChange={(event) => onOnlyProvenChange(event.target.checked)}
          />
          nur Belegtes
        </label>
      )}
    </div>
  );
}
