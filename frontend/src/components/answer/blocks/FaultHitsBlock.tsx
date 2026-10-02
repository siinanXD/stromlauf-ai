"use client";

import { CheckCircle2, ChevronRight, History } from "lucide-react";
import type { ReactNode } from "react";
import { useEffect, useState } from "react";

import type { FaultHits } from "@/lib/api";
import type { DetailRef } from "@/lib/detail";
import { cn } from "@/lib/utils";

import { hasHits, peekFaultHits, prefetchFaultHits } from "../faultHitsStore";
import { useInView } from "../useInView";
import { Block } from "./Block";

/** Fehler-Zeile (Figma): Code-Pille, Symptom, Ursache, Chevron; ganze Zeile tippbar. */
const ROW =
  "flex min-h-11 w-full items-center gap-3 rounded-md px-1 py-2 text-left hover:bg-bg-fill focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none disabled:hover:bg-transparent";

/** Code der Fehlerliste: orange-hell fuer diese Maschine ("hier schauen"), grau fuer Erfahrung anderer Maschinen. */
function CodePill({ children, own }: { children: ReactNode; own: boolean }) {
  return (
    <span className={cn("flex shrink-0 items-center gap-1 rounded-sm px-2 py-1 font-mono text-tag-sm font-medium", own ? "bg-look-soft text-look-strong" : "bg-bg-fill text-muted-foreground")}>
      {children}
    </span>
  );
}

const Chevron = () => <ChevronRight className="size-[18px] shrink-0 text-text-tertiary" strokeWidth={2.5} aria-hidden />;

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
        {/* In der Form einer Fehler-Zeile, damit beim Eintreffen der Treffer wenig springt */}
        <div className="flex items-center gap-3 px-1 py-2" aria-busy="true">
          <span className="sr-only">Fehlerliste wird durchsucht</span>
          <span className="h-6 w-12 shrink-0 animate-pulse rounded-sm bg-bg-fill" aria-hidden />
          <span className="flex-1 space-y-2" aria-hidden>
            <span className="block h-4 w-2/3 animate-pulse rounded-xs bg-bg-fill" />
            <span className="block h-3.5 w-1/2 animate-pulse rounded-xs bg-bg-fill" />
          </span>
        </div>
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
      <ul className="space-y-0.5">
        {hits.faults.map((fault) => (
          <li key={fault.id}>
            <button type="button" className={ROW} onClick={() => onOpenDetail({ kind: "fault", faultId: fault.id })}>
              {fault.code && <CodePill own>{fault.code}</CodePill>}
              <span className="min-w-0 flex-1 space-y-0.5">
                <span className="line-clamp-2 text-subhead font-semibold">{fault.symptom || "Ohne Symptom"}</span>
                {fault.cause && <span className="line-clamp-2 text-footnote text-muted-foreground">Ursache: {fault.cause}</span>}
              </span>
              <Chevron />
            </button>
          </li>
        ))}
        {hits.experience.map((entry) => (
          <li key={`x-${entry.fault.id}`}>
            <button type="button" className={ROW} onClick={() => onOpenDetail({ kind: "fault", faultId: entry.fault.id })}>
              <CodePill own={false}>{entry.fault.code || "–"}</CodePill>
              <span className="min-w-0 flex-1 space-y-0.5">
                <span className="block text-caption-2 text-muted-foreground uppercase">Erfahrung</span>
                <span className="line-clamp-2 text-subhead font-semibold">{entry.fault.symptom || entry.fault.code}</span>
                <span className="line-clamp-2 text-footnote text-muted-foreground">an {entry.machine_name} · kein Beleg für diese Maschine</span>
              </span>
              <Chevron />
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
              <CodePill own={false}>
                <History className="size-3.5" aria-hidden />
              </CodePill>
              <span className="min-w-0 flex-1 space-y-0.5">
                <span className="block text-caption-2 text-muted-foreground uppercase">Störfall</span>
                <span className="line-clamp-2 text-subhead font-semibold">{incident.title}</span>
                {incident.finding && (
                  <span className="flex items-start gap-1 text-footnote text-muted-foreground">
                    <CheckCircle2 className="mt-0.5 size-3.5 shrink-0" aria-hidden />
                    Befund: {incident.finding}
                  </span>
                )}
              </span>
              {onOpenIncident && <Chevron />}
            </button>
          </li>
        ))}
      </ul>
    </Block>
  );
}
