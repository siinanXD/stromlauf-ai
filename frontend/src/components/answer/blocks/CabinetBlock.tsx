"use client";

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
            <li key={item.hotspot_id} className="w-44 shrink-0 snap-start" data-testid="evidence-cabinet">
              <button
                type="button"
                onClick={() => onOpenDetail({ kind: "cabinet", cabinetId: item.cabinet_id, hotspotId: item.hotspot_id })}
                className="block w-full overflow-hidden rounded-lg border border-border bg-card text-left hover:border-primary focus-visible:ring-2 focus-visible:ring-ring"
                aria-label={`${item.tag} im Foto ${item.cabinet_title} zeigen`}
              >
                <span className="relative block aspect-[4/3] w-full overflow-hidden bg-secondary">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={plant.cabinetImageUrl(item.cabinet_id)} alt="" className="absolute inset-0 size-full object-cover" loading="lazy" />
                  <span
                    aria-hidden
                    className="absolute rounded-sm border-2 border-signal shadow-[0_0_0_1px_var(--signal-foreground)]"
                    style={{ left: `${item.box.x * 100}%`, top: `${item.box.y * 100}%`, width: `${item.box.w * 100}%`, height: `${item.box.h * 100}%` }}
                  />
                </span>
                <span className="block truncate px-2 py-1.5 font-mono text-[11px] text-muted-foreground">
                  <span className="font-semibold text-foreground">{item.tag}</span> · {item.cabinet_title}
                  {!item.confirmed && " · unbestätigt"}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </LazyBlock>
  );
}
