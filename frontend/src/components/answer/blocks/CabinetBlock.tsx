"use client";

import { Camera, ChevronRight } from "lucide-react";

import { plant, type CabinetEvidence } from "@/lib/api";
import type { DetailRef } from "@/lib/detail";

import { BlockSkeleton, LazyBlock } from "./Block";

/** Bauteile im Schaltschrankfoto (meta.evidence vom Typ cabinet); das Foto laedt erst, wenn der Block ins Bild kommt. */
export function CabinetBlock({ evidence, onOpenDetail }: { evidence: CabinetEvidence[]; onOpenDetail: (detail: DetailRef) => void }) {
  if (evidence.length === 0) return null;
  const cabinets = [...new Set(evidence.map((e) => e.cabinet_title))];
  return (
    <LazyBlock kind="cabinet" title="Im Schrank" source={cabinets.join(", ")} skeleton={<BlockSkeleton tiles={Math.min(evidence.length, 3)} label="Schrankfotos werden geladen" />} testId="block-cabinet">
      {() => (
        <ul className="scroll-contain flex w-0 min-w-full snap-x gap-3 overflow-x-auto pb-1 [scrollbar-width:thin]" aria-label="Bauteile im Schaltschrank">
          {evidence.map((item) => (
            <li key={item.hotspot_id} className={evidence.length > 1 ? "w-[min(326px,85%)] shrink-0 snap-start" : "w-full max-w-[420px]"} data-testid="evidence-cabinet">
              <button
                type="button"
                onClick={() => onOpenDetail({ kind: "cabinet", cabinetId: item.cabinet_id, hotspotId: item.hotspot_id })}
                className="group block w-full space-y-2 rounded-md text-left focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
                aria-label={`${item.tag} im Foto ${item.cabinet_title} zeigen`}
              >
                <span className="relative block h-[184px] w-full overflow-hidden rounded-md bg-bg-fill">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={plant.cabinetImageUrl(item.cabinet_id)} alt="" className="absolute inset-0 size-full object-cover" loading="lazy" />
                  <span
                    aria-hidden
                    className="absolute rounded-sm border-2 border-signal shadow-[0_0_0_1px_var(--signal-foreground)]"
                    style={{ left: `${item.box.x * 100}%`, top: `${item.box.y * 100}%`, width: `${item.box.w * 100}%`, height: `${item.box.h * 100}%` }}
                  />
                </span>
                <span className="flex items-center gap-2">
                  <Camera className="size-5 shrink-0 text-accent" aria-hidden />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-mono text-tag-sm font-medium">{item.tag}</span>
                    <span className="block truncate text-footnote text-muted-foreground">
                      {item.cabinet_title}
                      {!item.confirmed && " · unbestätigt"}
                    </span>
                  </span>
                  <ChevronRight className="size-[18px] shrink-0 text-text-tertiary group-hover:text-muted-foreground" strokeWidth={2.5} aria-hidden />
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </LazyBlock>
  );
}
