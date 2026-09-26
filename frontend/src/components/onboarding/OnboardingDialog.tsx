"use client";

import { FileStack } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { api, DOC_TYPE_LABELS, MACHINE_TYPE_LABELS, onboarding, type KnowledgeSource, type MachineType, type OnboardingProposal } from "@/lib/api";

const TYPES = Object.keys(MACHINE_TYPE_LABELS) as MachineType[];

/** Maschine aus einer Wissensquelle anlegen: Vorschlag pruefen, Fehler auswaehlen, uebernehmen. */
export function OnboardingDialog({ hallId, onCreated }: { hallId: string; onCreated: () => void }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [sources, setSources] = useState<KnowledgeSource[]>([]);
  const [sourceId, setSourceId] = useState("");
  const [proposal, setProposal] = useState<OnboardingProposal | null>(null);
  const [name, setName] = useState("");
  const [type, setType] = useState<MachineType>("other");
  const [chosen, setChosen] = useState<Set<number>>(new Set());
  const [busy, setBusy] = useState(false);
  const latest = useRef("");

  useEffect(() => {
    if (open) api.listSources().then(setSources).catch(() => setSources([]));
  }, [open]);

  function openDialog() {
    // Jedes Oeffnen beginnt leer, kein Vorschlag vom letzten Mal
    latest.current = "";
    setSourceId("");
    setProposal(null);
    setOpen(true);
  }

  async function load(id: string) {
    latest.current = id;
    setSourceId(id);
    setProposal(null);
    if (!id) return;
    try {
      const result = await onboarding.proposal(id);
      if (latest.current !== id) return; // spaete Antwort einer frueher gewaehlten Quelle
      setProposal(result);
      setName(result.name);
      setType(result.machine_type);
      setChosen(new Set(result.faults.map((_, i) => i)));
    } catch (err) {
      toast.error((err as Error).message);
    }
  }

  async function create() {
    if (!proposal) return;
    setBusy(true);
    try {
      const machine = await onboarding.create(hallId, {
        source_id: proposal.source_id,
        name,
        machine_type: type,
        faults: proposal.faults.filter((_, i) => chosen.has(i)),
      });
      toast.success(`${machine.name} angelegt`);
      setOpen(false);
      onCreated();
      router.push(`/werk/maschine/${machine.id}`);
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Button size="sm" variant="outline" className="border-line" onClick={openDialog}>
        <FileStack className="size-3.5" />
        Aus Dokumentation anlegen
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[90vh] overflow-y-auto rounded-none sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle className="font-mono uppercase tracking-[0.04em]">Maschine aus Dokumentation</DialogTitle>
            <DialogDescription>
              Name, Typ und Fehlerliste werden aus Stückliste und Handbuch vorgeschlagen. Kein KI-Aufruf, keine Kosten.
            </DialogDescription>
          </DialogHeader>

          <label className="grid gap-1 text-sm">
            <span className="text-muted-foreground">Wissensquelle</span>
            <select value={sourceId} onChange={(e) => load(e.target.value)} className="h-9 border border-border bg-background px-2">
              <option value="">Quelle wählen …</option>
              {sources.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} ({s.document_count} Dokumente)
                </option>
              ))}
            </select>
          </label>

          {proposal && (
            <div className="space-y-4 text-sm">
              <div className="grid gap-3 sm:grid-cols-[1fr_200px]">
                <label className="grid gap-1">
                  <span className="text-muted-foreground">Name</span>
                  <Input value={name} onChange={(e) => setName(e.target.value)} />
                </label>
                <label className="grid gap-1">
                  <span className="text-muted-foreground">Typ</span>
                  <select value={type} onChange={(e) => setType(e.target.value as MachineType)} className="h-8 border border-border bg-background px-2">
                    {TYPES.map((t) => (
                      <option key={t} value={t}>
                        {MACHINE_TYPE_LABELS[t]}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              <p className="font-mono text-xs text-muted-foreground">
                {proposal.devices} Betriebsmittel · {proposal.documents.length} Dokumente (
                {[...new Set(proposal.documents.map((d) => DOC_TYPE_LABELS[d.doc_type] ?? d.doc_type))].join(", ")})
              </p>

              <section>
                <div className="mb-1.5 flex items-center justify-between">
                  <h3 className="font-mono text-[11px] font-semibold uppercase tracking-[0.06em] text-muted-foreground">
                    Fehlerliste · {chosen.size} von {proposal.faults.length}
                  </h3>
                  {proposal.faults.length > 0 && (
                    <button
                      className="text-xs text-primary hover:underline"
                      onClick={() => setChosen(chosen.size === proposal.faults.length ? new Set() : new Set(proposal.faults.map((_, i) => i)))}
                    >
                      {chosen.size === proposal.faults.length ? "keine" : "alle"}
                    </button>
                  )}
                </div>
                <ul className="max-h-64 divide-y divide-border overflow-y-auto border border-line">
                  {proposal.faults.map((fault, i) => (
                    <li key={i}>
                      <label className="flex cursor-pointer gap-2 px-3 py-2">
                        <input
                          type="checkbox"
                          checked={chosen.has(i)}
                          onChange={() => {
                            const next = new Set(chosen);
                            if (next.has(i)) next.delete(i);
                            else next.add(i);
                            setChosen(next);
                          }}
                        />
                        <span className="min-w-0">
                          <span className="block font-medium">{fault.symptom}</span>
                          <span className="block text-xs text-muted-foreground">
                            {fault.cause || fault.fix} · {fault.doc_ref}
                          </span>
                        </span>
                      </label>
                    </li>
                  ))}
                  {proposal.faults.length === 0 && <li className="px-3 py-2 text-muted-foreground">Keine Fehlertabelle gefunden.</li>}
                </ul>
              </section>

              {proposal.hints.map((hint) => (
                <p key={hint} className="border-l-[3px] border-nav bg-secondary px-3 py-1.5 text-xs">
                  {hint}
                </p>
              ))}
            </div>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>
              Abbrechen
            </Button>
            <Button disabled={!proposal || !name.trim() || busy} onClick={create}>
              Anlegen
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
