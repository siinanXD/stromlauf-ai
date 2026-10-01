"use client";

import { ArrowLeft, Route } from "lucide-react";
import { useEffect, useState, useSyncExternalStore, type ReactNode } from "react";

import type { PageTarget } from "@/components/PageViewer";
import { Button } from "@/components/ui/button";
import { signalPathMain, type SignalMainResult } from "@/lib/api";
import type { DetailRef } from "@/lib/detail";
import { cn } from "@/lib/utils";

import { SignalChain } from "./SignalChain";
import { SignalEmpty } from "./SignalEmpty";
import { SignalLegend } from "./SignalLegend";
import { SignalWorkbench } from "./SignalWorkbench";
import { mainPath } from "./signalColumns";

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

/**
 * Signalweg fuer Antwortblock ("compact") und Detailansicht ("auto"), aus der Hauptweg-Sicht des Backends.
 * compact: hoechstens 5 Schritte um den Start als Kette und "ganz zeigen". auto: unter 1024 px die ganze Kette,
 * ab 1024 px die Grafik in festen Spalten mit der Planseite des gewaehlten Knotens darunter.
 */
export function SignalView({
  sourceId,
  tag,
  variant,
  onOpenDetail,
}: {
  sourceId: string;
  tag: string;
  variant: "compact" | "auto";
  onOpenDetail: (detail: DetailRef) => void;
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
    />
  );
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
}) {
  const compact = variant === "compact";
  const openPart = (part: string) => onOpenDetail({ kind: "part", tag: part });
  const openPlan = (target: PageTarget) => onOpenDetail({ kind: "plan", target });
  const data = load.status === "done" && load.result.ok && mainPath(load.result.data).length > 0 ? load.result.data : null;

  let body: ReactNode;
  if (load.status === "loading") {
    body = (
      <div className="space-y-2" aria-busy="true" aria-label="Signalweg wird geladen">
        {Array.from({ length: compact ? 3 : 5 }, (_, i) => (
          <div key={i} className="h-12 animate-pulse border border-line bg-secondary" />
        ))}
      </div>
    );
  } else if (load.status === "error") {
    body = (
      <div className="border border-line bg-card px-4 py-4 text-sm">
        <p>Signalweg konnte nicht geladen werden.</p>
        <Button variant="outline" className="mt-2 min-h-11 rounded-none border-line" onClick={onRetry}>
          Erneut versuchen
        </Button>
      </div>
    );
  } else if (!data) {
    body = (
      <SignalEmpty
        reason={load.result.ok ? "unknown_tag" : load.result.reason}
        tag={tag}
        sourceId={sourceId}
        compact={compact}
        onOpenDetail={onOpenDetail}
        onReload={onRetry}
      />
    );
  } else if (compact) {
    body = (
      <>
        <SignalChain data={data} limit={COMPACT_STEPS} onOpenPart={openPart} onOpenPlan={openPlan} />
        <button
          type="button"
          className="mt-1 min-h-11 px-1 text-sm font-medium text-primary hover:underline"
          onClick={() => onOpenDetail({ kind: "signal", tag })}
        >
          ganz zeigen
        </button>
      </>
    );
  } else if (wide) {
    body = <SignalWorkbench sourceId={sourceId} data={data} onOpenDetail={onOpenDetail} onFollow={onFollow} />;
  } else {
    body = (
      <>
        <SignalChain data={data} onOpenPart={openPart} onOpenPlan={openPlan} onFollow={onFollow} />
        <SignalLegend className="mt-3" />
      </>
    );
  }

  if (compact) return <div data-signal-view="compact">{body}</div>;
  return (
    <div data-signal-view="auto" className="flex h-full min-h-0 flex-col bg-card">
      <header className="flex min-h-12 shrink-0 items-center gap-2 border-b border-line px-3">
        <Route className="size-4 text-primary" />
        <h2 className="text-sm font-medium">
          Signalweg <span className="font-mono">{tag}</span>
        </h2>
        {back && onBack && (
          <Button variant="ghost" className="ml-auto min-h-11 rounded-none" onClick={onBack}>
            <ArrowLeft className="size-4" />
            zurück zu <span className="font-mono">{back}</span>
          </Button>
        )}
      </header>
      <div className={cn("min-h-0 flex-1", wide && data ? "flex flex-col overflow-auto" : "overflow-auto p-3")}>{body}</div>
    </div>
  );
}
