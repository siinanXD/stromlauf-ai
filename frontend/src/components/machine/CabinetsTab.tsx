"use client";

import { ImageUp } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { CabinetEditor } from "@/components/CabinetEditor";
import type { PageTarget } from "@/components/PageViewer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { plant, type MachineDetail } from "@/lib/api";

/** Schaltschrankbilder mit Hotspots (Foto oder Aufbauplan), unveraendert aus der alten Maschinenseite. */
export function CabinetsTab({
  machine,
  highlightTag,
  highlightTags,
  onChanged,
  onOpenPage,
}: {
  machine: MachineDetail;
  highlightTag: string | null;
  highlightTags?: string[];
  onChanged: () => void;
  onOpenPage: (target: PageTarget) => void;
}) {
  const [title, setTitle] = useState("Schaltschrank");

  async function upload(file: File | undefined) {
    if (!file) return;
    await plant.uploadCabinet(machine.id, file, title).catch((err: Error) => toast.error(err.message));
    onChanged();
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <Input value={title} onChange={(e) => setTitle(e.target.value)} className="h-8 w-56" aria-label="Titel des Schaltschrankbilds" />
        <Button size="sm" variant="outline" className="border-line" asChild>
          <label className="cursor-pointer">
            <ImageUp className="size-3.5" />
            Foto oder Aufbauplan
            <input type="file" accept="image/*" className="hidden" onChange={(e) => upload(e.target.files?.[0])} />
          </label>
        </Button>
      </div>
      {machine.cabinets.length === 0 && (
        <p className="text-sm text-muted-foreground">
          Foto vom offenen Schaltschrank oder den Aufbauplan hochladen, Bauteile markieren (oder erkennen lassen) und per Klick zur Doku springen.
        </p>
      )}
      {machine.cabinets.map((cabinet) => (
        <section key={cabinet.id} className="border border-line bg-card p-4">
          <div className="mb-3 flex items-center gap-3">
            <h3 className="font-mono text-sm font-semibold uppercase tracking-[0.04em]">{cabinet.title}</h3>
            <span className="text-xs text-muted-foreground">
              {cabinet.width}×{cabinet.height}
            </span>
            <button
              onClick={async () => {
                if (!confirm(`„${cabinet.title}“ mit ${cabinet.hotspots.length} Markierungen löschen?`)) return;
                await plant.deleteCabinet(cabinet.id).catch((err: Error) => toast.error(err.message));
                onChanged();
              }}
              className="ml-auto text-sm text-muted-foreground hover:text-danger"
            >
              löschen
            </button>
          </div>
          <CabinetEditor cabinet={cabinet} machineId={machine.id} highlightTag={highlightTag} highlightTags={highlightTags} onChanged={onChanged} onOpenPage={onOpenPage} />
        </section>
      ))}
    </div>
  );
}
