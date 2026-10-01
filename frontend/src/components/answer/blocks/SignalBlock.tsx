"use client";

import dynamic from "next/dynamic";

import type { DetailRef } from "@/lib/detail";

import { BlockSkeleton, LazyBlock } from "./Block";

// Erst laden, wenn der Block ins Bild kommt: die Signalweg-Ansicht bringt eigene Abhaengigkeiten mit.
const SignalView = dynamic(() => import("@/components/signal/SignalView").then((m) => m.SignalView), {
  ssr: false,
  loading: () => <BlockSkeleton rows={3} label="Signalweg wird geladen" />,
});

/** Hauptweg ab meta.signal_start, kompakt (hoechstens 5 Schritte); "ganz zeigen" oeffnet die Signalweg-Ansicht. */
export function SignalBlock({ sourceId, start, onOpenDetail }: { sourceId: string; start: string; onOpenDetail: (detail: DetailRef) => void }) {
  return (
    <LazyBlock kind="signal" title="Signalweg" source={`ab ${start} · Klemmenplan, Programm und Plan`} skeleton={<BlockSkeleton rows={3} label="Signalweg wird geladen" />} testId="block-signal">
      {() => <SignalView sourceId={sourceId} tag={start} variant="compact" onOpenDetail={onOpenDetail} />}
    </LazyBlock>
  );
}
