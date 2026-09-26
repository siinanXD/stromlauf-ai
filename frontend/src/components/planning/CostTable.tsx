import type { CalcResult } from "@/lib/api";
import { eur, num, plural } from "@/lib/format";
import { cn } from "@/lib/utils";

const HEAD = "px-3 py-2 text-right font-mono text-[11px] font-semibold uppercase tracking-[0.06em] text-muted-foreground";
const CELL = "whitespace-nowrap px-3 py-1.5 text-right font-mono";

/** Kosten je Position (Material, Fertigung, Buero und Versand anteilig nach Paletten) und Summe. */
export function CostTable({ costs }: { costs: CalcResult["costs"] }) {
  return (
    <div className="space-y-1.5">
      <div className="overflow-x-auto border border-line bg-card">
        <table className="w-full min-w-[640px] border-collapse text-[13px]">
          <thead className="border-b border-line">
            <tr>
              <th className={cn(HEAD, "text-left")}>Position</th>
              <th className={HEAD}>Material</th>
              <th className={HEAD}>Fertigung</th>
              <th className={HEAD}>Büro</th>
              <th className={HEAD}>Versand</th>
              <th className={HEAD}>Summe</th>
              <th className={HEAD}>je Einheit</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {costs.positions.map((row, index) => (
              <tr key={index}>
                <td className="px-3 py-1.5">
                  {row.article}
                  <span className="block font-mono text-[11px] text-muted-foreground">
                    {num(row.units)} {plural(row.unit_name)}
                  </span>
                </td>
                <td className={CELL}>{eur(row.material)}</td>
                <td className={CELL}>{eur(row.production)}</td>
                <td className={CELL}>{eur(row.office)}</td>
                <td className={CELL}>{eur(row.shipping)}</td>
                <td className={cn(CELL, "font-semibold")}>{eur(row.total)}</td>
                <td className={cn(CELL, "font-semibold")}>
                  {eur(row.per_unit)}
                  <span className="block text-[11px] font-normal text-muted-foreground">je {row.unit_name}</span>
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot className="border-t border-line">
            <tr>
              <td className="px-3 py-1.5 font-mono text-[11px] font-semibold uppercase tracking-[0.06em]">Auftrag</td>
              <td className={CELL}>{eur(costs.total.material)}</td>
              <td className={CELL}>{eur(costs.total.production)}</td>
              <td className={CELL}>{eur(costs.total.office)}</td>
              <td className={CELL}>{eur(costs.total.shipping)}</td>
              <td className={cn(CELL, "font-semibold")}>{eur(costs.total.total)}</td>
              <td />
            </tr>
          </tfoot>
        </table>
      </div>
      <p className="text-[11px] text-muted-foreground">
        Alle Preise und Sätze sind Richtwerte (Annahme). Maschinenstundensätze stehen im Tab „Kennzahlen“ der Maschine und
        wirken sofort; Büro und Versand werden nach Paletten auf die Positionen verteilt.
      </p>
    </div>
  );
}
