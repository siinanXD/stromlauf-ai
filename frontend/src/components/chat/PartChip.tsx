"use client";

import { cn } from "@/lib/utils";

/**
 * Bauteil-Chip: Kennzeichen in Mono, amber wenn in der Antwort referenziert ("hier schauen").
 * Immer ein Button mit aria-label, damit Tastatur und Screenreader ihn als Sprung zum Datenblatt lesen.
 */
export function PartChip({
  tag,
  label,
  referenced = false,
  active = false,
  onClick,
  className,
}: {
  tag: string;
  label?: string;
  referenced?: boolean;
  active?: boolean;
  onClick?: () => void;
  className?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={!onClick}
      aria-label={`Bauteil ${tag} öffnen`}
      aria-pressed={active || undefined}
      data-referenced={referenced ? "true" : "false"}
      data-tag={tag}
      title={label ? `${tag} · ${label}` : tag}
      className={cn(
        "part-chip inline-flex min-h-8 max-w-full items-center gap-1.5 rounded-lg border px-2 py-1 font-mono text-[13px] leading-none transition-colors",
        referenced
          ? "border-signal bg-signal-soft text-signal-foreground"
          : "border-border bg-card text-foreground",
        active && "ring-2 ring-primary",
        onClick ? "cursor-pointer hover:border-primary" : "cursor-default",
        className,
      )}
    >
      <span className="font-semibold">{tag}</span>
      {label && <span className="truncate font-sans text-xs text-muted-foreground">{label}</span>}
    </button>
  );
}
