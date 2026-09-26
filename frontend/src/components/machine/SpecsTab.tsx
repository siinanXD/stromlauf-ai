"use client";

import { ExternalLink, Plus, X } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { plant, type MachineSpec } from "@/lib/api";
import { sourceLink } from "@/lib/site";

const EMPTY: MachineSpec = { label: "", value: "", unit: "", source: "" };
const CELL = "h-8 w-full border border-border bg-background px-2 text-[13px]";
const HEAD = "px-3 py-2 text-left font-mono text-[11px] font-semibold uppercase tracking-[0.06em] text-muted-foreground";

function Source({ source }: { source: string }) {
  const link = sourceLink(source);
  if (!link) return <span className="text-muted-foreground">{source || "–"}</span>;
  return (
    <a href={link.href} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-primary hover:underline">
      {link.host}
      <ExternalLink className="size-3" />
    </a>
  );
}

/** Kennzahlen einer Maschine mit Quelle; die erste Kennzahl erscheint auf der Kachel in der Halle. */
export function SpecsTab({ machineId, onSaved }: { machineId: string; onSaved: () => void }) {
  const [specs, setSpecs] = useState<MachineSpec[] | null>(null);
  const [draft, setDraft] = useState<MachineSpec[] | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    plant
      .getSpecs(machineId)
      .then(setSpecs)
      .catch((err: Error) => toast.error(`Kennzahlen nicht geladen: ${err.message}`));
  }, [machineId]);

  function edit(index: number, change: Partial<MachineSpec>) {
    setDraft((rows) => rows && rows.map((row, i) => (i === index ? { ...row, ...change } : row)));
  }

  async function save() {
    if (!draft) return;
    setSaving(true);
    try {
      setSpecs(await plant.replaceSpecs(machineId, draft));
      setDraft(null);
      toast.success("Kennzahlen gespeichert");
      onSaved();
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  if (specs === null) return <p className="text-muted-foreground">Lade Kennzahlen …</p>;

  return (
    <section className="max-w-4xl space-y-3">
      <div className="flex items-center gap-3">
        <p className="text-[13px] text-muted-foreground">
          Die erste Kennzahl steht auf der Kachel in der Halle. „Richtwert“ heißt: keine Herstellerangabe.
        </p>
        {draft === null && (
          <Button size="sm" variant="outline" className="ml-auto border-line" onClick={() => setDraft(specs.length ? specs : [{ ...EMPTY }])}>
            Bearbeiten
          </Button>
        )}
      </div>

      <div className="overflow-x-auto border border-line bg-card">
        <table className="w-full min-w-[560px] border-collapse text-[13px]">
          <thead className="border-b border-line">
            <tr>
              <th className={HEAD}>Kennzahl</th>
              <th className={HEAD}>Wert</th>
              <th className={HEAD}>Einheit</th>
              <th className={HEAD}>Quelle</th>
              {draft && <th className="w-8" />}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {draft
              ? draft.map((row, index) => (
                  <tr key={index}>
                    <td className="px-2 py-1.5">
                      <input aria-label="Kennzahl" value={row.label} onChange={(e) => edit(index, { label: e.target.value })} placeholder="Leistung" className={CELL} />
                    </td>
                    <td className="px-2 py-1.5">
                      <input aria-label="Wert" value={row.value} onChange={(e) => edit(index, { value: e.target.value })} placeholder="220" className={CELL} />
                    </td>
                    <td className="px-2 py-1.5">
                      <input aria-label="Einheit" value={row.unit} onChange={(e) => edit(index, { unit: e.target.value })} placeholder="Pakete/min" className={CELL} />
                    </td>
                    <td className="px-2 py-1.5">
                      <input aria-label="Quelle" value={row.source} onChange={(e) => edit(index, { source: e.target.value })} placeholder="https://… oder Richtwert" className={CELL} />
                    </td>
                    <td className="px-1">
                      <button
                        type="button"
                        aria-label={`Kennzahl ${index + 1} entfernen`}
                        onClick={() => setDraft(draft.filter((_, i) => i !== index))}
                        className="grid size-7 place-items-center text-muted-foreground hover:text-danger"
                      >
                        <X className="size-3.5" />
                      </button>
                    </td>
                  </tr>
                ))
              : specs.map((spec) => (
                  <tr key={spec.id}>
                    <td className="px-3 py-2">{spec.label}</td>
                    <td className="px-3 py-2 font-mono font-semibold">{spec.value}</td>
                    <td className="px-3 py-2 font-mono text-muted-foreground">{spec.unit}</td>
                    <td className="px-3 py-2">
                      <Source source={spec.source} />
                    </td>
                  </tr>
                ))}
            {!draft && specs.length === 0 && (
              <tr>
                <td colSpan={4} className="px-3 py-3 text-muted-foreground">
                  Noch keine Kennzahlen. „Bearbeiten“ legt die erste an.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {draft && (
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="outline" className="border-line" onClick={() => setDraft([...draft, { ...EMPTY }])}>
            <Plus className="size-3.5" />
            Kennzahl
          </Button>
          <Button size="sm" className="ml-auto" disabled={saving} onClick={save}>
            Speichern
          </Button>
          <Button size="sm" variant="outline" className="border-line" disabled={saving} onClick={() => setDraft(null)}>
            Abbrechen
          </Button>
        </div>
      )}
    </section>
  );
}
