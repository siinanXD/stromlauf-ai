"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { AblaufGraph } from "@/components/ablauf/AblaufGraph";
import { Dropzone } from "@/components/ablauf/Dropzone";
import { Ergebnis } from "@/components/ablauf/Ergebnis";
import { GruppenVorschlag } from "@/components/ablauf/GruppenVorschlag";
import { haengt } from "@/components/ablauf/knoten";
import { pruefeLimits, wendeAn, type Abgelegt, type Gruppierung } from "@/components/ablauf/ordner";
import { SchrittPanel } from "@/components/ablauf/SchrittPanel";
import { Zeiten } from "@/components/ablauf/ZeitenTabelle";
import { ablauf, type Run, type Zeiten as ZeitenDaten } from "@/lib/api";

const POLL_MS = 2000;

/** Genau eine Datei ohne Ordner: der alte Weg, ein Lauf ohne Vorschlag. */
const einfach = (abgelegt: Abgelegt[]) => abgelegt.length === 1 && !abgelegt[0].pfad.includes("/");

/** Ablauf: Unterlagen oder Ordner ablegen, Anlagen bestätigen, Läufe starten, die sieben Schritte live verfolgen. */
export default function AblaufPage() {
  const [abgelegt, setAbgelegt] = useState<Abgelegt[]>([]);
  const [gruppierung, setGruppierung] = useState<Gruppierung | null>(null);
  const [pruefe, setPruefe] = useState(false);
  const [runs, setRuns] = useState<Run[]>([]);
  const [selected, setSelected] = useState<{ runId: string; key: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [zeiten, setZeiten] = useState<ZeitenDaten | null>(null);
  const [zeitenFehler, setZeitenFehler] = useState(false);
  const [now, setNow] = useState(() => new Date());
  const anfrage = useRef(0);
  const runsRef = useRef<Run[]>([]);
  useEffect(() => {
    runsRef.current = runs;
  }, [runs]);

  // Ein hängender Lauf zählt wie ein beendeter: Seite wieder frei, kein Polling mehr für ihn.
  const aktiv = runs.some((r) => r.status === "laeuft" && !haengt(r, now));
  useEffect(() => {
    if (!aktiv) return;
    const timer = setInterval(() => {
      const offen = runsRef.current.filter((r) => r.status === "laeuft" && !haengt(r, new Date()));
      Promise.all(offen.map((r) => ablauf.get(r.id)))
        .then((neu) => {
          setRuns((alt) => alt.map((r) => neu.find((n) => n.id === r.id) ?? r));
          setNow(new Date());
        })
        .catch((err) => setError((err as Error).message));
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [aktiv]);

  function ablegen(liste: Abgelegt[]) {
    const nr = ++anfrage.current;
    setAbgelegt(liste);
    setGruppierung(null);
    setError(null);
    setPruefe(false);
    if (liste.length === 0) return;
    const grenze = pruefeLimits(liste);
    if (grenze) return setError(grenze);
    if (einfach(liste)) return;
    setPruefe(true);
    ablauf
      .gruppen(liste.map((a) => ({ name: a.file.name, pfad: a.pfad })))
      .then((vorschlag) => nr === anfrage.current && setGruppierung(wendeAn(vorschlag, liste)))
      .catch((err) => nr === anfrage.current && setError((err as Error).message))
      .finally(() => nr === anfrage.current && setPruefe(false));
  }

  /** Läufe nacheinander anlegen; bei einem Fehler bleiben die bisherigen stehen. */
  async function starte(jobs: { files: File[]; name: string }[]) {
    setError(null);
    setSelected(null);
    setRuns([]);
    setStarting(true);
    try {
      for (const job of jobs) {
        const created = await ablauf.start(job.files, job.name);
        setRuns((alt) => [...alt, created]);
      }
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setStarting(false);
    }
  }

  async function startAlle() {
    if (!gruppierung) return;
    const jobs = gruppierung.gruppen.map((g) => ({ files: g.dateien.map((d) => d.file), name: g.name.trim() }));
    setGruppierung(null);
    setAbgelegt([]);
    await starte(jobs);
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
  const ende = runs.length > 0 && runs.every((r) => r.status !== "laeuft");
  useEffect(() => {
    if (ende) ladeZeiten();
  }, [ende, ladeZeiten]);

  const close = useCallback(() => setSelected(null), []);
  const haengende = runs.filter((r) => haengt(r, now));
  const running = starting || pruefe || aktiv;

  return (
    <AppShell breadcrumb={[{ label: "Ablauf" }]}>
      <div className="flex h-full flex-col overflow-y-auto">
        <div className="space-y-3 border-b border-border p-4 md:px-6">
          <h1 className="font-mono text-lg font-semibold uppercase tracking-[0.04em]">Ablauf</h1>
          <p className="text-subhead text-muted-foreground">Stromlaufplan, Stückliste, AWL oder Handbuch hier ablegen. Alles Weitere passiert von selbst.</p>
          {gruppierung ? (
            <GruppenVorschlag gruppierung={gruppierung} onChange={setGruppierung} onStart={startAlle} onAbbrechen={() => ablegen([])} disabled={running} />
          ) : (
            <>
              <Dropzone files={abgelegt} onFiles={ablegen} disabled={running} />
              {pruefe && <p className="text-footnote text-muted-foreground">Anlagen werden erkannt …</p>}
              {einfach(abgelegt) && (
                <button
                  type="button"
                  onClick={() => starte([{ files: abgelegt.map((a) => a.file), name: "" }])}
                  disabled={running}
                  className="min-h-11 rounded-md bg-primary px-4 text-subhead font-medium text-primary-foreground disabled:opacity-50"
                >
                  Lauf starten
                </button>
              )}
            </>
          )}
          {error && (
            <p role="alert" className="text-footnote text-danger">
              {error}
            </p>
          )}
          {haengende.length > 0 && (
            <p role="alert" className="text-footnote text-danger">
              {haengende.length === 1 ? "Lauf hängt" : `${haengende.length} Läufe hängen`} seit 10 Minuten. Backend neu gestartet? Neu starten.
            </p>
          )}
          {runs.map(
            (r) =>
              r.status === "fehler" &&
              r.error && (
                <p key={r.id} role="alert" className="text-footnote text-danger">
                  {runs.length > 1 ? `${r.name}: ` : ""}
                  {r.error}
                </p>
              ),
          )}
        </div>

        {runs.map((run) => {
          const step = selected?.runId === run.id ? (run.steps.find((s) => s.key === selected.key) ?? null) : null;
          return (
            <section key={run.id} aria-label={run.name || "Lauf"} data-testid={`lauf-${run.id}`} className="flex min-h-0 flex-col border-b border-border md:flex-row">
              <div className="flex min-w-0 flex-1 flex-col">
                {runs.length > 1 && <h2 className="px-4 pt-3 text-headline font-semibold md:px-6">{run.name}</h2>}
                <div className="h-[220px] shrink-0 border-b border-border">
                  <AblaufGraph steps={run.steps} selected={step?.key ?? null} onSelect={(s) => setSelected({ runId: run.id, key: s.key })} />
                </div>
                <Ergebnis run={run} />
              </div>
              {step && <SchrittPanel step={step} onClose={close} />}
            </section>
          );
        })}

        {zeiten && !zeitenFehler && <Zeiten zeiten={zeiten} />}
        {zeitenFehler && <p className="p-4 text-footnote text-muted-foreground md:px-6">Zeiten nicht verfügbar</p>}
      </div>
    </AppShell>
  );
}
