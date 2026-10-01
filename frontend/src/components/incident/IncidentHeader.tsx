"use client";

import { ChevronLeft, Trash2 } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

import { isTempId, outcomeOf, type Incident } from "./incidents";
import { stateLabel, StateIcon } from "./IncidentStatus";

export const MAX_FINDING = 2000;

/** Textknopf der Nav-Leiste; ab 1024 px eine Pille (Figma "Störfall-Kopf"), Trefferflaeche per before: 44 px. */
const ACTION =
  "relative min-h-11 rounded-full px-2 text-headline text-primary before:absolute before:inset-x-0 before:-inset-y-1 before:content-[''] hover:bg-bg-fill disabled:opacity-40 lg:min-h-9 lg:px-4 lg:text-subhead lg:font-semibold";

/**
 * Kopf eines Stoerfalls: Titel, Stand (nie nur ueber Farbe), "Erledigt" mit optionalem Befund in einem Satz,
 * "Wieder öffnen" und Loeschen mit Rueckfrage. Am Handy eine Nav-Leiste mit Milchglas, "‹ Störfälle" fuehrt zur Liste.
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
  // Ohne Server-ID (wird angelegt oder nicht angelegt) gibt es nichts zu erledigen
  const local = isTempId(incident.id);

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
    <header
      className="flex shrink-0 items-center gap-1 border-b-[0.5px] border-border bg-bg-bar px-1 py-1 backdrop-blur-bar lg:gap-3 lg:border-b-0 lg:bg-transparent lg:px-6 lg:pt-5 lg:pb-1 lg:backdrop-blur-none"
      data-testid="incident-header"
    >
      <button
        type="button"
        onClick={onBack}
        className="flex min-h-11 shrink-0 items-center rounded-md pr-1.5 text-body text-primary hover:bg-bg-fill lg:hidden"
        aria-label="Zurück zur Liste"
      >
        <ChevronLeft className="size-6" aria-hidden />
        <span aria-hidden>Störfälle</span>
      </button>
      <div className="min-w-0 flex-1 text-center lg:text-left">
        <h2 className="truncate text-headline lg:line-clamp-2 lg:text-title-3 lg:whitespace-normal">{incident.title}</h2>
        <p className="flex items-center justify-center gap-1 text-caption-1 text-muted-foreground lg:justify-start lg:text-footnote" data-testid="incident-status">
          <StateIcon incident={incident} size="sm" />
          <span className={incident.failed ? "text-danger" : undefined}>{stateLabel(incident, false)}</span>
          {resolved && incident.finding && <span className="min-w-0 truncate">· Befund: {incident.finding}</span>}
        </p>
      </div>
      <div className="flex shrink-0 items-center lg:gap-1">
        {resolved ? (
          <button type="button" className={cn(ACTION, "lg:bg-bg-fill")} disabled={busy || local} onClick={() => void run(onReopen)}>
            Wieder öffnen
          </button>
        ) : (
          <button type="button" className={cn(ACTION, "lg:bg-primary lg:text-primary-foreground lg:hover:bg-primary/85")} disabled={busy || local} onClick={() => setDialog("resolve")}>
            Erledigt
          </button>
        )}
        <button
          type="button"
          className="grid size-11 shrink-0 place-items-center rounded-full text-muted-foreground hover:bg-bg-fill hover:text-foreground disabled:opacity-40"
          disabled={busy || pending}
          onClick={() => setDialog("delete")}
          aria-label="Störfall löschen"
        >
          <Trash2 className="size-5" aria-hidden />
        </button>
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
