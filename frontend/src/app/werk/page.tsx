"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { HallCanvas } from "@/components/HallCanvas";
import { OnboardingDialog } from "@/components/onboarding/OnboardingDialog";
import {
  api,
  MACHINE_TYPE_LABELS,
  plant,
  type Flow,
  type Hall,
  type HallDetail,
  type KnowledgeSource,
  type Machine,
  type MachineType,
} from "@/lib/api";

const TYPES = Object.keys(MACHINE_TYPE_LABELS) as MachineType[];

export default function WerkPage() {
  const [halls, setHalls] = useState<Hall[]>([]);
  const [hallId, setHallId] = useState<string | null>(null);
  const [hall, setHall] = useState<HallDetail | null>(null);
  const [sources, setSources] = useState<KnowledgeSource[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [newHall, setNewHall] = useState("");
  const [newMachine, setNewMachine] = useState({ name: "", machine_type: "main" as MachineType });
  const [error, setError] = useState<string | null>(null);

  const loadHalls = useCallback(
    () =>
      plant
        .listHalls()
        .then((list) => {
          setHalls(list);
          setHallId((current) => current ?? list[0]?.id ?? null);
        })
        .catch((err) => setError((err as Error).message)),
    [],
  );

  const loadHall = useCallback(
    (id: string) =>
      plant
        .getHall(id)
        .then(setHall)
        .catch(() => setHall(null)),
    [],
  );

  useEffect(() => {
    loadHalls();
    api.listSources().then(setSources).catch(() => {});
  }, [loadHalls]);

  useEffect(() => {
    if (hallId) loadHall(hallId);
  }, [hallId, loadHall]);

  async function createHall(event: React.FormEvent) {
    event.preventDefault();
    if (!newHall.trim()) return;
    try {
      const created = await plant.createHall(newHall.trim());
      setNewHall("");
      await loadHalls();
      setHallId(created.id);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function deleteHall() {
    if (!hall || !confirm(`Halle „${hall.name}“ mit ${hall.machines.length} Maschine(n) löschen?`)) return;
    await plant.deleteHall(hall.id).catch((err) => setError(err.message));
    setHallId(null);
    await loadHalls();
  }

  async function createMachine(event: React.FormEvent) {
    event.preventDefault();
    if (!hall || !newMachine.name.trim()) return;
    const index = hall.machines.length;
    try {
      const machine = await plant.createMachine(hall.id, {
        name: newMachine.name.trim(),
        machine_type: newMachine.machine_type,
        pos_x: 48 + (index % 4) * 216,
        pos_y: 48 + Math.floor(index / 4) * 144,
      });
      setNewMachine({ name: "", machine_type: newMachine.machine_type });
      await loadHall(hall.id);
      setSelectedId(machine.id);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function updateSelected(body: Parameters<typeof plant.updateMachine>[1]) {
    if (!hall || !selectedId) return;
    await plant.updateMachine(selectedId, body).catch((err) => setError(err.message));
    await loadHall(hall.id);
  }

  async function deleteSelected() {
    const machine = hall?.machines.find((m) => m.id === selectedId);
    if (!hall || !machine || !confirm(`Maschine „${machine.name}“ löschen?`)) return;
    await plant.deleteMachine(machine.id).catch((err) => setError(err.message));
    setSelectedId(null);
    await loadHall(hall.id);
  }

  async function saveFlows(flows: Flow[]) {
    if (!hall) return;
    setHall({ ...hall, flows });
    await plant.replaceFlows(hall.id, flows).catch((err) => setError(err.message));
    await loadHall(hall.id);
  }

  const current = hall && hall.id === hallId ? hall : null;
  const selected: Machine | undefined = current?.machines.find((m) => m.id === selectedId);

  return (
    <AppShell breadcrumb={current ? [{ label: "Werk", href: "/werk" }, { label: current.name }] : [{ label: "Werk" }]}>
      <div className="flex h-full flex-col">

        <div className="flex min-h-0 flex-1">
          <aside className="hidden w-64 shrink-0 border-r border-border bg-card md:block">
            <div className="flex items-center justify-between px-4 pb-1.5 pt-4">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Hallen</h2>
            </div>
            <ul>
              {halls.map((h) => (
                <li key={h.id}>
                  <button
                    onClick={() => {
                      setHallId(h.id);
                      setSelectedId(null);
                    }}
                    className={`flex w-full items-center gap-2 px-4 py-1.5 text-left text-sm hover:bg-secondary ${h.id === hallId ? "bg-secondary font-medium" : ""}`}
                  >
                    <span className="truncate">{h.name}</span>
                    <span className="ml-auto text-xs text-muted-foreground">{h.machine_count}</span>
                  </button>
                </li>
              ))}
            </ul>
            <form onSubmit={createHall} className="flex gap-1.5 px-3 pt-2">
              <input
                value={newHall}
                onChange={(event) => setNewHall(event.target.value)}
                placeholder="Neue Halle, z. B. Halle 3"
                className="min-w-0 flex-1 rounded-md border border-border bg-background px-2 py-1.5 text-sm"
              />
              <button className="rounded-md bg-primary px-2.5 text-sm font-medium text-primary-foreground">+</button>
            </form>
            {error && <p className="px-4 pt-2 text-xs text-danger">{error}</p>}
          </aside>

          <main className="flex min-w-0 flex-1 flex-col">
            {!current ? (
              <div className="p-8 text-muted-foreground">
                <h1 className="text-xl font-semibold text-foreground">Werk</h1>
                <p className="mt-2 max-w-md text-sm">
                  Lege links eine Halle an. Darin ordnest du Maschinen als Kacheln an, zeichnest den Materialfluss und
                  hängst an jede Maschine ihre Doku, Fehlerliste und Schaltschrankbilder.
                </p>
              </div>
            ) : (
              <>
                <div className="flex items-center gap-3 border-b border-border px-4 py-2">
                  <h1 className="truncate font-mono text-lg font-semibold uppercase">{current.name}</h1>
                  <span className="text-sm text-muted-foreground">{current.machines.length} Maschinen</span>
                  <span className="ml-auto">
                    <OnboardingDialog hallId={current.id} onCreated={() => loadHall(current.id)} />
                  </span>
                  <button onClick={deleteHall} className="text-sm text-muted-foreground hover:text-danger">
                    Halle löschen
                  </button>
                </div>
                <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
                  <div className="min-h-[420px] min-w-0 flex-1">
                    <HallCanvas
                      machines={current.machines}
                      flows={current.flows}
                      selectedId={selectedId}
                      onSelect={setSelectedId}
                      onMoved={(id, x, y) => plant.updateMachine(id, { pos_x: x, pos_y: y }).catch((err) => setError(err.message))}
                      onFlowsChanged={saveFlows}
                    />
                  </div>

                  <aside className="max-h-[45%] shrink-0 overflow-y-auto border-t border-border bg-card p-4 lg:max-h-none lg:w-80 lg:border-l lg:border-t-0">
                    <form onSubmit={createMachine} className="space-y-2">
                      <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Maschine anlegen</h2>
                      <input
                        value={newMachine.name}
                        onChange={(event) => setNewMachine({ ...newMachine, name: event.target.value })}
                        placeholder="Name, z. B. Förderband FB-01"
                        className="w-full rounded-md border border-border bg-background px-2 py-1.5 text-sm"
                      />
                      <div className="flex gap-1.5">
                        <select
                          value={newMachine.machine_type}
                          onChange={(event) => setNewMachine({ ...newMachine, machine_type: event.target.value as MachineType })}
                          className="min-w-0 flex-1 rounded-md border border-border bg-background px-2 py-1.5 text-sm"
                        >
                          {TYPES.map((type) => (
                            <option key={type} value={type}>
                              {MACHINE_TYPE_LABELS[type]}
                            </option>
                          ))}
                        </select>
                        <button className="rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground">Anlegen</button>
                      </div>
                    </form>

                    {selected && (
                      <div className="mt-6 space-y-3 border-t border-border pt-4">
                        <div className="flex items-center justify-between">
                          <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Ausgewählt</h2>
                          <Link href={`/werk/maschine/${selected.id}`} className="text-sm text-primary hover:underline">
                            Maschinenseite →
                          </Link>
                        </div>
                        <label className="block text-sm">
                          <span className="text-xs text-muted-foreground">Name</span>
                          <input
                            key={selected.id + selected.name}
                            defaultValue={selected.name}
                            onBlur={(event) => event.target.value.trim() && event.target.value !== selected.name && updateSelected({ name: event.target.value.trim() })}
                            className="mt-0.5 w-full rounded-md border border-border bg-background px-2 py-1.5"
                          />
                        </label>
                        <label className="block text-sm">
                          <span className="text-xs text-muted-foreground">Typ</span>
                          <select
                            value={selected.machine_type}
                            onChange={(event) => updateSelected({ machine_type: event.target.value as MachineType })}
                            className="mt-0.5 w-full rounded-md border border-border bg-background px-2 py-1.5"
                          >
                            {TYPES.map((type) => (
                              <option key={type} value={type}>
                                {MACHINE_TYPE_LABELS[type]}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label className="block text-sm">
                          <span className="text-xs text-muted-foreground">Wissensquelle (Doku)</span>
                          <select
                            value={selected.source_id ?? ""}
                            onChange={(event) =>
                              event.target.value ? updateSelected({ source_id: event.target.value }) : updateSelected({ clear_source: true })
                            }
                            className="mt-0.5 w-full rounded-md border border-border bg-background px-2 py-1.5"
                          >
                            <option value="">keine</option>
                            {sources.map((source) => (
                              <option key={source.id} value={source.id}>
                                {source.name} ({source.document_count})
                              </option>
                            ))}
                          </select>
                        </label>
                        <button onClick={deleteSelected} className="text-sm text-muted-foreground hover:text-danger">
                          Maschine löschen
                        </button>
                      </div>
                    )}
                  </aside>
                </div>
              </>
            )}
          </main>
        </div>
      </div>
    </AppShell>
  );
}
