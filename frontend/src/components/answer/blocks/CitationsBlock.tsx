"use client";

import { ChevronRight, ShieldCheck } from "lucide-react";

import { CitationChip } from "@/components/chat/CitationChip";
import type { CitationCheck, SourceRef } from "@/lib/api";

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

/**
 * Belege, zugeklappt: oben der Pruefstempel des Zitat-Resolvers ("Belege: 5 von 6 gültig"), aufgeklappt die
 * Belege je Dokument und die Gruende fuer ungueltige oder nicht pruefbare Orte.
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
  return (
    <Block kind="citations" title="Belege" source="Zitat-Prüfung">
      <details data-testid="citations-valid" className="group text-xs">
        <summary className="flex min-h-11 cursor-pointer list-none items-center gap-1.5 font-mono text-[12px] text-muted-foreground hover:text-foreground">
          <ChevronRight className="size-3.5 transition-transform group-open:rotate-90" aria-hidden />
          <ShieldCheck className="size-3.5" aria-hidden />
          {stamp}
        </summary>
        <div className="space-y-3 pt-1">
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
            <ul className="space-y-0.5 pl-1 text-muted-foreground">
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
