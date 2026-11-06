"use client";

import { EyeOff, Undo2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { plant, type MachineMap, type MapPartPatch } from "@/lib/api";
import { correctionOf, zoneOf, zoneTitle } from "@/lib/model";

/**
 * Teil im Modell korrigieren (SIN-1217): Bezeichnung, Zone, ausblenden, zuruecknehmen. Die Korrektur liegt am
 * Server (map_overrides) und ueberlebt "Neu verarbeiten". Im Demo-Modus (403) verschwinden die Bedienelemente.
 */
export function PartCorrection({
  machineId,
  tag,
  map,
  label,
  onChanged,
  onHidden,
}: {
  machineId: string;
  tag: string;
  map: MachineMap | null | undefined;
  label: string;
  onChanged: () => void;
  onHidden: () => void;
}) {
  const [draft, setDraft] = useState(label);
  const [busy, setBusy] = useState(false);
  const [readOnly, setReadOnly] = useState(false);
  const zone = zoneOf(map, tag);
  const correction = correctionOf(map, tag);

  if (!map || !zone) return null;
  if (readOnly) return <p className="text-footnote text-muted-foreground" data-testid="part-correction-readonly">Korrekturen sind in der Demo gesperrt.</p>;

  async function run(call: () => Promise<unknown>, done: string, after = onChanged) {
    setBusy(true);
    try {
      await call();
      toast.success(done);
      after();
    } catch (error) {
      if ((error as { status?: number }).status === 403) setReadOnly(true);
      else toast.error("Speichern hat nicht geklappt. Erneut versuchen.");
    } finally {
      setBusy(false);
    }
  }
  const patch = (body: MapPartPatch, done: string, after?: () => void) => run(() => plant.correctPart(machineId, tag, body), done, after);
  const trimmed = draft.trim();

  return (
    <section className="space-y-3" aria-labelledby="part-correction-title" data-testid="part-correction">
      <h3 id="part-correction-title" className="text-footnote font-semibold text-muted-foreground uppercase">
        Im Modell korrigieren
        {correction && <span className="ml-2 font-normal normal-case">von Hand geändert</span>}
      </h3>
      <form
        className="flex items-end gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          // leeres Feld nimmt die eigene Bezeichnung zurueck
          void patch({ label: trimmed || null }, trimmed ? `${tag} heißt jetzt „${trimmed}“.` : `Bezeichnung von ${tag} zurückgenommen.`);
        }}
      >
        <label className="min-w-0 flex-1 space-y-1">
          <span className="block text-footnote text-muted-foreground">Bezeichnung</span>
          <Input value={draft} maxLength={200} onChange={(e) => setDraft(e.target.value)} disabled={busy} className="h-11" />
        </label>
        <Button type="submit" variant="outline" className="h-11" disabled={busy || trimmed === label.trim()}>
          Speichern
        </Button>
      </form>
      <label className="block space-y-1">
        <span className="block text-footnote text-muted-foreground">Zone</span>
        <select
          value={zone.code}
          disabled={busy}
          onChange={(e) => {
            const target = map.zones.find((z) => z.code === e.target.value);
            if (target) void patch({ zone_code: target.code }, `${tag} liegt jetzt in ${zoneTitle(target)}.`);
          }}
          className="min-h-11 w-full rounded-md border border-border bg-card px-2 text-subhead"
        >
          {map.zones.map((z) => (
            <option key={z.id} value={z.code}>
              {zoneTitle(z)}
            </option>
          ))}
        </select>
      </label>
      <div className="flex flex-wrap gap-2">
        <Button type="button" variant="outline" className="h-11" disabled={busy} onClick={() => void patch({ hidden: true }, `${tag} ausgeblendet. Unter „Ausgeblendete zeigen“ wieder einblenden.`, () => { onChanged(); onHidden(); })}>
          <EyeOff className="size-4" /> Ausblenden
        </Button>
        {correction && (
          <Button type="button" variant="ghost" className="h-11 text-primary" disabled={busy} onClick={() => void run(() => plant.resetPart(machineId, tag), `Korrektur an ${tag} zurückgenommen.`)}>
            <Undo2 className="size-4" /> Korrektur zurücknehmen
          </Button>
        )}
      </div>
    </section>
  );
}
