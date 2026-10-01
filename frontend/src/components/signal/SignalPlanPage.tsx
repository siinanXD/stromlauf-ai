"use client";

import { Expand, FileText } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { PageCanvas, type PageTarget } from "@/components/PageViewer";
import { Button } from "@/components/ui/button";
import { locate, type LocateResult, type SignalMainData, type SignalMainNode } from "@/lib/api";

import { findPlanTarget, schematicTarget } from "./planTarget";
import { nodeTitle } from "./signalColumns";

type Spot = { target: PageTarget; page: number; box: LocateResult["box"]; column: number | null };

/**
 * Planseite des gewaehlten Knotens unter der Grafik, mit markierter Spalte und Zoom. Blattverweis und Stromlaufplan
 * kommen aus der Signalweg-Antwort; fehlt der Verweis, sucht die Befundkarte die Stelle.
 */
export function SignalPlanPage({
  sourceId,
  node,
  schematic,
  onOpenPlan,
}: {
  sourceId: string;
  node: SignalMainNode;
  schematic: SignalMainData["schematic"];
  onOpenPlan: (target: PageTarget) => void;
}) {
  const direct = useMemo(() => schematicTarget(node, schematic), [node, schematic]);
  const key = `${sourceId}|${node.id}`;
  const [found, setFound] = useState<{ key: string; target: PageTarget | null } | null>(null);
  const [spot, setSpot] = useState<Spot | null>(null);
  const [failedPage, setFailedPage] = useState<string | null>(null);

  useEffect(() => {
    if (direct) return;
    let cancelled = false;
    findPlanTarget(sourceId, node.id)
      .then((target) => !cancelled && setFound({ key, target }))
      .catch(() => !cancelled && setFound({ key, target: null }));
    return () => {
      cancelled = true;
    };
  }, [direct, sourceId, node.id, key]);

  // undefined: wird gesucht; null: keine Stelle im Plan
  const target = direct ?? (found?.key === key ? found.target : undefined);

  useEffect(() => {
    if (!target?.reference) return;
    let cancelled = false;
    locate(target.documentId, target.reference)
      .then((result) => !cancelled && setSpot({ target, page: result.page, box: result.box, column: result.column }))
      .catch(() => !cancelled && setSpot({ target, page: target.page ?? 1, box: null, column: null }));
    return () => {
      cancelled = true;
    };
  }, [target]);

  if (target === undefined) return <PlanPlaceholder text="Planseite wird gesucht …" />;
  if (target === null) {
    return <PlanPlaceholder text={`Für ${nodeTitle(node)} ist keine Stelle im Stromlaufplan bekannt.`} />;
  }
  const located = target.reference ? (spot?.target === target ? spot : null) : { target, page: target.page ?? 1, box: null, column: null };
  const pageKey = located ? `${target.documentId}:${located.page}` : null;

  return (
    // Planseite-Karte (Figma): Seite mit markierter Spalte, darunter Blatt/Spalte und "Groß öffnen"
    <section className="flex size-full min-h-0 flex-col gap-2" aria-label="Planseite">
      <div className="min-h-0 flex-1 overflow-hidden rounded-md border border-border bg-white">
        {!located ? (
          <PlanPlaceholder text={`Lade ${target.reference ?? "Planseite"} …`} bare />
        ) : failedPage === pageKey ? (
          <PlanPlaceholder text={`Seite ${located.page} konnte nicht geladen werden.`} bare />
        ) : (
          <PageCanvas
            documentId={target.documentId}
            filename={target.filename}
            page={located.page}
            box={located.box}
            onError={() => setFailedPage(pageKey)}
          />
        )}
      </div>
      <div className="flex items-center gap-2">
        <FileText className="size-5 shrink-0 text-accent" aria-hidden />
        <span className="min-w-0 flex-1">
          <span className="block truncate text-subhead font-semibold">
            {[located ? `Seite ${located.page}` : null, located?.column ? `Spalte ${located.column}` : null].filter(Boolean).join(" · ") || "Planseite"}
          </span>
          <span className="block truncate text-footnote text-muted-foreground">{target.label ?? target.filename}</span>
        </span>
        <Button variant="outline" className="min-h-11 shrink-0 px-3" onClick={() => onOpenPlan(target)}>
          <Expand className="size-4" />
          Groß öffnen
        </Button>
      </div>
    </section>
  );
}

function PlanPlaceholder({ text, bare = false }: { text: string; bare?: boolean }) {
  return (
    <div className={bare ? "flex size-full items-center justify-center p-6" : "flex size-full items-center justify-center rounded-md bg-bg-grouped p-6"}>
      <p className="text-center text-subhead text-muted-foreground">{text}</p>
    </div>
  );
}
