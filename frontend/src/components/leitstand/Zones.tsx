"use client";

import type { SimResult } from "@/lib/api";
import { num } from "@/lib/format";
import type { LeitstandState, ResourceState } from "@/lib/leitstand";
import { cn } from "@/lib/utils";

const TITLE = "mb-2 font-mono text-[11px] font-semibold uppercase tracking-[0.06em] text-muted-foreground";
const ZONE = "border-b border-border p-4 lg:border-r last:border-b-0";

function Zone({ title, children, className }: { title: string; children: React.ReactNode; className?: string }) {
  return (
    <section className={cn(ZONE, className)}>
      <h2 className={TITLE}>{title}</h2>
      {children}
    </section>
  );
}

function Slot({ busy }: { busy: boolean }) {
  return <span className={cn("inline-block size-2.5 border border-primary", busy && "bg-primary")} aria-hidden />;
}

/** Buero: je Station Personen (belegt/frei), laufende Auftraege, Warteschlange, Kreditklaerung. */
export function OfficeZone({ state, closed }: { state: LeitstandState; closed: boolean }) {
  const stations = Object.values(state.resources).filter((r) => r.kind === "office");
  return (
    <Zone title={closed ? "Büro · geschlossen" : "Büro"}>
      <div className="grid grid-cols-[minmax(0,1fr)_auto_minmax(0,2fr)] items-center gap-x-3 gap-y-1.5 text-[13px]">
        {stations.map((r) => (
          <Row key={r.key} resource={r} closed={closed} />
        ))}
      </div>
    </Zone>
  );
}

function Row({ resource, closed }: { resource: ResourceState; closed: boolean }) {
  const slots = Array.from({ length: resource.capacity }, (_, i) => resource.busy.some((b) => b.slot === i));
  const parts = [
    ...resource.busy.map((b) => b.order),
    ...(resource.hold.length ? [`Klärung ${resource.hold.join(", ")}`] : []),
  ];
  return (
    <>
      <span className="truncate">{resource.label}</span>
      <span className="flex gap-0.5">
        {slots.map((busy, i) => (
          <Slot key={i} busy={busy} />
        ))}
      </span>
      <span className="truncate font-mono text-[12px]">
        {parts.length ? parts.join(" · ") : <span className={cn("text-muted-foreground", closed && "italic")}>{closed ? "Feierabend" : "frei"}</span>}
        {resource.queue.length > 0 && <span className="text-muted-foreground"> · wartet {resource.queue.length}</span>}
      </span>
    </>
  );
}

/** Fertigung: PM1 und Linien mit laufendem Auftrag als Fortschrittsbalken und Warteschlange. */
export function ProductionZone({ state }: { state: LeitstandState }) {
  const machines = Object.values(state.resources).filter((r) => r.kind === "paper" || r.kind === "line");
  return (
    <Zone title="Fertigung">
      <div className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-x-2 gap-y-1.5 font-mono text-[12px]">
        {machines.map((r) => {
          const current = r.busy[0];
          return (
            <div key={r.key} className="contents">
              <span className="truncate">{r.kind === "paper" ? "PM1" : r.label.split(" ")[0]}</span>
              <span className="relative h-4 border border-border bg-secondary">
                {current && (
                  <>
                    <span className="absolute inset-y-0 left-0 bg-primary" style={{ width: `${Math.round(current.progress * 100)}%` }} />
                    <span className={cn("absolute inset-y-0 left-1 leading-4", current.progress > 0.3 ? "text-primary-foreground" : "text-foreground")}>
                      {current.order}
                    </span>
                  </>
                )}
                {!current && <span className="absolute inset-y-0 left-1 leading-4 text-muted-foreground">frei</span>}
              </span>
              <span className="w-6 text-muted-foreground">{r.queue.length > 0 ? `+${r.queue.length}` : ""}</span>
            </div>
          );
        })}
      </div>
    </Zone>
  );
}

/** Lager: Bestand je Artikel in Paletten und was heute verladen wird. */
export function StockZone({ state }: { state: LeitstandState }) {
  const max = Math.max(1, ...state.stock.map((s) => s.pallets));
  return (
    <Zone title="Lager · Paletten">
      <div className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-x-2 gap-y-1 font-mono text-[12px]">
        {state.stock.map((s) => (
          <div key={s.code} className="contents">
            <span title={s.name}>{s.code.split("-").slice(0, 2).join("-")}</span>
            <span className="h-2 bg-secondary">
              <span className="block h-2 bg-nav" style={{ width: `${Math.max(1, (s.pallets / max) * 100)}%` }} />
            </span>
            <span className="w-8 text-right">{num(s.pallets)}</span>
          </div>
        ))}
        {state.stock.length === 0 && <span className="col-span-3 text-muted-foreground">kein Bestand</span>}
      </div>
      <p className="mt-2 border-t border-border pt-2 text-[12px]">
        <span className="font-mono text-[11px] text-muted-foreground">HEUTE RAUS </span>
        {state.todayOut.length ? state.todayOut.map((o) => `${o.order} (${o.trucks} LKW)`).join(", ") : "nichts"}
      </p>
    </Zone>
  );
}

/** Versand: Tore mit LKW und Fortschritt, wartende LKW. */
export function ShippingZone({ state, closed }: { state: LeitstandState; closed: boolean }) {
  return (
    <Zone title={`Versand · ${state.docks.length} Tore${closed ? " · geschlossen" : ""}`} className="lg:border-r-0">
      <div className="grid grid-cols-4 gap-1.5 font-mono text-[11px]">
        {state.docks.map((dock, i) => (
          <div key={i} className={cn("border px-1.5 py-1", dock ? "border-line bg-card" : "border-border text-muted-foreground")}>
            T{i + 1}
            <div className="truncate">{dock ? dock.order : "frei"}</div>
            {dock && (
              <div className="mt-0.5 h-[3px] bg-secondary">
                <div className="h-[3px] bg-primary" style={{ width: `${Math.round(dock.progress * 100)}%` }} />
              </div>
            )}
          </div>
        ))}
      </div>
      <p className="mt-2 text-[12px] text-muted-foreground">
        {state.waitingTrucks ? `wartend: ${state.waitingTrucks} LKW` : "wartend: kein LKW"}
      </p>
    </Zone>
  );
}

/** Kennzahlen des ganzen Laufs. */
export function Kpis({ result }: { result: SimResult }) {
  const k = result.kpis;
  const lines = Object.entries(k.utilization).filter(([key]) => key.startsWith("line:"));
  const busiest = lines.sort((a, b) => b[1] - a[1])[0];
  const finance = k.avg_wait_hours["office:fin"] ?? 0;
  const items: [string, string][] = [
    [k.on_time_rate === null ? "–" : `${Math.round(k.on_time_rate * 100)} %`, "Termintreue"],
    [k.avg_lead_hours === null ? "–" : `${num(k.avg_lead_hours / 24, 1)} Tage`, "Ø Durchlauf"],
    [busiest ? `${Math.round(busiest[1] * 100)} %` : "–", `Auslastung ${busiest ? busiest[0].replace("line:", "").split(" ")[0] : "Linie"}`],
    [`${num(finance, 1)} h`, "Ø Warten Finanzen"],
  ];
  return (
    <dl className="grid grid-cols-2 gap-3 border-t border-line bg-card px-4 py-2.5 font-mono sm:grid-cols-4">
      {items.map(([value, label]) => (
        <div key={label}>
          <dd className="text-base font-semibold">{value}</dd>
          <dt className="text-[11px] text-muted-foreground">{label}</dt>
        </div>
      ))}
    </dl>
  );
}
