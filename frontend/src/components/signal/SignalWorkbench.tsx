"use client";

import { Crosshair, SquareArrowOutUpRight } from "lucide-react";
import dynamic from "next/dynamic";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import type { SignalMainData } from "@/lib/api";
import type { DetailRef } from "@/lib/detail";

import { isPart } from "./planTarget";
import { SignalPlanPage } from "./SignalPlanPage";
import { COLUMN_LABELS, KIND_LABELS, nodeTitle } from "./signalColumns";

/** xyflow nur am PC und erst bei Bedarf; die Kette am Handy kommt ohne aus. */
const SignalGraph = dynamic(() => import("./SignalGraph").then((mod) => mod.SignalGraph), {
  ssr: false,
  loading: () => <div className="size-full animate-pulse bg-secondary" aria-label="Grafik wird geladen" />,
});

/**
 * PC-Ansicht ab 1024 px: oben die Grafik in festen Spalten, darunter der gewaehlte Knoten mit seiner Planseite
 * (Netzwerke: AWL-Code). Ein Klick waehlt; Bauteil-Detail und "Von hier weiter verfolgen" sind Knoepfe, damit die
 * Grafik beim Ansehen der Planseite stehen bleibt.
 */
export function SignalWorkbench({
  sourceId,
  data,
  onOpenDetail,
  onFollow,
}: {
  sourceId: string;
  data: SignalMainData;
  onOpenDetail: (detail: DetailRef) => void;
  onFollow: (tag: string) => void;
}) {
  const [selectedId, setSelectedId] = useState(data.start);
  const [seen, setSeen] = useState(data);
  if (seen !== data) {
    setSeen(data);
    setSelectedId(data.start);
  }
  const selected = data.nodes.find((node) => node.id === selectedId) ?? null;

  return (
    <div className="flex min-h-[640px] flex-1 flex-col">
      <div className="min-h-[320px] flex-[3] border-b border-line">
        <SignalGraph data={data} selected={selectedId} onSelect={(node) => setSelectedId(node.id)} />
      </div>
      {selected && (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-line px-3 py-1">
          <span className="font-mono text-sm font-semibold">{nodeTitle(selected)}</span>
          <span className="min-w-0 flex-1 truncate text-[13px] text-muted-foreground">
            {[selected.label || KIND_LABELS[selected.kind], selected.column ? COLUMN_LABELS[selected.column] : "Abzweig"].join(" · ")}
          </span>
          {isPart(selected) && (
            <Button variant="ghost" className="min-h-11 rounded-none" onClick={() => onOpenDetail({ kind: "part", tag: selected.id })}>
              <SquareArrowOutUpRight className="size-4" />
              Bauteil öffnen
            </Button>
          )}
          {selected.id !== data.start && (
            <Button variant="ghost" className="min-h-11 rounded-none" onClick={() => onFollow(selected.id)}>
              <Crosshair className="size-4" />
              Von hier weiter verfolgen
            </Button>
          )}
        </div>
      )}
      <div className="min-h-[280px] flex-[2]">
        {selected?.kind === "network" ? (
          <section className="flex size-full min-h-0 flex-col" aria-label="AWL-Code">
            {selected.label && <p className="px-3 pt-2 text-[13px] font-medium">{selected.label}</p>}
            <pre className="min-h-0 flex-1 overflow-auto px-3 py-2 font-mono text-[12px] leading-5">{selected.detail || "Kein Code hinterlegt."}</pre>
          </section>
        ) : selected?.kind === "variable" ? (
          <p className="p-6 text-center text-sm text-muted-foreground">{nodeTitle(selected)} steht nur im SPS-Programm, nicht im Plan.</p>
        ) : selected ? (
          <SignalPlanPage
            sourceId={sourceId}
            node={selected}
            schematic={data.schematic}
            onOpenPlan={(target) => onOpenDetail({ kind: "plan", target })}
          />
        ) : null}
      </div>
    </div>
  );
}
