"use client";

import { CheckCircle2, ChevronLeft, CircleDot, RotateCcw, Trash2 } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";

import { outcomeOf, type Incident } from "./incidents";

export const MAX_FINDING = 2000;

/**
 * Kopf eines Stoerfalls: Titel, Stand (nie nur ueber Farbe), "Erledigt" mit optionalem Befund in einem Satz,
 * "Wieder öffnen" und Loeschen mit Rueckfrage. Am Handy fuehrt "Zurück" zur Liste.
 */
export function IncidentHeader({
  incident,
  onBack,
  onResolve,
  onReopen,
  onDelete,
}: {
  incident: Incident;
  onBack: () => void;
  onResolve: (finding: string) => Promise<boolean>;
  onReopen: () => Promise<boolean>;
  onDelete: () => Promise<boolean>;
}) {
  const [dialog, setDialog] = useState<"resolve" | "delete" | null>(null);
  const [finding, setFinding] = useState("");
  const [busy, setBusy] = useState(false);
  const resolved = outcomeOf(incident) === "resolved";
  const pending = Boolean(incident.pending);

  async function run(action: () => Promise<boolean>) {
    setBusy(true);
    const ok = await action();
    setBusy(false);
    if (ok) {
      setDialog(null);
      setFinding("");
    }
  }

  return (
    <header className="flex flex-wrap items-center gap-x-2 gap-y-1 border-b border-border bg-card px-2 py-1.5 sm:px-3" data-testid="incident-header">
      <button type="button" onClick={onBack} className="grid size-11 shrink-0 place-items-center rounded-md text-muted-foreground hover:bg-secondary hover:text-foreground lg:hidden" aria-label="Zurück zur Liste">
        <ChevronLeft className="size-5" />
      </button>
      <div className="min-w-0 flex-1 py-1">
        <h2 className="line-clamp-2 text-[15px] font-semibold leading-snug">{incident.title}</h2>
        <p className="flex items-center gap-1 text-xs text-muted-foreground" data-testid="incident-status">
          {resolved ? <CheckCircle2 className="size-3.5" aria-hidden /> : <CircleDot className="size-3.5" aria-hidden />}
          {pending ? "wird angelegt …" : resolved ? "Erledigt" : "Offen"}
          {resolved && incident.finding && <span className="min-w-0 truncate">· Befund: {incident.finding}</span>}
        </p>
      </div>
      <div className="flex shrink-0 items-center gap-1">
        {resolved ? (
          <Button variant="outline" className="h-11 px-3" disabled={busy || pending} onClick={() => void run(onReopen)}>
            <RotateCcw /> Wieder öffnen
          </Button>
        ) : (
          <Button className="h-11 px-3" disabled={busy || pending} onClick={() => setDialog("resolve")}>
            <CheckCircle2 /> Erledigt
          </Button>
        )}
        <Button variant="ghost" className="size-11" disabled={busy || pending} onClick={() => setDialog("delete")} aria-label="Störfall löschen">
          <Trash2 />
        </Button>
      </div>

      <Dialog open={dialog === "resolve"} onOpenChange={(open) => !open && setDialog(null)}>
        <DialogContent showCloseButton={false}>
          <form
            className="grid gap-4"
            onSubmit={(event) => {
              event.preventDefault();
              void run(() => onResolve(finding.trim()));
            }}
          >
            <DialogHeader>
              <DialogTitle>Störfall erledigt</DialogTitle>
              <DialogDescription>Optional ein Satz zum Befund. Er hilft bei der nächsten passenden Meldung.</DialogDescription>
            </DialogHeader>
            <label className="grid gap-1.5 text-sm">
              <span className="text-muted-foreground">Befund (optional)</span>
              <Input value={finding} onChange={(event) => setFinding(event.target.value)} maxLength={MAX_FINDING} placeholder="z. B. Motorschutz ausgelöst, zurückgesetzt" className="h-11" autoFocus />
            </label>
            <DialogFooter>
              <Button type="button" variant="outline" className="h-11" onClick={() => setDialog(null)}>
                Abbrechen
              </Button>
              <Button type="submit" className="h-11" disabled={busy}>
                Erledigt
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog open={dialog === "delete"} onOpenChange={(open) => !open && setDialog(null)}>
        <DialogContent showCloseButton={false}>
          <DialogHeader>
            <DialogTitle>Störfall löschen?</DialogTitle>
            <DialogDescription>„{incident.title}“ und der ganze Verlauf werden gelöscht. Das lässt sich nicht rückgängig machen.</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button type="button" variant="outline" className="h-11" onClick={() => setDialog(null)}>
              Abbrechen
            </Button>
            <Button type="button" className="h-11" disabled={busy} onClick={() => void run(onDelete)}>
              Löschen
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </header>
  );
}
