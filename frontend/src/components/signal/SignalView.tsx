"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { useEffect, useMemo, useState, useSyncExternalStore, type ReactNode } from "react";

import type { PageTarget } from "@/components/PageViewer";
import { Button } from "@/components/ui/button";
import { signalPathMain, type SignalMainData, type SignalMainResult } from "@/lib/api";
import type { DetailRef } from "@/lib/detail";
import { cn } from "@/lib/utils";

import { schematicTarget } from "./planTarget";
import { onlyProven } from "./provenance";
import { SignalChain } from "./SignalChain";
import { SignalEmpty } from "./SignalEmpty";
import { SignalLegend } from "./SignalLegend";
import { SignalWorkbench } from "./SignalWorkbench";
import { mainPath, nodeTitle } from "./signalColumns";

/** Hoechstens so viele Hauptwegknoten zeigt der Antwortblock. */
export const COMPACT_STEPS = 5;

const WIDE_QUERY = "(min-width: 1024px)";

function subscribeWide(onChange: () => void) {
  const query = window.matchMedia(WIDE_QUERY);
  query.addEventListener("change", onChange);
  return () => query.removeEventListener("change", onChange);
}

/** Ab 1024 px Breite. Auf dem Server und beim Hydrieren false: erst die Kette, die Grafik laedt nur am PC. */
function useWide(): boolean {
  return useSyncExternalStore(
    subscribeWide,
    () => window.matchMedia(WIDE_QUERY).matches,
    () => false,
  );
}

export type SignalLoad = { status: "loading" } | { status: "error" } | { status: "done"; result: SignalMainResult };

const stepsText = (n: number) => (n === 1 ? "1 Schritt" : `${n} Schritte`);

/** "Hauptweg von -S1 bis -M1 · 8 Schritte" (Figma, Kopf der Signalweg-Ansicht). */
export function mainSummary(data: SignalMainData): string {
  const path = mainPath(data);
  if (path.length === 0) return "";
  const first = nodeTitle(path[0]);
  const last = nodeTitle(path[path.length - 1]);
  return path.length === 1 ? `Hauptweg ${first} · 1 Schritt` : `Hauptweg von ${first} bis ${last} · ${stepsText(path.length)}`;
}

/**
 * Signalweg fuer Antwortblock ("compact") und Detailansicht ("auto"), aus der Hauptweg-Sicht des Backends.
 * compact: hoechstens 5 Schritte um den Start als Kette und "ganz zeigen". auto: unter 1024 px die ganze Kette,
 * ab 1024 px die Grafik in festen Spalten mit dem gewaehlten Knoten und seiner Planseite darunter. onClose zeigt im
 * Kopf "‹ Störfall" (Detail des Stoerfalls).
 */
export function SignalView({
  sourceId,
  tag,
  variant,
  onOpenDetail,
  onClose,
}: {
  sourceId: string;
  tag: string;
  variant: "compact" | "auto";
  onOpenDetail: (detail: DetailRef) => void;
  onClose?: () => void;
}) {
  // Mitte des Signalwegs; "Von hier weiter verfolgen" verschiebt sie, trail merkt sich den Rueckweg
  const [center, setCenter] = useState(tag);
  const [trail, setTrail] = useState<string[]>([]);
  const [seenTag, setSeenTag] = useState(tag);
  if (seenTag !== tag) {
    setSeenTag(tag);
    setCenter(tag);
    setTrail([]);
  }
  const [attempt, setAttempt] = useState(0);
  const key = `${sourceId}|${center}|${attempt}`;
  const [loaded, setLoaded] = useState<{ key: string; load: SignalLoad } | null>(null);
  const wide = useWide();

  useEffect(() => {
    let cancelled = false;
    signalPathMain(center, sourceId)
      .then((result) => !cancelled && setLoaded({ key, load: { status: "done", result } }))
      .catch(() => !cancelled && setLoaded({ key, load: { status: "error" } }));
    return () => {
      cancelled = true;
    };
  }, [center, sourceId, key]);

  const load: SignalLoad = loaded?.key === key ? loaded.load : { status: "loading" };
  const back = trail.at(-1) ?? null;

  return (
    <SignalViewBody
      sourceId={sourceId}
      tag={center}
      variant={variant}
      wide={wide}
      load={load}
      onOpenDetail={onOpenDetail}
      onFollow={(next) => {
        setTrail([...trail, center]);
        setCenter(next);
      }}
      back={back}
      onBack={() => {
        setCenter(back ?? tag);
        setTrail(trail.slice(0, -1));
      }}
      onRetry={() => setAttempt((n) => n + 1)}
      onClose={onClose}
    />
  );
}

/** Weisse Karte der Signalweg-Ansicht (Figma: Zusammenfassung, Kette). */
function Card({ children, className }: { children: ReactNode; className?: string }) {
  return <section className={cn("rounded-lg bg-card p-4 shadow-card", className)}>{children}</section>;
}

/** Darstellung ohne Abruf, je Ladezustand: so testbar und in Block und Detail gleich aufgebaut. */
export function SignalViewBody({
  sourceId,
  tag,
  variant,
  wide,
  load,
  onOpenDetail,
  onFollow,
  back = null,
  onBack,
  onRetry,
  onClose,
}: {
  sourceId: string;
  tag: string;
  variant: "compact" | "auto";
  /** Ab 1024 px: Grafik statt Kette (nur auto). */
  wide: boolean;
  load: SignalLoad;
  onOpenDetail: (detail: DetailRef) => void;
  onFollow: (tag: string) => void;
  /** Vorige Mitte nach "Von hier weiter verfolgen"; null am Anfang. */
  back?: string | null;
  onBack?: () => void;
  onRetry: () => void;
  /** Detail schliessen ("‹ Störfall"); ohne keinen Zurueck-Knopf. */
  onClose?: () => void;
}) {
  const [proven, setProven] = useState(false);
  const compact = variant === "compact";
  const openPart = (part: string) => onOpenDetail({ kind: "part", tag: part });
  const openPlan = (target: PageTarget) => onOpenDetail({ kind: "plan", target });
  const data = load.status === "done" && load.result.ok && mainPath(load.result.data).length > 0 ? load.result.data : null;
  const shown = useMemo(() => (data && proven ? onlyProven(data) : data), [data, proven]);
  const summary = data ? mainSummary(data) : "";
  const startNode = data?.nodes.find((node) => node.id === data.start) ?? null;
  const startPlan: PageTarget | null = data && startNode ? schematicTarget(startNode, data.schematic) : null;

  let body: ReactNode;
  if (load.status === "loading") {
    body = (
      <div className={cn("space-y-2", !compact && "p-4")} aria-busy="true" aria-label="Signalweg wird geladen">
        {Array.from({ length: compact ? 3 : 5 }, (_, i) => (
          <div key={i} className="h-12 animate-pulse rounded-md bg-bg-fill" />
        ))}
      </div>
    );
  } else if (load.status === "error") {
    body = (
      <div className={cn(!compact && "p-4")}>
        <Card className={cn(compact && "p-0 shadow-none")}>
          <p className="text-subhead">Signalweg konnte nicht geladen werden.</p>
          <Button variant="outline" className="mt-3 min-h-11" onClick={onRetry}>
            Erneut versuchen
          </Button>
        </Card>
      </div>
    );
  } else if (!data) {
    body = (
      <div className={cn(!compact && "p-4")}>
        <SignalEmpty
          reason={load.result.ok ? "unknown_tag" : load.result.reason}
          tag={tag}
          sourceId={sourceId}
          compact={compact}
          onOpenDetail={onOpenDetail}
          onReload={onRetry}
        />
      </div>
    );
  } else if (compact) {
    body = (
      <>
        <SignalChain data={data} limit={COMPACT_STEPS} onOpenPart={openPart} onOpenPlan={openPlan} />
        <button
          type="button"
          className="mt-1 inline-flex min-h-11 items-center gap-0.5 text-subhead font-semibold text-primary hover:underline"
          onClick={() => onOpenDetail({ kind: "signal", tag })}
        >
          Weg ganz zeigen · {stepsText(mainPath(data).length)}
          <ChevronRight className="size-4" strokeWidth={2.5} aria-hidden />
        </button>
      </>
    );
  } else if (wide) {
    body = <SignalWorkbench sourceId={sourceId} data={data} onOpenDetail={onOpenDetail} onFollow={onFollow} />;
  } else {
    body = (
      <div className="space-y-3 p-4">
        <Card>
          <p className="text-subhead font-semibold">{summary}</p>
          <SignalLegend className="mt-2" onlyProven={proven} onOnlyProvenChange={setProven} />
        </Card>
        <Card>
          <SignalChain data={shown ?? data} onOpenPart={openPart} onOpenPlan={openPlan} onFollow={onFollow} />
        </Card>
      </div>
    );
  }

  if (compact) return <div data-signal-view="compact">{body}</div>;
  return (
    <div data-signal-view="auto" className="flex h-full min-h-0 flex-col bg-background">
      {/* Kopf (Figma "Nav-Leiste" am Handy, "Kopfzeile" am PC): Zurueck, Titel mit Hauptweg, Legende bzw. "Plan" */}
      <header className="flex min-h-[52px] shrink-0 items-center gap-1 border-b-[0.5px] border-border bg-bg-bar px-1 py-1 backdrop-blur-bar lg:gap-6 lg:px-6 lg:py-3">
        {onClose && (
          <button type="button" onClick={onClose} className="flex min-h-11 shrink-0 items-center rounded-md pr-1.5 text-body text-primary hover:bg-bg-fill" aria-label="Zurück zum Störfall">
            <ChevronLeft className="size-6" aria-hidden />
            <span aria-hidden className="lg:hidden">
              Antwort
            </span>
            <span aria-hidden className="hidden lg:inline">
              Störfall
            </span>
          </button>
        )}
        <div className={cn("min-w-0 flex-1 lg:min-w-60 lg:text-left", onClose ? "text-center" : "px-3 lg:px-0")}>
          <h2 className="truncate text-headline lg:text-title-2">
            Signalweg <span className="font-mono">{tag}</span>
          </h2>
          {(summary || back) && (
            <p className="hidden items-center gap-2 truncate text-footnote text-muted-foreground lg:flex">
              {summary}
              {back && onBack && (
                <button type="button" className="min-h-11 font-semibold text-primary hover:underline lg:min-h-0" onClick={onBack}>
                  ‹ zurück zu <span className="font-mono">{back}</span>
                </button>
              )}
            </p>
          )}
        </div>
        {wide && data ? (
          <SignalLegend className="hidden max-w-[50%] min-w-0 text-footnote lg:block [&_ul]:justify-end" />
        ) : (
          startPlan && (
            <button type="button" className="min-h-11 shrink-0 rounded-md px-2 text-headline text-primary hover:bg-bg-fill" onClick={() => openPlan(startPlan)}>
              Plan
            </button>
          )
        )}
      </header>
      {back && onBack && (
        <button type="button" className="flex min-h-11 items-center gap-0.5 px-4 text-subhead font-semibold text-primary lg:hidden" onClick={onBack}>
          <ChevronLeft className="size-4" aria-hidden />
          zurück zu <span className="font-mono">{back}</span>
        </button>
      )}
      <div className={cn("relative min-h-0 flex-1", wide && data ? "flex flex-col overflow-auto" : "overflow-auto")}>{body}</div>
    </div>
  );
}
