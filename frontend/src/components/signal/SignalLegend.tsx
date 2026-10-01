import { cn } from "@/lib/utils";

import { PROVENANCE_LABELS, PROVENANCE_ORDER, type Provenance } from "./provenance";

/** Strichart je Herkunftsstufe als CSS-Rahmen: durchgezogen, gestrichelt, gepunktet (Kette und Legende). */
export const PROVENANCE_BORDER: Record<Provenance, string> = {
  beleg: "border-solid",
  leitung: "border-dashed",
  lage: "border-dotted",
};

/** Kurzes Linienmuster einer Herkunftsstufe, waagrecht (Legende) oder senkrecht. */
export function ProvenanceLine({ provenance, vertical = false, className }: { provenance: Provenance; vertical?: boolean; className?: string }) {
  return (
    <span
      aria-hidden
      className={cn("block shrink-0 border-line", vertical ? "h-7 w-0 border-l-2" : "h-0 w-6 border-t-2", PROVENANCE_BORDER[provenance], className)}
    />
  );
}

/** Schalter im iOS-Stil (Rolle switch); die Zeile ist 44 px hoch und ganz tippbar. */
export function Switch({ checked, onChange, label, className }: { checked: boolean; onChange: (value: boolean) => void; label: string; className?: string }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className={cn("flex min-h-11 w-full items-center justify-between gap-3 text-left text-body focus-visible:outline-none", className)}
    >
      <span>{label}</span>
      <span
        aria-hidden
        className={cn(
          "relative h-[31px] w-[51px] shrink-0 rounded-full transition-colors",
          checked ? "bg-primary" : "bg-bg-fill",
          "[button:focus-visible>&]:ring-3 [button:focus-visible>&]:ring-ring/50",
        )}
      >
        <span className={cn("absolute top-0.5 left-0.5 size-[27px] rounded-full bg-white shadow-card transition-transform", checked && "translate-x-5")} />
      </span>
    </button>
  );
}

/**
 * Legende der Herkunft: je Stufe ein Linienmuster und ihr Name (nicht nur die Farbe). Mit onOnlyProvenChange gibt es
 * den Schalter "Nur Belegtes zeigen", der alles ausser Tabelle oder Programm ausblendet.
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
    <div className={cn("text-caption-1 text-muted-foreground", className)}>
      <span className="sr-only">Herkunft der Verbindungen:</span>
      <ul className="flex flex-wrap items-center gap-x-4 gap-y-1">
        {PROVENANCE_ORDER.map((provenance) => (
          <li key={provenance} className="flex items-center gap-1.5">
            <ProvenanceLine provenance={provenance} className="border-muted-foreground" />
            {PROVENANCE_LABELS[provenance]}
          </li>
        ))}
      </ul>
      {onOnlyProvenChange && <Switch checked={onlyProven ?? false} onChange={onOnlyProvenChange} label="Nur Belegtes zeigen" className="mt-1 text-foreground" />}
    </div>
  );
}
