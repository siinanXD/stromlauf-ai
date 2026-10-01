"use client";

import { Expand } from "lucide-react";
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
    <section className="flex size-full min-h-0 flex-col" aria-label="Planseite">
      <header className="flex items-center gap-2 border-b border-line px-3 py-1">
        <span className="min-w-0 flex-1 truncate font-mono text-[11px] font-semibold uppercase tracking-[0.06em] text-muted-foreground">
          {[target.label ?? target.filename, located ? `S. ${located.page}` : null, located?.column ? `Spalte ${located.column}` : null]
            .filter(Boolean)
            .join(" · ")}
        </span>
        <Button variant="ghost" className="min-h-11 rounded-none" onClick={() => onOpenPlan(target)}>
          <Expand className="size-4" />
          Groß öffnen
        </Button>
      </header>
      <div className="min-h-0 flex-1 bg-white">
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
    </section>
  );
}

function PlanPlaceholder({ text, bare = false }: { text: string; bare?: boolean }) {
  return (
    <div className={bare ? "flex size-full items-center justify-center p-6" : "flex size-full items-center justify-center bg-secondary/50 p-6"}>
      <p className="text-center text-sm text-muted-foreground">{text}</p>
    </div>
  );
}
