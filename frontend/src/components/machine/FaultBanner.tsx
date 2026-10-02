"use client";

import { X } from "lucide-react";

import { Tag } from "@/components/Tag";
import { Button } from "@/components/ui/button";
import type { Fault } from "@/lib/api";
import type { FaultHits } from "@/lib/faults";

/**
 * Gewaehlter Fehler ueber allen Tabs: beteiligte Kennzeichen und wo sie markiert sind (Schaltschrank).
 * Rot nur hier, weil es ein Fehler ist.
 */
export function FaultBanner({
  fault,
  hits,
  onTab,
  onTag,
  onClose,
}: {
  fault: Fault;
  hits: FaultHits;
  onTab: (tab: "schaltschrank" | "fehler") => void;
  onTag: (tag: string) => void;
  onClose: () => void;
}) {
  const link = "text-primary hover:underline disabled:text-muted-foreground disabled:no-underline";
  return (
    <div className="mx-6 mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5 border border-danger/50 bg-danger/5 px-3 py-2 text-sm" role="status">
      <span className="font-mono text-[11px] font-semibold uppercase tracking-[0.06em] text-danger">Fehler</span>
      <span className="font-medium">
        {fault.code && <span className="font-mono">{fault.code} </span>}
        {fault.symptom}
      </span>
      <span className="flex flex-wrap items-center gap-x-1.5">
        {hits.tags.map((tag) => (
          <Tag key={tag} value={tag} onClick={() => onTag(tag)} />
        ))}
        {hits.tags.length === 0 && <span className="text-muted-foreground">keine Kennzeichen am Eintrag</span>}
      </span>
      <span className="flex flex-wrap items-center gap-x-3 text-xs">
        <button className={link} disabled={hits.hotspotIds.length === 0} onClick={() => onTab("schaltschrank")}>
          Schaltschrank {hits.hotspotIds.length}
        </button>
        {hits.unplaced.length > 0 && <span className="text-muted-foreground">nicht platziert: {hits.unplaced.join(", ")}</span>}
      </span>
      <span className="ml-auto flex items-center gap-1">
        <Button size="icon-xs" variant="ghost" aria-label="Markierung aufheben" onClick={onClose}>
          <X />
        </Button>
      </span>
    </div>
  );
}
