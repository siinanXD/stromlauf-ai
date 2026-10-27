"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { AblaufGraph } from "@/components/ablauf/AblaufGraph";
import { Dropzone } from "@/components/ablauf/Dropzone";
import { Ergebnis } from "@/components/ablauf/Ergebnis";
import { haengt } from "@/components/ablauf/knoten";
import { SchrittPanel } from "@/components/ablauf/SchrittPanel";
import { Zeiten } from "@/components/ablauf/ZeitenTabelle";
import { ablauf, type Run, type RunStep, type Zeiten as ZeitenDaten } from "@/lib/api";

const POLL_MS = 2000;

/** Ablauf: Unterlagen ablegen, Lauf starten, die sieben Schritte live verfolgen. */
export default function AblaufPage() {
  const [files, setFiles] = useState<File[]>([]);
  const [run, setRun] = useState<Run | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [zeiten, setZeiten] = useState<ZeitenDaten | null>(null);
  const [zeitenFehler, setZeitenFehler] = useState(false);
  const [now, setNow] = useState(() => new Date());
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  const stop = useCallback(() => {
    if (timer.current) clearInterval(timer.current);
    timer.current = null;
  }, []);
  useEffect(() => stop, [stop]);

  const poll = useCallback(
    (id: string) => {
      stop();
      timer.current = setInterval(() => {
        ablauf
          .get(id)
          .then((next) => {
            setRun(next);
            setNow(new Date());
            if (next.status !== "laeuft") stop();
          })
          .catch((err) => setError((err as Error).message));
      }, POLL_MS);
    },
    [stop],
  );

  async function start() {
    setError(null);
    setSelected(null);
    setStarting(true);
    try {
      const created = await ablauf.start(files, "");
      setRun(created);
      if (created.status === "laeuft") poll(created.id);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setStarting(false);
    }
  }

  const ladeZeiten = useCallback(() => {
    ablauf
      .zeiten()
      .then((z) => {
        setZeiten(z);
        setZeitenFehler(false);
      })
      .catch(() => setZeitenFehler(true));
  }, []);
  useEffect(ladeZeiten, [ladeZeiten]);
  const status = run?.status;
  useEffect(() => {
    if (status === "fertig" || status === "fehler") ladeZeiten();
  }, [status, ladeZeiten]);

  const select = useCallback((step: RunStep) => setSelected(step.key), []);
  const close = useCallback(() => setSelected(null), []);
  const hung = run ? haengt(run, now) : false;
  // Ein hängender Lauf zählt wie ein beendeter: Seite wieder frei, Polling aus.
  const running = starting || (run?.status === "laeuft" && !hung);
  const step = run?.steps.find((s) => s.key === selected) ?? null;
  useEffect(() => {
    if (hung) stop();
  }, [hung, stop]);

  return (
    <AppShell breadcrumb={[{ label: "Ablauf" }]}>
      <div className="flex h-full flex-col overflow-y-auto">
        <div className="space-y-3 border-b border-border p-4 md:px-6">
          <h1 className="font-mono text-lg font-semibold uppercase tracking-[0.04em]">Ablauf</h1>
          <p className="text-subhead text-muted-foreground">Stromlaufplan, Stückliste, AWL oder Handbuch hier ablegen. Alles Weitere passiert von selbst.</p>
          <Dropzone files={files} onFiles={setFiles} disabled={running} />
          <button
            type="button"
            onClick={start}
            disabled={files.length === 0 || running}
            className="min-h-11 rounded-md bg-primary px-4 text-subhead font-medium text-primary-foreground disabled:opacity-50"
          >
            Lauf starten
          </button>
          {error && (
            <p role="alert" className="text-footnote text-danger">
              {error}
            </p>
          )}
          {hung && (
            <p role="alert" className="text-footnote text-danger">
              Lauf hängt seit 10 Minuten. Backend neu gestartet? Lauf neu starten.
            </p>
          )}
          {run?.status === "fehler" && run.error && (
            <p role="alert" className="text-footnote text-danger">
              {run.error}
            </p>
          )}
        </div>

        {run && (
          <div className="flex min-h-0 flex-1 flex-col md:flex-row">
            <div className="flex min-w-0 flex-1 flex-col">
              <div className="h-[220px] shrink-0 border-b border-border">
                <AblaufGraph steps={run.steps} selected={selected} onSelect={select} />
              </div>
              <Ergebnis run={run} />
              {zeiten && !zeitenFehler && <Zeiten zeiten={zeiten} />}
              {zeitenFehler && <p className="p-4 text-footnote text-muted-foreground md:px-6">Zeiten nicht verfügbar</p>}
            </div>
            {step && <SchrittPanel step={step} onClose={close} />}
          </div>
        )}
      </div>
    </AppShell>
  );
}
