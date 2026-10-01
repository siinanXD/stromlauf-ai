"use client";

import { CheckCircle2, ChevronRight, History } from "lucide-react";
import { useEffect, useState } from "react";

import type { FaultHits } from "@/lib/api";
import type { DetailRef } from "@/lib/detail";

import { hasHits, peekFaultHits, prefetchFaultHits } from "../faultHitsStore";
import { useInView } from "../useInView";
import { Block, BlockSkeleton } from "./Block";

const ROW = "flex min-h-11 w-full items-start gap-2 rounded-md px-2 py-1.5 text-left hover:bg-secondary focus-visible:ring-2 focus-visible:ring-ring";

/**
 * Erster Block jeder Antwort: Treffer der Fehlerliste zur Meldung, ohne Modell. Die Abfrage startet beim Senden
 * (prefetchFaultHits); im Verlauf laedt der Block, sobald er ins Bild kommt. Ohne Treffer oder bei Fehler (etwa ein
 * Server ohne diesen Endpunkt) faellt er weg.
 */
export function FaultHitsBlock({
  machineId,
  query,
  onOpenDetail,
  onOpenIncident,
}: {
  machineId: string;
  query: string;
  onOpenDetail: (detail: DetailRef) => void;
  onOpenIncident?: (conversationId: string) => void;
}) {
  const [ref, inView] = useInView<HTMLElement>();
  const [loaded, setLoaded] = useState<{ key: string; hits: FaultHits | null } | null>(null);
  const key = `${machineId}|${query}`;
  const cached = peekFaultHits(machineId, query);
  const hits = cached !== undefined ? cached : loaded?.key === key ? loaded.hits : undefined;

  useEffect(() => {
    if (hits !== undefined || !inView) return;
    let cancelled = false;
    prefetchFaultHits(machineId, query).then((result) => {
      if (!cancelled) setLoaded({ key, hits: result });
    });
    return () => {
      cancelled = true;
    };
  }, [hits, inView, machineId, query, key]);

  if (hits === undefined) {
    return (
      <Block kind="faults" title="Fehlerliste" source="wird durchsucht" innerRef={ref} testId="block-faults">
        <BlockSkeleton rows={1} label="Fehlerliste wird durchsucht" />
      </Block>
    );
  }
  if (!hasHits(hits)) return null;

  return <FaultHitsList hits={hits} onOpenDetail={onOpenDetail} onOpenIncident={onOpenIncident} />;
}

/** Darstellung der drei Listen; Erfahrung anderer Maschinen ist als solche benannt und kein Beleg. */
export function FaultHitsList({
  hits,
  onOpenDetail,
  onOpenIncident,
}: {
  hits: FaultHits;
  onOpenDetail: (detail: DetailRef) => void;
  onOpenIncident?: (conversationId: string) => void;
}) {
  const count = hits.faults.length;
  return (
    <Block kind="faults" title="Fehlerliste" source={count > 0 ? `${count} ${count === 1 ? "Eintrag" : "Einträge"} dieser Maschine` : "keine Einträge dieser Maschine"} testId="block-faults">
      <ul className="-mx-2 space-y-0.5">
        {hits.faults.map((fault) => (
          <li key={fault.id}>
            <button type="button" className={ROW} onClick={() => onOpenDetail({ kind: "fault", faultId: fault.id })}>
              {fault.code && <span className="shrink-0 font-mono text-[13px] font-semibold">{fault.code}</span>}
              <span className="min-w-0 flex-1">
                <span className="block text-[13px] font-medium">{fault.symptom || "Ohne Symptom"}</span>
                {fault.cause && <span className="block truncate text-xs text-muted-foreground">Ursache: {fault.cause}</span>}
              </span>
              <ChevronRight className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden />
            </button>
          </li>
        ))}
        {hits.experience.map((entry) => (
          <li key={`x-${entry.fault.id}`}>
            <button type="button" className={ROW} onClick={() => onOpenDetail({ kind: "fault", faultId: entry.fault.id })}>
              <span className="shrink-0 rounded border border-border px-1 font-mono text-[10px] uppercase tracking-[0.06em] text-muted-foreground">Erfahrung</span>
              <span className="min-w-0 flex-1">
                <span className="block text-[13px]">{entry.fault.symptom || entry.fault.code}</span>
                <span className="block truncate text-xs text-muted-foreground">an {entry.machine_name} · kein Beleg für diese Maschine</span>
              </span>
              <ChevronRight className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden />
            </button>
          </li>
        ))}
        {hits.incidents.map((incident) => (
          <li key={`i-${incident.conversation_id}`}>
            <button
              type="button"
              className={ROW}
              onClick={onOpenIncident ? () => onOpenIncident(incident.conversation_id) : undefined}
              disabled={!onOpenIncident}
            >
              <span className="flex shrink-0 items-center gap-1 rounded border border-border px-1 font-mono text-[10px] uppercase tracking-[0.06em] text-muted-foreground">
                <History className="size-3" aria-hidden />
                Störfall
              </span>
              <span className="min-w-0 flex-1">
                <span className="block text-[13px]">{incident.title}</span>
                {incident.finding && (
                  <span className="flex items-start gap-1 text-xs text-muted-foreground">
                    <CheckCircle2 className="mt-0.5 size-3 shrink-0" aria-hidden />
                    Befund: {incident.finding}
                  </span>
                )}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </Block>
  );
}
