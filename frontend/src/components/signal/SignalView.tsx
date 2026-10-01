"use client";

import { SignalPath } from "@/components/signal/SignalPath";
import type { DetailRef } from "@/lib/detail";

/**
 * Signalweg fuer Antwortblock ("compact") und Detailansicht ("auto").
 *
 * Vertrag der Stoerfall-Arbeitsflaeche: Die Props bleiben gleich, den Inhalt ersetzt Spur C1 durch Kette und
 * Grafik in festen Spalten. Bis dahin zeigt die Komponente die bisherige Ansicht.
 */
export function SignalView({
  sourceId,
  tag,
  onOpenDetail,
}: {
  sourceId: string;
  tag: string;
  variant: "compact" | "auto";
  onOpenDetail: (detail: DetailRef) => void;
}) {
  return (
    <SignalPath
      sourceId={sourceId}
      initialTag={tag}
      onOpen={(target) => onOpenDetail({ kind: "plan", target })}
    />
  );
}
