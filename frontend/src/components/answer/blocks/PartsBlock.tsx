"use client";

import type { DetailRef } from "@/lib/detail";

import { Block } from "./Block";

/** Bauteile der Antwort mit ihrer Art aus dem Kennzeichen-Index (meta.part_kinds); Tippen oeffnet das Bauteil. */
export function PartsBlock({
  tags,
  kinds,
  onOpenDetail,
  onShowInModel,
}: {
  tags: string[];
  kinds: Record<string, string>;
  onOpenDetail: (detail: DetailRef) => void;
  onShowInModel?: (tags: string[]) => void;
}) {
  if (tags.length === 0) return null;
  return (
    <Block
      kind="parts"
      title="Bauteile"
      source="Kennzeichen-Index"
      testId="referenced-parts"
      action={
        onShowInModel && (
          <button type="button" onClick={() => onShowInModel(tags)} className="min-h-11 rounded-md px-2 text-xs font-medium text-primary hover:underline">
            Im Modell zeigen
          </button>
        )
      }
    >
      <ul className="flex flex-wrap gap-1.5">
        {tags.map((tag) => (
          <li key={tag}>
            <button
              type="button"
              onClick={() => onOpenDetail({ kind: "part", tag })}
              aria-label={`Bauteil ${tag} öffnen`}
              data-tag={tag}
              className="inline-flex min-h-11 items-center gap-1.5 rounded-lg border border-border bg-card px-2.5 py-1 text-left hover:border-primary focus-visible:ring-2 focus-visible:ring-ring"
            >
              <span className="font-mono text-[13px] font-semibold">{tag}</span>
              {kinds[tag] && <span className="text-xs text-muted-foreground">{kinds[tag]}</span>}
            </button>
          </li>
        ))}
      </ul>
    </Block>
  );
}
