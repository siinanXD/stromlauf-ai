"use client";

import { TriangleAlert } from "lucide-react";
import { useEffect, useState } from "react";

import type { FaultHits } from "@/lib/api";
import type { DetailRef } from "@/lib/detail";
import { matchesAny } from "@/lib/faults";
import { cn } from "@/lib/utils";

import { peekFaultHits, prefetchFaultHits } from "../faultHitsStore";
import { Block } from "./Block";

/**
 * Kennzeichen aus den Treffern der Fehlerliste dieser Maschine zur Meldung: die Bauteile mit Stoerungsbezug.
 * Liest dasselbe Ergebnis wie der Block "Fehlerliste"; ohne Meldung oder Treffer keine.
 */
function useFaultTags(machineId: string | undefined, query: string): string[] {
  const active = Boolean(machineId && query.trim());
  const key = `${machineId}|${query}`;
  const [loaded, setLoaded] = useState<{ key: string; hits: FaultHits | null } | null>(null);
  const cached = active ? peekFaultHits(machineId!, query) : null;
  const hits = cached !== undefined ? cached : loaded?.key === key ? loaded.hits : undefined;

  useEffect(() => {
    if (hits !== undefined || !active) return;
    let cancelled = false;
    prefetchFaultHits(machineId!, query).then((result) => {
      if (!cancelled) setLoaded({ key, hits: result });
    });
    return () => {
      cancelled = true;
    };
  }, [hits, active, machineId, query, key]);

  return hits ? hits.faults.flatMap((fault) => fault.tags) : [];
}

/**
 * Bauteile der Antwort (Figma "Bauteil-Chip") mit ihrer Art aus dem Kennzeichen-Index (meta.part_kinds); Tippen
 * oeffnet das Bauteil. Blau-hell = gerade im Detail offen; rot nur mit Stoerungsbezug (steht in einem Treffer der
 * Fehlerliste dieser Maschine), dazu ein Warnsymbol und der Grund im Namen, damit es nicht nur die Farbe sagt.
 */
export function PartsBlock({
  tags,
  kinds,
  machineId,
  question = "",
  activeTag = null,
  onOpenDetail,
  onShowInModel,
}: {
  tags: string[];
  kinds: Record<string, string>;
  machineId?: string;
  /** Meldung zu dieser Antwort; ihre Fehlerlisten-Treffer markieren Bauteile mit Stoerungsbezug. */
  question?: string;
  /** Bauteil, das gerade im Detail offen ist. */
  activeTag?: string | null;
  onOpenDetail: (detail: DetailRef) => void;
  onShowInModel?: (tags: string[]) => void;
}) {
  const faultTags = useFaultTags(machineId, question);
  if (tags.length === 0) return null;
  return (
    <Block
      kind="parts"
      title="Bauteile"
      source="Kennzeichen-Index"
      testId="referenced-parts"
      action={
        onShowInModel && (
          <button type="button" onClick={() => onShowInModel(tags)} className="min-h-11 rounded-md px-2 text-footnote font-semibold text-primary hover:bg-bg-fill">
            Im Modell zeigen
          </button>
        )
      }
    >
      <ul className="flex flex-wrap gap-x-2 gap-y-3">
        {tags.map((tag) => {
          const fault = matchesAny(tag, faultTags);
          const active = !fault && activeTag !== null && matchesAny(tag, [activeTag]);
          return (
            <li key={tag}>
              <button
                type="button"
                onClick={() => onOpenDetail({ kind: "part", tag })}
                aria-label={`Bauteil ${tag} öffnen${fault ? ", steht in der Fehlerliste" : ""}`}
                aria-current={active ? "true" : undefined}
                data-tag={tag}
                data-state={fault ? "fault" : active ? "active" : "normal"}
                className={cn(
                  "relative inline-flex items-center gap-2 rounded-full px-3 py-2 text-left before:absolute before:inset-x-0 before:-inset-y-1.5 before:content-[''] focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none",
                  fault ? "bg-error-soft" : active ? "bg-primary-soft" : "bg-bg-fill hover:bg-muted",
                )}
              >
                {fault && <TriangleAlert className="size-3.5 shrink-0 text-danger" aria-hidden />}
                <span className={cn("font-mono text-tag-sm font-medium", fault ? "text-danger" : active ? "text-primary" : "text-foreground")}>{tag}</span>
                {kinds[tag] && <span className="text-footnote text-muted-foreground">{kinds[tag]}</span>}
              </button>
            </li>
          );
        })}
      </ul>
    </Block>
  );
}
