"use client";

import { Check, Minus, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { CitationChip } from "@/components/chat/CitationChip";
import type { PageTarget } from "@/components/PageViewer";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { diagnoses, type Diagnosis, type DiagnosisStep, type StepStatus } from "@/lib/api";
import { cn } from "@/lib/utils";

const STATUS_BUTTONS: { status: StepStatus; label: string; icon: typeof Check; active: string }[] = [
  { status: "ok", label: "in Ordnung", icon: Check, active: "border-ok bg-ok text-white" },
  { status: "nok", label: "Fehler gefunden", icon: X, active: "border-danger bg-danger text-white" },
  { status: "skip", label: "übersprungen", icon: Minus, active: "border-muted-foreground bg-muted-foreground text-white" },
];

/** Checkliste einer laufenden Fehlersuche: Schritte abhaken, Notizen, Abschluss mit Befund. */
export function DiagnosisRunner({
  diagnosis,
  schematic,
  onChanged,
  onClose,
  onOpen,
}: {
  diagnosis: Diagnosis;
  schematic: { document_id: string; filename: string } | null;
  onChanged: (diagnosis: Diagnosis) => void;
  onClose: () => void;
  onOpen: (target: PageTarget) => void;
}) {
  // Schritte lokal fuehren (sofort sichtbar); der Server speichert je Schritt und fuehrt zusammen.
  // Antworten aendern den lokalen Stand nicht, damit langsame Antworten keine neueren Klicks ueberschreiben.
  const [steps, setSteps] = useState<DiagnosisStep[]>(diagnosis.steps);
  const [finding, setFinding] = useState(diagnosis.finding);
  const [addToFaults, setAddToFaults] = useState(true);
  const [saving, setSaving] = useState(false);
  const closed = useRef(false);
  useEffect(() => () => void (closed.current = true), []);
  const done = steps.filter((s) => s.status !== "open").length;
  const firstNok = steps.find((s) => s.status === "nok");

  function setStep(index: number, change: Pick<Partial<DiagnosisStep>, "status" | "note">) {
    setSteps((current) => current.map((step, i) => (i === index ? { ...step, ...change } : step)));
    diagnoses.updateStep(diagnosis.id, index, change).catch((err: Error) => {
      if (!closed.current) toast.error(`Schritt ${index + 1} nicht gespeichert: ${err.message}`);
    });
  }

  async function finish(outcome: "resolved" | "unresolved") {
    setSaving(true);
    try {
      const text = finding.trim() || (firstNok ? `${firstNok.text}${firstNok.note ? `: ${firstNok.note}` : ""}` : "");
      onChanged(await diagnoses.finish(diagnosis.id, { outcome, finding: text, add_to_faults: addToFaults && !!text }));
      closed.current = true;
      toast.success(outcome === "resolved" ? "Fehlersuche abgeschlossen, Befund gespeichert" : "Als nicht behoben gespeichert");
      onClose();
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="border border-line bg-card">
      <div className="flex items-center gap-3 bg-nav px-4 py-2 text-white">
        <span className="font-mono text-xs font-semibold tracking-[0.06em]">FEHLERSUCHE</span>
        <span className="min-w-0 flex-1 truncate text-[13px]">{diagnosis.title}</span>
        <span className="font-mono text-xs text-nav-foreground">
          {done}/{steps.length}
        </span>
        <button onClick={onClose} aria-label="Schließen" className="hover:text-white/70">
          <X className="size-4" />
        </button>
      </div>

      <ol className="divide-y divide-border">
        {steps.map((step, index) => (
          <li key={index} className={cn("px-4 py-2.5", step.status === "nok" && "bg-danger/5")}>
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-sm font-semibold text-primary">{index + 1}</span>
              <span className={cn("min-w-0 flex-1 text-[13px]", step.status === "skip" && "text-muted-foreground line-through")}>{step.text}</span>
              {step.ref && schematic && (
                <CitationChip
                  label={`${step.tag} ${step.ref}`}
                  onClick={() =>
                    onOpen({ documentId: schematic.document_id, filename: schematic.filename, reference: step.ref, label: `Stromlaufplan ${step.ref}`, tag: step.tag || null })
                  }
                />
              )}
              <div className="flex gap-1">
                {STATUS_BUTTONS.map(({ status, label, icon: Icon, active }) => (
                  <button
                    key={status}
                    type="button"
                    title={label}
                    aria-label={`Schritt ${index + 1}: ${label}`}
                    onClick={() => setStep(index, { status: step.status === status ? "open" : status })}
                    className={cn("grid size-7 place-items-center border", step.status === status ? active : "border-border bg-background text-muted-foreground hover:border-foreground")}
                  >
                    <Icon className="size-3.5" />
                  </button>
                ))}
              </div>
            </div>
            {step.status === "nok" && (
              <input
                defaultValue={step.note}
                placeholder="Was genau? z. B. Kontakt 3/4 verbrannt, Phase V fehlt"
                onBlur={(e) => e.target.value !== step.note && setStep(index, { note: e.target.value })}
                className="mt-2 h-8 w-full border border-border bg-background px-2 text-[13px]"
              />
            )}
          </li>
        ))}
      </ol>

      <div className="space-y-2 border-t border-line px-4 py-3">
        <label className="block text-[13px]">
          <span className="text-muted-foreground">Befund (tatsächliche Ursache)</span>
          <Textarea
            value={finding}
            onChange={(e) => setFinding(e.target.value)}
            rows={2}
            placeholder={firstNok ? `z. B. ${firstNok.text}` : "Was war die Ursache, was wurde getan?"}
          />
        </label>
        <label className="flex items-center gap-2 text-[13px]">
          <input type="checkbox" checked={addToFaults} onChange={(e) => setAddToFaults(e.target.checked)} />
          Befund datiert in die Fehlerliste übernehmen
        </label>
        <div className="flex flex-wrap gap-2">
          <Button disabled={saving} onClick={() => finish("resolved")}>
            Behoben
          </Button>
          <Button variant="outline" className="border-line" disabled={saving} onClick={() => finish("unresolved")}>
            Nicht behoben
          </Button>
        </div>
      </div>
    </section>
  );
}
