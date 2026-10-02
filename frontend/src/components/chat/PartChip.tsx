"use client";

import { cn } from "@/lib/utils";

/**
 * Bauteil-Chip (Figma "Bauteil-Chip"): Pille mit Kennzeichen in Mono, orange-hell wenn in der Antwort referenziert
 * ("hier schauen"), blau-hell wenn gewaehlt.
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
        "part-chip inline-flex min-h-8 max-w-full items-center gap-2 rounded-full border px-3 py-1 font-mono text-tag-sm transition-colors",
        referenced ? "border-look bg-look-soft text-look-strong" : active ? "border-transparent bg-primary-soft text-primary" : "border-transparent bg-bg-fill text-foreground",
        active && "ring-2 ring-accent",
        onClick ? "cursor-pointer hover:border-line" : "cursor-default",
        className,
      )}
    >
      <span className="font-medium">{tag}</span>
      {label && <span className="truncate font-sans text-footnote text-muted-foreground">{label}</span>}
    </button>
  );
}
