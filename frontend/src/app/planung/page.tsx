"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { AppShell } from "@/components/AppShell";
import { CostTable } from "@/components/planning/CostTable";
import { MasterData } from "@/components/planning/MasterData";
import { MaterialTable } from "@/components/planning/MaterialTable";
import { newPosition, OrderForm, type OrderDraft } from "@/components/planning/OrderForm";
import { Schedule } from "@/components/planning/Schedule";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { leitstand, planning, type ArticleInfo, type CalcResult } from "@/lib/api";
import { minutesText, num, parseAmount, whenText } from "@/lib/format";

const TRIGGER = "px-3 text-sm data-active:font-semibold data-active:text-primary after:!bg-primary";

const pad = (n: number) => String(n).padStart(2, "0");
const localDate = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
const localDateTime = (d: Date) => `${localDate(d)}T${pad(d.getHours())}:${pad(d.getMinutes())}`;

function initialDraft(articles: ArticleInfo[]): OrderDraft {
  const now = new Date();
  const due = new Date(now.getTime() + 7 * 86_400_000);
  return { customer: "", received_at: localDateTime(now), due_date: localDate(due), positions: [newPosition(articles[0].id)] };
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-2">
      <h2 className="font-mono text-[11px] font-semibold uppercase tracking-[0.06em] text-muted-foreground">{title}</h2>
      {children}
    </section>
  );
}

/** Planung: Auftrag eingeben, Termin, Zeitplan, Material und Kosten sofort sehen (ohne LLM). */
export default function PlanningPage() {
  const [articles, setArticles] = useState<ArticleInfo[] | null>(null);
  const [draft, setDraft] = useState<OrderDraft | null>(null);
  const [result, setResult] = useState<CalcResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const latest = useRef(0);
  const router = useRouter();

  // Kalkulierte Bestellung ins Auftragsbuch (Leitstand) uebernehmen
  async function createOrder() {
    if (!draft) return;
    setCreating(true);
    try {
      const order = await leitstand.createOrder({
        customer: draft.customer.trim() || "Kunde ohne Namen",
        received_at: draft.received_at,
        due_date: draft.due_date || null,
        lines: draft.positions.map((p) => ({ article_id: p.article_id, quantity: parseAmount(p.quantity) ?? 0, unit: p.unit })),
      });
      toast.success(`Auftrag ${order.number} angelegt`, {
        action: { label: "Zum Leitstand", onClick: () => router.push("/leitstand") },
      });
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setCreating(false);
    }
  }

  useEffect(() => {
    planning
      .articles()
      .then((list) => {
        setArticles(list);
        if (list.length) setDraft(initialDraft(list));
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  // Neu rechnen bei jeder Aenderung; nur die letzte Antwort zaehlt
  useEffect(() => {
    if (!draft || draft.positions.some((p) => !p.article_id || !((parseAmount(p.quantity) ?? 0) > 0))) return;
    const id = ++latest.current;
    const timer = setTimeout(() => {
      planning
        .calc({
          received_at: draft.received_at,
          due_date: draft.due_date || null,
          positions: draft.positions.map((p) => ({ article_id: p.article_id, quantity: parseAmount(p.quantity) ?? 0, unit: p.unit })),
        })
        .then((calc) => {
          if (latest.current !== id) return;
          setResult(calc);
          setError(null);
        })
        .catch((err: Error) => latest.current === id && setError(err.message));
    }, 250);
    return () => clearTimeout(timer);
  }, [draft]);

  const s = result?.summary;
  const incomplete = !!draft?.positions.some((p) => !p.article_id || !((parseAmount(p.quantity) ?? 0) > 0));
  const stale = incomplete || !!error;
  return (
    <AppShell breadcrumb={[{ label: "Planung" }]}>
      <Tabs defaultValue="kalkulation" className="flex h-full flex-col gap-0">
        <div className="flex flex-wrap items-end gap-x-6 border-b border-border px-4 pt-3">
          <h1 className="pb-2 font-mono text-lg font-semibold uppercase tracking-[0.04em]">Planung</h1>
          <TabsList variant="line" className="h-10 justify-start gap-2 pb-1">
            <TabsTrigger value="kalkulation" className={TRIGGER}>
              Kalkulation
            </TabsTrigger>
            <TabsTrigger value="stammdaten" className={TRIGGER}>
              Stammdaten
            </TabsTrigger>
          </TabsList>
        </div>

        {error && !draft && <p className="m-4 border border-danger/40 bg-danger/5 px-3 py-2 text-sm text-danger">{error}</p>}
        {articles && articles.length === 0 && (
          <p className="m-6 max-w-xl text-sm text-muted-foreground">
            Noch keine Stammdaten (Artikel, Arbeitspläne, Materialien). Testwerk laden:{" "}
            <code className="font-mono">python scripts/load_testwerk.py</code>
          </p>
        )}

        <TabsContent value="kalkulation" className="flex min-h-0 flex-1 flex-col">
          {draft && articles && (
            <div className="flex min-h-0 flex-1 flex-col overflow-y-auto lg:flex-row lg:overflow-hidden">
              <aside className="shrink-0 border-b border-border bg-card p-4 lg:w-80 lg:overflow-y-auto lg:border-b-0 lg:border-r">
                <OrderForm articles={articles} draft={draft} onChange={setDraft} />
              </aside>

              <main className="min-w-0 flex-1 space-y-5 p-4 md:px-6 lg:overflow-y-auto">
                {error && <p className="border border-danger/40 bg-danger/5 px-3 py-2 text-sm text-danger">{error}</p>}
                {incomplete && (
                  <p className="border-l-[3px] border-nav bg-secondary px-3 py-2 text-[13px]">
                    Menge eingeben, dann wird neu gerechnet. Unten steht noch der letzte vollständige Stand.
                  </p>
                )}
                {result && s && (
                  <div className={stale ? "space-y-5 opacity-50" : "space-y-5"}>
                    <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                      <span className="font-mono text-[11px] font-semibold uppercase tracking-[0.06em] text-muted-foreground">Verladebereit</span>
                      <span className="font-mono text-2xl font-semibold uppercase">{whenText(result.ready_at)}</span>
                      {result.meets_due !== null && result.days_delta !== null && (
                        result.meets_due ? (
                          <span className="border border-ok px-2 text-sm font-semibold text-ok">
                            hält · {result.days_delta === 0 ? "ohne Puffer" : `${result.days_delta} ${result.days_delta === 1 ? "Tag" : "Tage"} Puffer`}
                          </span>
                        ) : (
                          <span className="border border-foreground px-2 text-sm font-semibold">
                            +{-result.days_delta} {result.days_delta === -1 ? "Tag" : "Tage"} nach Wunschtermin
                          </span>
                        )
                      )}
                      <span className="text-[13px] text-muted-foreground">Durchlauf {minutesText(s.lead_minutes)}</span>
                      <span className="ml-auto flex items-center gap-2">
                        <button
                          type="button"
                          disabled={creating || incomplete}
                          onClick={createOrder}
                          className="h-8 border border-line bg-card px-3 text-sm font-medium hover:border-primary hover:text-primary disabled:opacity-50"
                        >
                          Als Auftrag anlegen
                        </button>
                        <Link href="/leitstand" className="text-[13px] text-primary hover:underline">
                          Leitstand →
                        </Link>
                      </span>
                    </div>

                    <dl className="grid grid-cols-2 gap-3 border-y border-line py-2.5 font-mono sm:grid-cols-3 xl:grid-cols-6">
                      {[
                        [num(s.units), "Einheiten"],
                        [num(s.pallets), "Paletten"],
                        [num(s.trucks), "LKW"],
                        [`${num(s.paper_t, 1)} t`, "Rohpapier"],
                        [minutesText(s.line_minutes), "Linienzeit"],
                        [s.bottleneck?.split(" ")[0] ?? "–", "Engpass"],
                      ].map(([value, label]) => (
                        <div key={label}>
                          <dd className="text-lg font-semibold">{value}</dd>
                          <dt className="text-[11px] text-muted-foreground">{label}</dt>
                        </div>
                      ))}
                    </dl>

                    {result.warnings.length > 0 && (
                      <ul className="space-y-1 border-l-[3px] border-nav bg-secondary px-3 py-2 text-[13px]">
                        {result.warnings.map((warning) => (
                          <li key={warning}>{warning}</li>
                        ))}
                      </ul>
                    )}

                    <Section title="Zeitplan">
                      <Schedule result={result} />
                      <p className="text-[11px] text-muted-foreground">
                        Schraffiert: geschlossen (Büro Mo–Fr 07–16, Versand Mo–Fr 06–22). Gestauchte Spalte: Leerlauf. Balken antippen
                        oder überfahren zeigt die Herleitung.
                      </p>
                    </Section>

                    <details className="group space-y-2">
                      <summary className="cursor-pointer list-none font-mono text-[11px] font-semibold uppercase tracking-[0.06em] text-muted-foreground hover:text-foreground">
                        <span className="mr-1 inline-block transition-transform group-open:rotate-90">›</span>
                        Herleitung · {result.stations.length} Schritte
                      </summary>
                      <ol className="divide-y divide-border border border-line bg-card text-[13px]">
                        {result.stations.map((station) => (
                          <li key={station.key} className="grid gap-x-3 px-3 py-1.5 sm:grid-cols-[180px_270px_1fr]">
                            <span className="font-medium">{station.label}</span>
                            <span className="font-mono text-[12px] text-muted-foreground">
                              {whenText(station.start)} – {whenText(station.end)}
                            </span>
                            <span className="text-muted-foreground">{station.basis}</span>
                          </li>
                        ))}
                      </ol>
                    </details>

                    <Section title="Materialbedarf">
                      <MaterialTable materials={result.materials} />
                    </Section>

                    <Section title="Kosten">
                      <CostTable costs={result.costs} />
                    </Section>
                  </div>
                )}
              </main>
            </div>
          )}
        </TabsContent>

        <TabsContent value="stammdaten" className="min-h-0 flex-1 overflow-y-auto p-4 md:px-6">
          {articles && articles.length > 0 && <MasterData articles={articles} />}
        </TabsContent>
      </Tabs>
    </AppShell>
  );
}
