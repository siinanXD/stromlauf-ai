"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { Clock, SPEEDS } from "@/components/leitstand/Clock";
import { OrderBook, OrderPath } from "@/components/leitstand/OrderBook";
import { Kpis, OfficeZone, ProductionZone, ShippingZone, StockZone } from "@/components/leitstand/Zones";
import { leitstand, type SimResult } from "@/lib/api";
import { stateAt } from "@/lib/leitstand";

const ms = (iso: string) => new Date(iso).getTime();

/** Leitstand: Durchlauf aller Auftraege abspielen; Zustand von Buero, Fertigung, Lager und Versand je Uhrzeit. */
export default function LeitstandPage() {
  const [result, setResult] = useState<SimResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [time, setTime] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(SPEEDS[1].value);
  const [selected, setSelected] = useState<string | null>(null);
  const frame = useRef<number>(0);

  useEffect(() => {
    leitstand
      .simulate()
      .then((sim) => {
        setResult(sim);
        if (sim.start) setTime(ms(sim.start));
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  const start = result?.start ? ms(result.start) : 0;
  const end = result?.end ? ms(result.end) : 0;

  // Uhr: Simulationszeit laeuft mit `speed` ms je Sekunde Echtzeit, stoppt am Ende
  useEffect(() => {
    if (!playing) return;
    let last = performance.now();
    const tick = (now: number) => {
      const delta = ((now - last) / 1000) * speed;
      last = now;
      setTime((t) => {
        const next = t + delta;
        if (next >= end) {
          setPlaying(false);
          return end;
        }
        return next;
      });
      frame.current = requestAnimationFrame(tick);
    };
    frame.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame.current);
  }, [playing, speed, end]);

  const state = useMemo(() => (result ? stateAt(result, time) : null), [result, time]);
  const selectedOrder = result?.orders.find((o) => o.number === selected) ?? null;

  return (
    <AppShell breadcrumb={[{ label: "Leitstand" }]}>
      <div className="flex h-full flex-col">
        <div className="flex items-center gap-4 border-b border-border px-4 py-2">
          <h1 className="font-mono text-lg font-semibold uppercase tracking-[0.04em]">Leitstand</h1>
          {result && (
            <span className="text-sm text-muted-foreground">
              {result.orders.length} Aufträge · Simulation, keine Echtzeitdaten
            </span>
          )}
        </div>
        {error && <p className="m-4 border border-danger/40 bg-danger/5 px-3 py-2 text-sm text-danger">{error}</p>}
        {result && result.orders.length === 0 && (
          <p className="m-6 max-w-xl text-sm text-muted-foreground">
            Keine Aufträge im Auftragsbuch. In der Planung „Als Auftrag anlegen“ oder Testwerk laden:{" "}
            <code className="font-mono">python scripts/load_testwerk.py</code>
          </p>
        )}
        {result && state && result.orders.length > 0 && (
          <>
            <Clock
              start={start}
              end={end}
              time={time}
              playing={playing}
              speed={speed}
              arrivals={result.orders.map((o) => ms(o.received_at))}
              onTime={setTime}
              onPlaying={setPlaying}
              onSpeed={setSpeed}
            />
            {result.warnings.length > 0 && (
              <ul className="border-b border-border bg-secondary px-4 py-1.5 text-[12px]">
                {result.warnings.map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
            )}
            <div className="flex min-h-0 flex-1 flex-col overflow-y-auto lg:flex-row lg:overflow-hidden">
              <aside className="shrink-0 border-b border-border bg-card p-4 lg:w-72 lg:overflow-y-auto lg:border-b-0 lg:border-r">
                <OrderBook orders={result.orders} state={state} selected={selected} onSelect={setSelected} />
                {selectedOrder && (
                  <div className="mt-4">
                    <OrderPath order={selectedOrder} time={time} />
                  </div>
                )}
              </aside>
              <main className="flex min-w-0 flex-1 flex-col lg:overflow-y-auto">
                <div className="grid flex-1 grid-cols-1 lg:grid-cols-2">
                  <OfficeZone state={state} closed={state.closed.office} />
                  <ProductionZone state={state} />
                  <StockZone state={state} />
                  <ShippingZone state={state} closed={state.closed.shipping} />
                </div>
                <Kpis result={result} />
              </main>
            </div>
          </>
        )}
      </div>
    </AppShell>
  );
}
