"use client";

import type { PageTarget } from "@/components/PageViewer";
import { api, type PlanSpot } from "@/lib/api";
import type { DetailRef } from "@/lib/detail";

import { BlockSkeleton, LazyBlock } from "./Block";

/** "Blatt 3", ohne gelesene Blattnummer "Seite 4". */
export function spotPlace(spot: PlanSpot): string {
  return spot.sheet != null ? `Blatt ${spot.sheet}` : `Seite ${spot.page}`;
}

/** Ziel fuer die Planseite: mit Blatt und Spalte als Verweis "/3.5", damit die Seitenansicht die Spalte markiert. */
export function spotTarget(spot: PlanSpot): PageTarget {
  const reference = spot.sheet != null && spot.column != null ? `/${spot.sheet}.${spot.column}` : undefined;
  const label = [`Stromlaufplan ${spotPlace(spot)}`, spot.column != null ? `Spalte ${spot.column}` : null].filter(Boolean).join(" · ");
  return { documentId: spot.document_id, filename: spot.filename, page: spot.page, reference, label, tag: spot.tag };
}

/** Fundstellen der Bauteile im Stromlaufplan; das Seitenbild laedt erst, wenn der Block ins Bild kommt. */
export function PlanBlock({ spots, onOpenDetail }: { spots: PlanSpot[]; onOpenDetail: (detail: DetailRef) => void }) {
  if (spots.length === 0) return null;
  const files = [...new Set(spots.map((s) => s.filename))];
  return (
    <LazyBlock kind="plan" title="Im Plan" source={files.join(", ")} skeleton={<BlockSkeleton tiles={Math.min(spots.length, 3)} label="Planseiten werden geladen" />} testId="block-plan">
      {() => (
        <ul className="scroll-contain flex w-0 min-w-full snap-x gap-3 overflow-x-auto pb-1 [scrollbar-width:thin]" aria-label="Fundstellen im Plan">
          {spots.map((spot) => (
            <li key={`${spot.tag}-${spot.document_id}-${spot.page}`} className="w-44 shrink-0 snap-start">
              <button
                type="button"
                onClick={() => onOpenDetail({ kind: "plan", target: spotTarget(spot) })}
                className="block w-full overflow-hidden rounded-lg border border-border bg-card text-left hover:border-primary focus-visible:ring-2 focus-visible:ring-ring"
                aria-label={`${spot.tag} im Plan, ${spotPlace(spot)}${spot.column != null ? `, Spalte ${spot.column}` : ""} öffnen`}
              >
                {/* Seitenbilder kommen dynamisch vom Server; next/image bringt hier nichts. */}
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={api.pageImageUrl(spot.document_id, spot.page)} alt="" className="aspect-[4/3] w-full bg-white object-cover object-top" loading="lazy" />
                <span className="block px-2 pt-1 font-mono text-[12px] font-semibold">
                  {spot.tag} · {spotPlace(spot)}
                  {spot.column != null && <span className="font-normal text-muted-foreground"> · Spalte {spot.column}</span>}
                </span>
                <span className="block truncate px-2 pb-1.5 text-[11px] text-muted-foreground">{spot.title || spot.filename}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </LazyBlock>
  );
}
