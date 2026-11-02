"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { OnboardingDialog } from "@/components/onboarding/OnboardingDialog";
import { MACHINE_TYPE_LABELS, plant, type MachineListItem } from "@/lib/api";
import { docsLabel, filterMachines, summarizeMachines } from "@/lib/machines";
import { cn } from "@/lib/utils";
import { plural } from "@/lib/format";

const TH = "px-3 py-2 text-left font-mono text-[11px] font-semibold uppercase tracking-[0.06em] text-muted-foreground";
const TD = "px-3 py-2 align-top";

/** Maschinenübersicht: jede Maschine mit Doku-Stand und Fehlerliste, Filter über alles; hier
 * entsteht auch eine neue Maschine aus ihrer Dokumentation. */
export default function MachinesPage() {
  const [machines, setMachines] = useState<MachineListItem[] | null>(null);
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    plant
      .listMachines()
      .then(setMachines)
      .catch((err) => setError((err as Error).message));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const shown = useMemo(() => filterMachines(machines ?? [], query), [machines, query]);
  const summary = useMemo(() => summarizeMachines(machines ?? []), [machines]);

  return (
    <AppShell breadcrumb={[{ label: "Maschinen" }]}>
      <div className="flex h-full flex-col">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-border px-4 py-2">
          <h1 className="text-page-title">Maschinen</h1>
          {machines && (
            <span className="text-sm text-muted-foreground">
              {plural(summary.total, "Maschine", "Maschinen")} · {summary.withoutDocs} ohne Doku · {plural(summary.faults, "Fehlereintrag", "Fehlereinträge")}
            </span>
          )}
          <div className="flex w-full flex-wrap items-center gap-2 sm:ml-auto sm:w-auto">
            <OnboardingDialog onCreated={load} />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Filter: Name, Linie, Halle, Typ …"
              aria-label="Maschinen filtern"
              className="h-8 min-w-0 flex-1 border border-border bg-background px-2 text-sm sm:w-72 sm:flex-none"
            />
          </div>
        </div>
        {error && <p className="border-b border-border px-4 py-1.5 text-xs text-danger">{error}</p>}

        <div className="min-h-0 flex-1 overflow-auto">
          {machines && machines.length === 0 && (
            <p className="p-6 text-sm text-muted-foreground">
              Noch keine Maschinen. Lege eine Maschine aus ihrer Dokumentation an („Aus Dokumentation anlegen“) oder lade das
              Testwerk: <code className="font-mono">python scripts/load_testwerk.py</code>
            </p>
          )}
          {machines && machines.length > 0 && (
            <ul className="space-y-3 p-4 md:hidden" data-testid="machine-cards">
              {shown.map((m) => (
                <li key={m.id} className="rounded-lg bg-card p-4 shadow-card">
                  <Link href={`/werk/maschine/${m.id}`} className="block min-h-11 text-headline text-primary">
                    {m.name}
                  </Link>
                  <p className="text-footnote text-muted-foreground">
                    {[MACHINE_TYPE_LABELS[m.machine_type] ?? m.machine_type, m.line, m.hall_name].filter(Boolean).join(" · ")}
                  </p>
                  <dl className="mt-3 grid grid-cols-3 gap-x-3 text-footnote">
                    <div>
                      <dt className="text-caption-1 text-muted-foreground">Dokumentation</dt>
                      <dd className={m.ready_document_count === 0 ? "text-muted-foreground" : undefined}>{docsLabel(m)}</dd>
                    </div>
                    <div>
                      <dt className="text-caption-1 text-muted-foreground">Fehler</dt>
                      <dd className="tabular-nums">{m.fault_count}</dd>
                    </div>
                    <div>
                      <dt className="text-caption-1 text-muted-foreground">Kennzahl</dt>
                      <dd className="font-mono break-words">{m.key_figure || "–"}</dd>
                    </div>
                  </dl>
                </li>
              ))}
              {shown.length === 0 && <li className="p-6 text-center text-muted-foreground">Keine Maschine passt zu „{query}“.</li>}
            </ul>
          )}
          {machines && machines.length > 0 && (
            <table className="hidden w-full min-w-[760px] border-collapse text-sm md:table">
              <thead className="sticky top-0 bg-card">
                <tr className="border-b border-line">
                  <th className={TH}>Maschine</th>
                  <th className={TH}>Typ</th>
                  <th className={TH}>Linie</th>
                  <th className={TH}>Halle</th>
                  <th className={TH}>Dokumentation</th>
                  <th className={cn(TH, "text-right")}>Fehler</th>
                  <th className={TH}>Kennzahl</th>
                </tr>
              </thead>
              <tbody>
                {shown.map((m) => (
                  <tr key={m.id} className="border-b border-border hover:bg-secondary">
                    <td className={TD}>
                      <Link href={`/werk/maschine/${m.id}`} className="font-medium text-primary hover:underline">
                        {m.name}
                      </Link>
                      <span className="ml-2 font-mono text-[11px] text-muted-foreground">
                        {m.cabinet_count > 0 ? `${m.cabinet_count} Schrank` : ""}
                      </span>
                    </td>
                    <td className={TD}>{MACHINE_TYPE_LABELS[m.machine_type] ?? m.machine_type}</td>
                    <td className={TD}>{m.line || <span className="text-muted-foreground">–</span>}</td>
                    <td className={TD}>{m.hall_name}</td>
                    <td className={cn(TD, m.ready_document_count === 0 && "text-muted-foreground")}>
                      {m.source_id && m.ready_document_count > 0 ? (
                        <Link href={`/quelle/${m.source_id}`} className="hover:text-primary hover:underline">
                          {docsLabel(m)}
                        </Link>
                      ) : (
                        docsLabel(m)
                      )}
                      {m.source_name && <span className="ml-1 text-xs text-muted-foreground">({m.source_name})</span>}
                    </td>
                    <td className={cn(TD, "text-right tabular-nums")}>{m.fault_count}</td>
                    <td className={cn(TD, "font-mono text-[13px]")}>{m.key_figure}</td>
                  </tr>
                ))}
                {shown.length === 0 && (
                  <tr>
                    <td colSpan={7} className="p-6 text-center text-muted-foreground">
                      Keine Maschine passt zu „{query}“.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </AppShell>
  );
}
