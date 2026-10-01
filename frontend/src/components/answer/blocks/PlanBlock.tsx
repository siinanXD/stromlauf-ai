"use client";

import { ChevronRight, FileText } from "lucide-react";
import { useEffect, useState } from "react";

import type { PageTarget } from "@/components/PageViewer";
import { api, locate, type LocateResult, type PlanSpot } from "@/lib/api";
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

/**
 * Lage der Spalte auf dem Seitenbild aus dem Schriftfeld-Raster (GET /locate, ohne Modell); null, wenn sie
 * unbekannt ist. Dann zeigt die Karte die Seite ohne Markierung, die Spalte steht weiter im Text.
 */
function useColumnBox(target: PageTarget): LocateResult["box"] {
  const reference = target.reference;
  const key = `${target.documentId}|${reference ?? ""}`;
  const [found, setFound] = useState<{ key: string; box: LocateResult["box"] } | null>(null);
  useEffect(() => {
    if (!reference) return;
    let cancelled = false;
    locate(target.documentId, reference)
      .then((result) => !cancelled && setFound({ key, box: result.page === target.page ? result.box : null }))
      .catch(() => !cancelled && setFound({ key, box: null }));
    return () => {
      cancelled = true;
    };
  }, [target.documentId, target.page, reference, key]);
  return found?.key === key ? found.box : null;
}

/**
 * Planseite-Karte (Figma): Seitenbild 184 px hoch mit markierter Spalte, darunter Blatt und Spalte, Titel und ein
 * Chevron. Die ganze Karte oeffnet die Seite im Detail.
 */
function PlanPageCard({ spot, onOpenDetail }: { spot: PlanSpot; onOpenDetail: (detail: DetailRef) => void }) {
  const target = spotTarget(spot);
  const box = useColumnBox(target);
  const place = [spotPlace(spot), spot.column != null ? `Spalte ${spot.column}` : null].filter(Boolean).join(" · ");
  return (
    <button
      type="button"
      onClick={() => onOpenDetail({ kind: "plan", target })}
      className="group block w-full space-y-2 rounded-md text-left focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
      aria-label={`${spot.tag} im Plan, ${spotPlace(spot)}${spot.column != null ? `, Spalte ${spot.column}` : ""} öffnen`}
    >
      <span className="block h-[184px] overflow-hidden rounded-md border border-border bg-white">
        <span className="relative block">
          {/* Seitenbilder kommen dynamisch vom Server; next/image bringt hier nichts. */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={api.pageImageUrl(spot.document_id, spot.page)} alt="" className="block h-auto w-full" loading="lazy" />
          {box && (
            <span
              aria-hidden
              data-testid="plan-column"
              className="absolute rounded-xs border-[1.5px] border-accent bg-accent-soft"
              style={{ left: `${box.x0 * 100}%`, top: `${box.y0 * 100}%`, width: `${(box.x1 - box.x0) * 100}%`, height: `${(box.y1 - box.y0) * 100}%` }}
            />
          )}
        </span>
      </span>
      <span className="flex items-center gap-2">
        <FileText className="size-5 shrink-0 text-accent" aria-hidden />
        <span className="min-w-0 flex-1">
          <span className="block truncate text-subhead font-semibold">{place}</span>
          <span className="block truncate text-footnote text-muted-foreground">
            <span className="font-mono">{spot.tag}</span> · {spot.title || spot.filename}
          </span>
        </span>
        <ChevronRight className="size-[18px] shrink-0 text-text-tertiary group-hover:text-muted-foreground" strokeWidth={2.5} aria-hidden />
      </span>
    </button>
  );
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
            <li key={`${spot.tag}-${spot.document_id}-${spot.page}`} className={spots.length > 1 ? "w-[min(326px,85%)] shrink-0 snap-start" : "w-full max-w-[420px]"}>
              <PlanPageCard spot={spot} onOpenDetail={onOpenDetail} />
            </li>
          ))}
        </ul>
      )}
    </LazyBlock>
  );
}
