"use client";

import { Check, ChevronRight } from "lucide-react";

import { CitationChip } from "@/components/chat/CitationChip";
import type { CitationCheck, SourceRef } from "@/lib/api";
import { cn } from "@/lib/utils";

import { Block } from "./Block";

export interface ChipData {
  key: string;
  label: string;
  open?: () => void;
  active: boolean;
  title: string;
  invalid: boolean;
}

export interface CitationGroup {
  label: string;
  chips: ChipData[];
}

/** Ausrufezeichen im Siegel (Figma "Icon/Exclamation"), in Schriftfarbe gezeichnet. */
function Exclamation() {
  return (
    <svg viewBox="0 0 16 16" fill="none" aria-hidden className="size-3.5">
      <path d="M8 4.667V9M8 11.333v.007" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/**
 * Belege, zugeklappt: oben der Beleg-Stempel des Zitat-Resolvers ("Belege: 5 von 6 gültig"; gruen mit Haken, wenn
 * alles gefunden ist, sonst orange mit Ausrufezeichen), aufgeklappt die Belege je Dokument und die Gruende fuer
 * ungueltige oder nicht pruefbare Orte. Ohne Pruefung ein grauer Stempel mit der Zahl der Belege.
 */
export function CitationsBlock({
  groups,
  validLabel,
  problems,
  fallback,
  onOpenSource,
}: {
  groups: CitationGroup[];
  validLabel: string;
  problems: CitationCheck[];
  /** Fundstellen der Suche, wenn die Antwort keine Belege nennt. */
  fallback: SourceRef[];
  onOpenSource: (source: SourceRef) => void;
}) {
  const count = groups.reduce((n, g) => n + g.chips.length, 0);
  if (count === 0 && fallback.length === 0 && !validLabel) return null;
  const stamp = validLabel || (count > 0 ? `${count} ${count === 1 ? "Beleg" : "Belege"}` : `${fallback.length} Fundstellen`);
  const tone = !validLabel ? "neutral" : problems.length > 0 ? "hint" : "ok";
  return (
    <Block kind="citations" title="Belege" source="Zitat-Prüfung">
      <details data-testid="citations-valid" data-tone={tone} className="group text-footnote">
        <summary
          className={cn(
            "flex min-h-11 cursor-pointer list-none items-center gap-2 rounded-md px-3 py-2 font-semibold focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none [&::-webkit-details-marker]:hidden",
            tone === "ok" ? "bg-ok-soft text-ok-strong" : tone === "hint" ? "bg-look-soft text-look-strong" : "bg-bg-fill text-muted-foreground",
          )}
        >
          <span
            className={cn("grid size-[22px] shrink-0 place-items-center rounded-full text-white", tone === "ok" ? "bg-ok" : tone === "hint" ? "bg-look" : "bg-muted-foreground")}
            aria-hidden
          >
            {tone === "hint" ? <Exclamation /> : <Check className="size-3.5" strokeWidth={3} />}
          </span>
          <span className="min-w-0 flex-1">{stamp}</span>
          <ChevronRight className="size-4 shrink-0 opacity-60 transition-transform group-open:rotate-90" strokeWidth={2.5} aria-hidden />
        </summary>
        <div className="space-y-3 pt-3">
          {groups.length > 0 && (
            <dl className="grid grid-cols-[max-content_1fr] items-center gap-x-4 gap-y-1">
              {groups.map((group) => (
                <div key={group.label} className="contents">
                  <dt className="text-muted-foreground">{group.label}</dt>
                  <dd className="flex flex-wrap gap-1">
                    {group.chips.map((c) => (
                      <CitationChip key={c.key + c.label} label={c.label} onClick={c.open} active={c.active} title={c.title} invalid={c.invalid} />
                    ))}
                  </dd>
                </div>
              ))}
            </dl>
          )}
          {problems.length > 0 && (
            <ul className="space-y-1 pl-1 text-muted-foreground">
              {problems.map((c) => (
                <li key={c.text}>
                  <span className={c.valid ? "" : "line-through decoration-muted-foreground/70"}>{c.text}</span>: {c.reason || "nicht prüfbar"}
                </li>
              ))}
            </ul>
          )}
          {groups.length === 0 && fallback.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {fallback.map((s) => (
                <CitationChip key={`${s.document_id}-${s.page}`} label={`${s.filename} S. ${s.page}`} onClick={() => onOpenSource(s)} />
              ))}
            </div>
          )}
        </div>
      </details>
    </Block>
  );
}
