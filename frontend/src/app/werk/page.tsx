"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { SiteCanvas } from "@/components/site/SiteCanvas";
import { HALL_KIND_LABELS, plant, type HallKind, type SiteData, type SiteFlow } from "@/lib/api";
import type { Rect } from "@/lib/site";
import { cn } from "@/lib/utils";

const KINDS = Object.keys(HALL_KIND_LABELS) as HallKind[];

/** Standortplan: alle Hallen mit Lage, Materialfluss zwischen Hallen, gewählte Halle im Panel. */
export default function WerkPage() {
  const [site, setSite] = useState<SiteData | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [newHall, setNewHall] = useState({ name: "", kind: "production" as HallKind });
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    () =>
      plant
        .getSite()
        .then((data) => {
          setSite(data);
          setError(null);
        })
        .catch((err) => setError((err as Error).message)),
    [],
  );
  useEffect(() => {
    load();
  }, [load]);

  const saveRect = useCallback((id: string, rect: Rect) => {
    setSite((current) => current && { ...current, halls: current.halls.map((h) => (h.id === id ? { ...h, ...rect } : h)) });
    plant
      .updateHall(id, { site_x: Math.round(rect.x), site_y: Math.round(rect.y), site_w: Math.round(rect.w), site_h: Math.round(rect.h) })
      .catch((err) => setError((err as Error).message));
  }, []);

  const saveFlows = useCallback(
    async (flows: SiteFlow[]) => {
      setSite((current) => current && { ...current, flows });
      await plant.replaceSiteFlows(flows).catch((err) => setError((err as Error).message));
      await load();
    },
    [load],
  );

  async function createHall(event: React.FormEvent) {
    event.preventDefault();
    if (!newHall.name.trim()) return;
    try {
      const hall = await plant.createHall(newHall.name.trim(), "", newHall.kind);
      setNewHall({ ...newHall, name: "" });
      await load();
      setSelectedId(hall.id);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function changeKind(id: string, kind: HallKind) {
    await plant.updateHall(id, { kind }).catch((err) => setError((err as Error).message));
    await load();
  }

  const selected = site?.halls.find((h) => h.id === selectedId);
  const machines = site?.halls.reduce((sum, h) => sum + h.machine_count, 0) ?? 0;

  return (
    <AppShell breadcrumb={[{ label: "Werk" }]}>
      <div className="flex h-full flex-col">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-border px-4 py-2">
          <h1 className="font-mono text-lg font-semibold uppercase tracking-[0.04em]">Standortplan</h1>
          {site && (
            <span className="text-sm text-muted-foreground">
              {site.halls.length} Hallen ·{" "}
              <Link href="/werk/maschinen" className="text-primary hover:underline">
                {machines} Maschinen
              </Link>
            </span>
          )}
          <form onSubmit={createHall} className="flex w-full flex-wrap gap-1.5 sm:ml-auto sm:w-auto sm:flex-nowrap">
            <input
              value={newHall.name}
              onChange={(event) => setNewHall({ ...newHall, name: event.target.value })}
              placeholder="Neue Halle, z. B. Halle 3"
              aria-label="Name der neuen Halle"
              className="h-8 min-w-0 basis-full border border-border bg-background px-2 text-sm sm:w-48 sm:basis-auto"
            />
            <select
              value={newHall.kind}
              onChange={(event) => setNewHall({ ...newHall, kind: event.target.value as HallKind })}
              aria-label="Art der neuen Halle"
              className="h-8 min-w-0 flex-1 border border-border bg-background px-1.5 text-sm sm:flex-none"
            >
              {KINDS.map((kind) => (
                <option key={kind} value={kind}>
                  {HALL_KIND_LABELS[kind]}
                </option>
              ))}
            </select>
            <button className="h-8 shrink-0 border border-line bg-card px-3 text-sm font-medium hover:border-primary hover:text-primary">
              + Halle anlegen
            </button>
          </form>
        </div>
        {error && <p className="border-b border-border px-4 py-1.5 text-xs text-danger">{error}</p>}

        <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
          <div className="min-h-[420px] min-w-0 flex-1">
            {site && <SiteCanvas site={site} selectedId={selectedId} onSelect={setSelectedId} onRect={saveRect} onFlowsChanged={saveFlows} />}
          </div>

          <aside className="max-h-[45%] shrink-0 overflow-y-auto border-t border-border bg-card p-4 text-sm lg:max-h-none lg:w-80 lg:border-l lg:border-t-0">
            {selected ? (
              <div className="space-y-3">
                <div>
                  <div className="font-mono text-[11px] uppercase tracking-[0.06em] text-muted-foreground">Halle</div>
                  <h2 className="font-mono text-base font-semibold uppercase">{selected.name}</h2>
                </div>
                <select
                  aria-label="Art der Halle"
                  value={selected.kind}
                  onChange={(event) => changeKind(selected.id, event.target.value as HallKind)}
                  className="h-8 w-full border border-border bg-background px-2"
                >
                  {KINDS.map((kind) => (
                    <option key={kind} value={kind}>
                      {HALL_KIND_LABELS[kind]}
                    </option>
                  ))}
                </select>
                <dl className="grid grid-cols-3 gap-2 font-mono">
                  <div>
                    <dd className="text-base font-semibold">{selected.machine_count}</dd>
                    <dt className="text-[11px] text-muted-foreground">Maschinen</dt>
                  </div>
                  <div>
                    <dd className="text-base font-semibold">{selected.lines.length}</dd>
                    <dt className="text-[11px] text-muted-foreground">Linien</dt>
                  </div>
                  <div>
                    <dd className={cn("text-base font-semibold", selected.open_diagnoses > 0 && "text-danger")}>{selected.open_diagnoses}</dd>
                    <dt className="text-[11px] text-muted-foreground">Fehlersuchen</dt>
                  </div>
                </dl>
                {selected.lines.length > 0 && (
                  <ul className="space-y-0.5 border-t border-border pt-2">
                    {selected.lines.map((line) => (
                      <li key={line}>{line}</li>
                    ))}
                  </ul>
                )}
                {selected.description && <p className="border-t border-border pt-2 text-[13px] text-muted-foreground">{selected.description}</p>}
                <Link
                  href={`/werk/halle/${selected.id}`}
                  className="block bg-primary py-2 text-center font-medium text-primary-foreground hover:bg-primary/90"
                >
                  Halle öffnen →
                </Link>
                <p className="text-[11px] leading-snug text-muted-foreground">
                  Ziehen: verschieben · Ecke: Größe · rechter Griff → Halle: Materialfluss · Pfeil anklicken: löschen
                </p>
              </div>
            ) : (
              <div>
                <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Hallen</h2>
                <ul className="mt-2 divide-y divide-border border-y border-border">
                  {site?.halls.map((hall) => (
                    <li key={hall.id}>
                      <button onClick={() => setSelectedId(hall.id)} className="flex w-full items-center gap-2 py-2 text-left hover:text-primary">
                        <span className="min-w-0 flex-1 truncate">{hall.name}</span>
                        <span className="font-mono text-[11px] text-muted-foreground">{HALL_KIND_LABELS[hall.kind]}</span>
                        <span className="w-6 text-right font-mono text-xs">{hall.machine_count}</span>
                      </button>
                    </li>
                  ))}
                </ul>
                <p className="mt-3 text-[11px] leading-snug text-muted-foreground">
                  Halle im Plan anklicken für Details. Testwerk laden: <code>python scripts/load_testwerk.py</code>
                </p>
              </div>
            )}
          </aside>
        </div>
      </div>
    </AppShell>
  );
}
