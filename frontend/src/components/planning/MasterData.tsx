"use client";

import { ChevronRight } from "lucide-react";
import { useEffect, useState } from "react";

import { planning, type ArticleInfo, type MaterialInfo, type RoutingInfo } from "@/lib/api";
import { eur, num, plural } from "@/lib/format";

const HEAD = "px-3 py-2 text-left font-mono text-[11px] font-semibold uppercase tracking-[0.06em] text-muted-foreground";
const CELL = "px-3 py-1.5";

const rateText = (step: RoutingInfo, unitName: string) =>
  step.rate_unit === "pallet_h" ? `${num(step.rate, 1)} Paletten/h` : `${num(step.rate, 1)} ${plural(unitName)}/min`;

function ArticleDetails({ article }: { article: ArticleInfo }) {
  const area = (article.sheet_w_mm * article.sheet_l_mm) / 1e6;
  return (
    <div className="space-y-3 border-t border-border bg-background px-3 py-3 text-[13px]">
      <p className="text-muted-foreground">
        Rohpapier je {article.unit_name}: {num(article.sheets_per_unit)} Blatt × {num(area, 4)} m² × {article.plies} Lagen ×{" "}
        {num(article.gsm, 0)} g/m² × (1 + {num(article.waste_pct, 0)} % Verschnitt) ={" "}
        <span className="font-mono font-semibold text-foreground">{num(article.paper_kg_per_unit, 3)} kg</span>
      </p>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[620px] border-collapse">
          <thead className="border-b border-border">
            <tr>
              <th className={HEAD}>Arbeitsplan</th>
              <th className={HEAD}>Leistung</th>
              <th className={HEAD}>Rüsten</th>
              <th className={HEAD}>Stundensatz</th>
              <th className={HEAD}>Herleitung</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {article.routing.map((step) => (
              <tr key={step.seq}>
                <td className={CELL}>{step.machine_name}</td>
                <td className={`${CELL} whitespace-nowrap font-mono`}>{rateText(step, article.unit_name)}</td>
                <td className={`${CELL} font-mono`}>{num(step.setup_min)} min</td>
                <td className={`${CELL} whitespace-nowrap font-mono`}>{step.hourly_rate === null ? "fehlt" : `${eur(step.hourly_rate)}/h`}</td>
                <td className={`${CELL} text-muted-foreground`}>{step.basis}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[420px] border-collapse">
          <thead className="border-b border-border">
            <tr>
              <th className={HEAD}>Stückliste</th>
              <th className={HEAD}>Menge</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {article.bom.map((line) => (
              <tr key={line.material_code}>
                <td className={CELL}>{line.material_name}</td>
                <td className={`${CELL} font-mono`}>
                  {num(line.qty, line.qty < 1 ? 3 : 0)} {line.unit} je {line.per === "pallet" ? "Palette" : article.unit_name}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/** Stammdaten der Vorkalkulation (nur lesen): Artikel mit Arbeitsplan und Stueckliste, Materialien mit Preis. */
export function MasterData({ articles }: { articles: ArticleInfo[] }) {
  const [materials, setMaterials] = useState<MaterialInfo[] | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  useEffect(() => {
    planning.materials().then(setMaterials).catch(() => setMaterials([]));
  }, []);

  return (
    <div className="max-w-5xl space-y-6">
      <p className="text-[13px] text-muted-foreground">
        Aus dem Testwerk geladen (<code className="font-mono">python scripts/load_testwerk.py</code>). Maschinenstundensätze
        ändern sich im Tab „Kennzahlen“ der jeweiligen Maschine; Preise ohne Quelle sind Richtwerte.
      </p>

      <section className="space-y-2">
        <h2 className="font-mono text-[11px] font-semibold uppercase tracking-[0.06em] text-muted-foreground">Artikel · {articles.length}</h2>
        <div className="border border-line bg-card">
          {articles.map((article) => {
            const expanded = open === article.id;
            const bottleneck = Math.min(
              ...article.routing.map((s) => (s.rate_unit === "pallet_h" ? (s.rate * article.units_per_pallet) / 60 : s.rate)),
            );
            return (
              <div key={article.id} className="border-b border-border last:border-b-0">
                <button
                  type="button"
                  aria-expanded={expanded}
                  onClick={() => setOpen(expanded ? null : article.id)}
                  className="grid w-full grid-cols-[16px_minmax(0,1fr)_auto] items-center gap-x-3 px-3 py-2 text-left text-[13px] hover:bg-secondary sm:grid-cols-[16px_110px_minmax(0,1fr)_150px_110px_120px]"
                >
                  <ChevronRight className={`size-3.5 text-muted-foreground transition-transform ${expanded ? "rotate-90" : ""}`} />
                  <span className="hidden font-mono text-[12px] sm:block">{article.code}</span>
                  <span className="min-w-0 truncate">{article.name}</span>
                  <span className="hidden text-muted-foreground sm:block">{article.line}</span>
                  <span className="hidden font-mono text-[12px] sm:block">{num(article.units_per_pallet)} je Palette</span>
                  <span className="font-mono text-[12px]">
                    {article.routing.length ? `${num(bottleneck, 1)}/min` : "kein Plan"}
                  </span>
                </button>
                {expanded && <ArticleDetails article={article} />}
              </div>
            );
          })}
        </div>
      </section>

      <section className="space-y-2">
        <h2 className="font-mono text-[11px] font-semibold uppercase tracking-[0.06em] text-muted-foreground">
          Materialien · {materials?.length ?? "…"}
        </h2>
        <div className="overflow-x-auto border border-line bg-card">
          <table className="w-full min-w-[620px] border-collapse text-[13px]">
            <thead className="border-b border-line">
              <tr>
                <th className={HEAD}>Material</th>
                <th className={HEAD}>Preis</th>
                <th className={HEAD}>Quelle / Herkunft</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {materials?.map((m) => (
                <tr key={m.code}>
                  <td className={CELL}>
                    {m.name}
                    <span className="ml-1.5 font-mono text-[11px] text-muted-foreground">{m.code}</span>
                  </td>
                  <td className={`${CELL} whitespace-nowrap font-mono`}>{m.price === null ? "–" : `${eur(m.price)} je ${m.unit}`}</td>
                  <td className={`${CELL} text-muted-foreground`}>
                    {m.made_on
                      ? `Eigenfertigung auf ${m.made_on}, ${num(m.made_rate_per_h ?? 0, 1)} ${m.unit}/h; Rezeptur je ${m.unit}: ${m.bom
                          .map((line) => `${num(line.qty, line.qty < 1 ? 2 : 0)} ${line.unit} ${line.material_name}`)
                          .join(", ")}`
                      : m.price_source}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
