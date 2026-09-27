"use client";

import { RefreshCw, Sparkles } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { plant } from "@/lib/api";

/**
 * Tab „Ablauf“: bettet die eigenstaendige Animationsseite (public/ablauf, SVG + Vanilla JS) ein.
 * Die Seite laedt nur das JSON aus dem Cache; ein Modell laeuft hier nie. Extraktion nur auf Knopfdruck.
 */
export function FlowTab({ machineId, hasSource }: { machineId: string; hasSource: boolean }) {
  const [version, setVersion] = useState(0);
  const [busy, setBusy] = useState(false);

  async function extract(force: boolean) {
    if (!confirm(force ? "Ablauf neu extrahieren? Kostet API-Tokens." : "Ablauf aus der Dokumentation extrahieren? Kostet API-Tokens, einmal je Dokumentstand.")) return;
    setBusy(true);
    try {
      const flow = await plant.extractFlow(machineId, force);
      toast.success(
        flow.meta.cached
          ? "Ablauf aus dem Cache, keine Kosten."
          : `Ablauf extrahiert: ${flow.io_points.length} I/O, ${flow.steps.length} Schritte, ${flow.meta.total.cost_usd.toFixed(4)} USD, ${(flow.meta.total.latency_ms / 1000).toFixed(1)} s`,
      );
      setVersion((v) => v + 1);
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (!hasSource) {
    return <p className="text-sm text-muted-foreground">Keine Dokumentation verknüpft. Im Tab „Dokumente“ eine Wissensquelle wählen.</p>;
  }
  const src = `/ablauf/index.html?src=${encodeURIComponent(plant.flowUrl(machineId))}&v=${version}`;
  return (
    <div className="flex h-full flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="text-muted-foreground">
          Schrittkette aus Handbuch, AWL und Symboltabelle. Anzeige liest nur das gespeicherte JSON. Klick auf Sensor, Aktor oder Schritt zeigt den Beleg.
        </span>
        <Button size="sm" variant="outline" className="ml-auto" onClick={() => setVersion((v) => v + 1)} disabled={busy}>
          <RefreshCw className="size-3.5" />
          Neu laden
        </Button>
        <Button size="sm" onClick={() => extract(false)} disabled={busy}>
          <Sparkles className="size-3.5" />
          {busy ? "Extrahiere …" : "Ablauf extrahieren (kostet Tokens)"}
        </Button>
      </div>
      <iframe key={src} src={src} title="Ablauf-Animation" className="min-h-[560px] flex-1 border border-line bg-card" />
    </div>
  );
}
