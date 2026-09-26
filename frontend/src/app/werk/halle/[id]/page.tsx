"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { HallCanvas } from "@/components/HallCanvas";
import { OnboardingDialog } from "@/components/onboarding/OnboardingDialog";
import {
  api,
  HALL_KIND_LABELS,
  MACHINE_TYPE_LABELS,
  plant,
  type Flow,
  type HallDetail,
  type HallKind,
  type KnowledgeSource,
  type Machine,
  type MachineType,
} from "@/lib/api";

const TYPES = Object.keys(MACHINE_TYPE_LABELS) as MachineType[];
const KINDS = Object.keys(HALL_KIND_LABELS) as HallKind[];
const FIELD = "mt-0.5 w-full border border-border bg-background px-2 py-1.5";

/** Hallen-Baukasten: Maschinen als Kacheln, Linienbaender, Materialfluss, Auswahlpanel. */
export default function HallPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [hall, setHall] = useState<HallDetail | null>(null);
  const [missing, setMissing] = useState(false);
  const [sources, setSources] = useState<KnowledgeSource[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [newMachine, setNewMachine] = useState({ name: "", machine_type: "main" as MachineType });
  const [error, setError] = useState<string | null>(null);

  const loadHall = useCallback(
    () =>
      plant
        .getHall(id)
        .then((detail) => {
          setHall(detail);
          setMissing(false);
        })
        .catch(() => setMissing(true)),
    [id],
  );

  useEffect(() => {
    loadHall();
    api.listSources().then(setSources).catch(() => {});
  }, [loadHall]);

  async function updateHall(body: Parameters<typeof plant.updateHall>[1]) {
    await plant.updateHall(id, body).catch((err) => setError(err.message));
    await loadHall();
  }

  async function deleteHall() {
    if (!hall || !confirm(`Halle „${hall.name}“ mit ${hall.machines.length} Maschine(n) löschen?`)) return;
    try {
      await plant.deleteHall(hall.id);
      router.push("/werk");
    } catch (err) {
      setError((err as Error).message);
    }
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
      await loadHall();
      setSelectedId(machine.id);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function updateSelected(body: Parameters<typeof plant.updateMachine>[1]) {
    if (!selectedId) return;
    await plant.updateMachine(selectedId, body).catch((err) => setError(err.message));
    await loadHall();
  }

  async function deleteSelected() {
    const machine = hall?.machines.find((m) => m.id === selectedId);
    if (!machine || !confirm(`Maschine „${machine.name}“ löschen?`)) return;
    await plant.deleteMachine(machine.id).catch((err) => setError(err.message));
    setSelectedId(null);
    await loadHall();
  }

  // Position sofort in den Seitenzustand, sonst setzt der naechste Neuaufbau (z. B. Auswahl) die Kachel zurueck
  const moveMachine = useCallback((machineId: string, x: number, y: number) => {
    setHall((current) => current && { ...current, machines: current.machines.map((m) => (m.id === machineId ? { ...m, pos_x: x, pos_y: y } : m)) });
    plant.updateMachine(machineId, { pos_x: x, pos_y: y }).catch((err) => setError(err.message));
  }, []);

  async function saveFlows(flows: Flow[]) {
    if (!hall) return;
    setHall({ ...hall, flows });
    await plant.replaceFlows(hall.id, flows).catch((err) => setError(err.message));
    await loadHall();
  }

  const selected: Machine | undefined = hall?.machines.find((m) => m.id === selectedId);
  const lines = [...new Set(hall?.machines.map((m) => m.line).filter(Boolean))];

  if (missing) {
    return (
      <AppShell breadcrumb={[{ label: "Werk", href: "/werk" }, { label: "Halle" }]}>
        <p className="p-8 text-sm text-muted-foreground">
          Diese Halle gibt es nicht mehr.{" "}
          <Link href="/werk" className="text-primary hover:underline">
            Zum Standortplan
          </Link>
        </p>
      </AppShell>
    );
  }

  return (
    <AppShell breadcrumb={[{ label: "Werk", href: "/werk" }, { label: hall?.name ?? "…" }]}>
      {hall && (
        <div className="flex h-full flex-col">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 border-b border-border px-4 py-2">
            <h1 className="truncate font-mono text-lg font-semibold uppercase">{hall.name}</h1>
            <select
              aria-label="Art der Halle"
              value={hall.kind}
              onChange={(event) => updateHall({ kind: event.target.value as HallKind })}
              className="h-7 border border-border bg-background px-1.5 text-sm"
            >
              {KINDS.map((kind) => (
                <option key={kind} value={kind}>
                  {HALL_KIND_LABELS[kind]}
                </option>
              ))}
            </select>
            <span className="text-sm text-muted-foreground">
              {hall.machines.length} Maschinen{lines.length > 0 && ` · ${lines.length} Linien`}
            </span>
            <span className="ml-auto">
              <OnboardingDialog hallId={hall.id} onCreated={loadHall} />
            </span>
            <button onClick={deleteHall} className="text-sm text-muted-foreground hover:text-danger">
              Halle löschen
            </button>
            {hall.description && <p className="w-full text-[13px] text-muted-foreground">{hall.description}</p>}
          </div>

          <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
            <div className="min-h-[420px] min-w-0 flex-1">
              <HallCanvas
                machines={hall.machines}
                flows={hall.flows}
                selectedId={selectedId}
                onSelect={setSelectedId}
                onMoved={moveMachine}
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
                  className="w-full border border-border bg-background px-2 py-1.5 text-sm"
                />
                <div className="flex gap-1.5">
                  <select
                    value={newMachine.machine_type}
                    onChange={(event) => setNewMachine({ ...newMachine, machine_type: event.target.value as MachineType })}
                    className="min-w-0 flex-1 border border-border bg-background px-2 py-1.5 text-sm"
                  >
                    {TYPES.map((type) => (
                      <option key={type} value={type}>
                        {MACHINE_TYPE_LABELS[type]}
                      </option>
                    ))}
                  </select>
                  <button className="bg-primary px-3 text-sm font-medium text-primary-foreground">Anlegen</button>
                </div>
              </form>
              {error && <p className="pt-2 text-xs text-danger">{error}</p>}

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
                      className={FIELD}
                    />
                  </label>
                  <label className="block text-sm">
                    <span className="text-xs text-muted-foreground">Typ</span>
                    <select value={selected.machine_type} onChange={(event) => updateSelected({ machine_type: event.target.value as MachineType })} className={FIELD}>
                      {TYPES.map((type) => (
                        <option key={type} value={type}>
                          {MACHINE_TYPE_LABELS[type]}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="block text-sm">
                    <span className="text-xs text-muted-foreground">Linie/Sektor</span>
                    <input
                      key={selected.id + selected.line}
                      defaultValue={selected.line}
                      list="hall-lines"
                      placeholder="z. B. L1 Toilettenpapier"
                      onBlur={(event) => event.target.value.trim() !== selected.line && updateSelected({ line: event.target.value.trim() })}
                      className={FIELD}
                    />
                    <datalist id="hall-lines">
                      {lines.map((line) => (
                        <option key={line} value={line} />
                      ))}
                    </datalist>
                  </label>
                  <label className="block text-sm">
                    <span className="text-xs text-muted-foreground">Wissensquelle (Doku)</span>
                    <select
                      value={selected.source_id ?? ""}
                      onChange={(event) =>
                        event.target.value ? updateSelected({ source_id: event.target.value }) : updateSelected({ clear_source: true })
                      }
                      className={FIELD}
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
        </div>
      )}
    </AppShell>
  );
}
