"use client";

import { FileText, Route } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import type { PageTarget } from "@/components/PageViewer";
import { Button } from "@/components/ui/button";
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { api, type PlanReadResult, type PlanReadStatus, type SignalMissingReason } from "@/lib/api";
import type { DetailRef } from "@/lib/detail";
import { num } from "@/lib/format";
import { cn } from "@/lib/utils";

import { findPlanTarget } from "./planTarget";

/** "0,12"; unter einem Cent "unter 0,01". */
export function usdText(value: number): string {
  return value > 0 && value < 0.01 ? "unter 0,01" : num(value, 2);
}

/** Der Grund in einem Satz, ohne 404-Text. */
export function emptyReasonText(reason: SignalMissingReason, tag: string): string {
  return reason === "no_sources" ? "Keine Tabellen und keine Leitungen im Plan gefunden." : `${tag} kommt im Signalweg nicht vor.`;
}

/** Die naechste Aktion in einem Satz, je nachdem ob es eine Planseite gibt (undefined = wird noch gesucht). */
export function emptyNextText(reason: SignalMissingReason, plan: PageTarget | null | undefined): string | null {
  if (plan === undefined) return null;
  if (reason === "no_sources") {
    return plan
      ? "Im Stromlaufplan nachsehen oder Klemmenplan bzw. SPS-Programm zu den Dokumenten hinzufügen."
      : "Ein Klemmenplan, ein SPS-Programm oder ein Stromlaufplan mit Leitungen in den Dokumenten macht den Signalweg möglich.";
  }
  return plan ? "Im Stromlaufplan nachsehen, wo es steht." : "Auch im Stromlaufplan ist keine Stelle dafür bekannt.";
}

type ModelOffer = { status: PlanReadStatus | null; estimate: PlanReadResult | null };

/**
 * Leerer Zustand der Signalweg-Ansicht: Grund und naechste Aktion, nie rot. "Planseite oeffnen", wenn die Quelle
 * einen Stromlaufplan hat; ausserhalb des Antwortblocks "Mit Modell lesen, ca. X USD", wenn ein Modell eingerichtet
 * ist (Schaetzung per dry_run, Lauf erst nach Bestaetigung).
 */
export function SignalEmpty({
  reason,
  tag,
  sourceId,
  compact = false,
  onOpenDetail,
  onReload,
}: {
  reason: SignalMissingReason;
  tag: string;
  sourceId: string;
  compact?: boolean;
  onOpenDetail: (detail: DetailRef) => void;
  /** Nach dem Lesen mit Modell: Signalweg neu laden. */
  onReload: () => void;
}) {
  const key = `${sourceId}|${tag}`;
  const [found, setFound] = useState<{ key: string; target: PageTarget | null } | null>(null);
  const [offer, setOffer] = useState<{ sourceId: string; value: ModelOffer } | null>(null);
  const [asking, setAsking] = useState(false);
  const [reading, setReading] = useState(false);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    findPlanTarget(sourceId, tag)
      .then((target) => !cancelled && setFound({ key, target }))
      .catch(() => !cancelled && setFound({ key, target: null }));
    return () => {
      cancelled = true;
    };
  }, [sourceId, tag, key]);

  useEffect(() => {
    if (compact) return;
    let cancelled = false;
    const load = async (): Promise<ModelOffer> => {
      const status = await api.planReadStatus(sourceId);
      if (!status.configured || status.cached) return { status, estimate: null };
      return { status, estimate: await api.planRead(sourceId, true) };
    };
    load()
      // Ohne Modell-Endpunkt (oder bei Fehlern) gibt es das Angebot einfach nicht
      .catch((): ModelOffer => ({ status: null, estimate: null }))
      .then((value) => !cancelled && setOffer({ sourceId, value }));
    return () => {
      cancelled = true;
    };
  }, [sourceId, compact]);

  const plan = found?.key === key ? found.target : undefined;
  const model = offer?.sourceId === sourceId ? offer.value : null;
  const estimate = model?.estimate && model.estimate.pages > 0 ? model.estimate : null;
  const next = emptyNextText(reason, plan);

  async function read() {
    setReading(true);
    setFailed(false);
    try {
      const result = await api.planRead(sourceId, false);
      setAsking(false);
      toast.success(`Plan gelesen: ${result.edges ?? 0} Verbindungen erkannt`);
      onReload();
    } catch {
      setFailed(true);
    } finally {
      setReading(false);
    }
  }

  return (
    <div className={cn("rounded-lg bg-card", compact ? "py-1" : "p-4 shadow-card")} data-signal-empty={reason}>
      <p className="flex items-start gap-2 text-subhead">
        <Route className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden />
        <span>{emptyReasonText(reason, tag)}</span>
      </p>
      {next && <p className="mt-1 pl-6 text-footnote text-muted-foreground">{next}</p>}
      {model?.status?.cached && (
        <p className="mt-1 pl-6 text-footnote text-muted-foreground">Auch das Modell hat hier keine Verbindung gefunden.</p>
      )}
      {(plan || estimate) && (
        <div className="mt-3 flex flex-wrap gap-2 pl-6">
          {plan && (
            <Button className="min-h-11 px-4" onClick={() => onOpenDetail({ kind: "plan", target: plan })}>
              <FileText className="size-4" />
              Planseite öffnen
            </Button>
          )}
          {estimate && (
            <Button variant="outline" className="min-h-11 px-4" onClick={() => setAsking(true)}>
              Mit Modell lesen, ca. {usdText(estimate.estimate_usd)} USD
            </Button>
          )}
        </div>
      )}
      {estimate && (
        <Dialog open={asking} onOpenChange={(open) => !reading && setAsking(open)}>
          <DialogContent showCloseButton={false}>
            <DialogHeader>
              <DialogTitle>Plan mit Modell lesen?</DialogTitle>
              <DialogDescription>
                {estimate.model} liest {estimate.pages} {estimate.pages === 1 ? "Seite" : "Seiten"} des Stromlaufplans. Das kostet
                geschätzt ca. {usdText(estimate.estimate_usd)} USD. Erkannte Verbindungen erscheinen danach im Signalweg mit der
                Herkunft „Modell“.
              </DialogDescription>
            </DialogHeader>
            {failed && <p className="text-subhead text-muted-foreground">Das Lesen hat nicht geklappt. Erneut versuchen?</p>}
            <DialogFooter>
              <DialogClose asChild>
                <Button variant="outline" className="min-h-11" disabled={reading}>
                  Abbrechen
                </Button>
              </DialogClose>
              <Button className="min-h-11" onClick={read} disabled={reading}>
                {reading ? "Liest …" : `Lesen, ca. ${usdText(estimate.estimate_usd)} USD`}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
}
