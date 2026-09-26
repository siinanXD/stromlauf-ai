"use client";

import type { SimOrderResult } from "@/lib/api";
import { num, whenText } from "@/lib/format";
import type { LeitstandState } from "@/lib/leitstand";
import { cn } from "@/lib/utils";

function DueBadge({ order }: { order: SimOrderResult }) {
  if (order.on_time === null) return <span className="text-muted-foreground">offen</span>;
  if (order.on_time) return <span className="text-ok">hält</span>;
  return <span className="font-semibold">+{-(order.days_delta ?? 0)} {order.days_delta === -1 ? "Tag" : "Tage"}</span>;
}

/** Auftragsbuch: alle Auftraege mit aktueller Station, Paletten und Termin; Klick waehlt einen Auftrag. */
export function OrderBook({
  orders,
  state,
  selected,
  onSelect,
}: {
  orders: SimOrderResult[];
  state: LeitstandState;
  selected: string | null;
  onSelect: (number: string | null) => void;
}) {
  return (
    <div>
      <h2 className="mb-2 font-mono text-[11px] font-semibold uppercase tracking-[0.06em] text-muted-foreground">Auftragsbuch · {orders.length}</h2>
      <ul className="divide-y divide-border">
        {orders.map((order) => {
          const status = state.orders[order.number];
          const future = status.status === "noch nicht eingegangen";
          return (
            <li key={order.number}>
              <button
                type="button"
                onClick={() => onSelect(selected === order.number ? null : order.number)}
                className={cn(
                  "w-full py-1.5 pr-1 text-left text-[12px] hover:bg-secondary",
                  selected === order.number ? "border-l-[3px] border-primary bg-secondary pl-1.5" : "pl-2.5",
                  future && "opacity-50",
                )}
              >
                <div className="flex items-baseline gap-1.5">
                  <span className="font-mono font-semibold">{order.number}</span>
                  <span className="min-w-0 flex-1 truncate">{order.customer}</span>
                </div>
                <div className="flex justify-between gap-2 text-muted-foreground">
                  <span className="truncate">
                    {status.status} · {num(order.pallets)} Pal
                  </span>
                  <DueBadge order={order} />
                </div>
              </button>
            </li>
          );
        })}
      </ul>
      {orders.length === 0 && <p className="text-[13px] text-muted-foreground">Keine Aufträge. In der Planung „Als Auftrag anlegen“ oder Testwerk laden.</p>}
    </div>
  );
}

/** Weg eines Auftrags: Warten hell, Arbeiten blau, mit Zeiten. */
export function OrderPath({ order, time }: { order: SimOrderResult; time: number }) {
  const start = new Date(order.received_at).getTime();
  const end = new Date(order.shipped_at ?? order.stages[order.stages.length - 1]?.end ?? order.received_at).getTime();
  const span = Math.max(1, end - start);
  const x = (iso: string) => `${((new Date(iso).getTime() - start) / span) * 100}%`;
  const w = (a: string, b: string) => `${Math.max(0, (new Date(b).getTime() - new Date(a).getTime()) / span) * 100}%`;
  const now = Math.min(100, Math.max(0, ((time - start) / span) * 100));
  return (
    <div className="space-y-1.5 border-t border-border pt-3">
      <div className="flex items-baseline justify-between font-mono text-[11px] text-muted-foreground">
        <span className="font-semibold uppercase tracking-[0.06em]">{order.number} · Weg</span>
        <span>
          {whenText(order.received_at)} → {order.shipped_at ? whenText(order.shipped_at) : "offen"}
        </span>
      </div>
      <div className="relative h-3 bg-secondary">
        {order.stages.map((s) => (
          <span key={s.stage} className="absolute inset-y-0" style={{ left: x(s.arrive), width: w(s.arrive, s.start) }}>
            <span className="block h-full bg-[#cdd5df]" title={`wartet ${s.label}`} />
          </span>
        ))}
        {order.stages.map((s) => (
          <span
            key={`${s.stage}-w`}
            title={`${s.label}: ${whenText(s.start)} – ${whenText(s.end)}`}
            className={cn("absolute inset-y-0", s.stage === "credit" ? "border border-primary bg-card" : "bg-primary")}
            style={{ left: x(s.start), width: w(s.start, s.end) }}
          />
        ))}
        <span className="absolute inset-y-[-3px] w-px bg-foreground" style={{ left: `${now}%` }} />
      </div>
      <ol className="space-y-0.5 text-[11px] text-muted-foreground">
        {order.stages.map((s) => (
          <li key={s.stage} className="flex justify-between gap-2">
            <span className="truncate">{s.label}</span>
            <span className="shrink-0 font-mono">
              {whenText(s.start).slice(3)} – {whenText(s.end).slice(3)}
            </span>
          </li>
        ))}
      </ol>
      <p className="text-[11px] text-muted-foreground">
        {order.positions.map((p) => `${p.code}: ${num(p.from_stock)} aus Lager, ${num(p.produced)} gefertigt`).join(" · ")}
      </p>
    </div>
  );
}
