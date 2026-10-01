"use client";

import dynamic from "next/dynamic";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import type { SignalMainData } from "@/lib/api";
import type { DetailRef } from "@/lib/detail";

import { isPart } from "./planTarget";
import { SignalPlanPage } from "./SignalPlanPage";
import { COLUMN_LABELS, KIND_LABELS, nodeTitle, sheetText } from "./signalColumns";

/** xyflow nur am PC und erst bei Bedarf; die Kette am Handy kommt ohne aus. */
const SignalGraph = dynamic(() => import("./SignalGraph").then((mod) => mod.SignalGraph), {
  ssr: false,
  loading: () => <div className="size-full animate-pulse bg-bg-fill" aria-label="Grafik wird geladen" />,
});

/**
 * PC-Ansicht ab 1024 px (Figma "Desktop · Signalweg Vollbild"): oben die Grafik in festen Spalten, darunter die
 * Karte "Ausgewählt" mit Knoten, Aktionen und seiner Planseite (Netzwerke: AWL-Code). Ein Klick waehlt; Bauteil-
 * Detail und "Von hier verfolgen" sind Knoepfe, damit die Grafik beim Ansehen der Planseite stehen bleibt.
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
  const sheet = selected ? sheetText(selected.ref) : null;

  return (
    <div className="@container flex min-h-[640px] flex-1 flex-col gap-3 pb-6">
      <div className="min-h-[300px] flex-[3]">
        <SignalGraph data={data} selected={selectedId} onSelect={(node) => setSelectedId(node.id)} />
      </div>
      {selected && (
        <section
          className="mx-4 flex flex-col gap-6 rounded-[20px] bg-card p-6 shadow-card lg:mx-6 @4xl:flex-row"
          aria-label={`Ausgewählt: ${nodeTitle(selected)}`}
        >
          <div className="min-w-0 flex-1 space-y-2">
            <p className="text-footnote font-semibold text-muted-foreground uppercase">Ausgewählt</p>
            <h3 className="text-title-3">
              <span className="font-mono">{nodeTitle(selected)}</span>
              {selected.label && ` · ${selected.label}`}
            </h3>
            <p className="text-body text-muted-foreground">
              {[KIND_LABELS[selected.kind], selected.column ? COLUMN_LABELS[selected.column] : "Abzweig", sheet].filter(Boolean).join(" · ")}
            </p>
            {(isPart(selected) || selected.id !== data.start) && (
              <div className="flex flex-wrap gap-3 pt-1">
                {isPart(selected) && (
                  <Button className="min-h-11 px-4" onClick={() => onOpenDetail({ kind: "part", tag: selected.id })}>
                    Bauteil öffnen
                  </Button>
                )}
                {selected.id !== data.start && (
                  <Button variant="outline" className="min-h-11 px-4" onClick={() => onFollow(selected.id)}>
                    Von hier weiter verfolgen
                  </Button>
                )}
              </div>
            )}
          </div>
          <div className="h-[280px] min-w-0 @4xl:w-[420px] @4xl:shrink-0">
            {selected.kind === "network" ? (
              <section className="flex size-full min-h-0 flex-col overflow-hidden rounded-md bg-bg-grouped" aria-label="AWL-Code">
                {selected.label && <p className="px-3 pt-2 text-footnote font-semibold">{selected.label}</p>}
                <pre className="min-h-0 flex-1 overflow-auto px-3 py-2 font-mono text-caption-1">{selected.detail || "Kein Code hinterlegt."}</pre>
              </section>
            ) : selected.kind === "variable" ? (
              <p className="grid size-full place-items-center rounded-md bg-bg-grouped p-6 text-center text-subhead text-muted-foreground">
                {nodeTitle(selected)} steht nur im SPS-Programm, nicht im Plan.
              </p>
            ) : (
              <SignalPlanPage sourceId={sourceId} node={selected} schematic={data.schematic} onOpenPlan={(target) => onOpenDetail({ kind: "plan", target })} />
            )}
          </div>
        </section>
      )}
    </div>
  );
}
