import type { CalcMaterial } from "@/lib/api";
import { eur, qtyText } from "@/lib/format";
import { cn } from "@/lib/utils";

const HEAD = "px-3 py-2 text-left font-mono text-[11px] font-semibold uppercase tracking-[0.06em] text-muted-foreground";

/** Materialbedarf mit Herleitung; Rezepturbestandteile eingerueckt unter dem Eigenfertigungsmaterial. */
export function MaterialTable({ materials }: { materials: CalcMaterial[] }) {
  return (
    <div className="overflow-x-auto border border-line bg-card">
      <table className="w-full min-w-[560px] border-collapse text-[13px]">
        <thead className="border-b border-line">
          <tr>
            <th className={HEAD}>Material</th>
            <th className={cn(HEAD, "text-right")}>Menge</th>
            <th className={HEAD}>Herleitung</th>
            <th className={cn(HEAD, "text-right")}>Kosten</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {materials.map((m) => (
            <tr key={m.code}>
              <td className="px-3 py-1.5" style={{ paddingLeft: 12 + m.level * 16 }}>
                {m.level > 0 && <span className="text-muted-foreground">↳ </span>}
                {m.name}
                {m.made && <span className="ml-1.5 font-mono text-[11px] text-muted-foreground">Eigenfertigung</span>}
              </td>
              <td className="whitespace-nowrap px-3 py-1.5 text-right font-mono">{qtyText(m.qty, m.unit)}</td>
              <td className="max-w-[320px] px-3 py-1.5 text-[12px] text-muted-foreground">{m.basis}</td>
              <td className="whitespace-nowrap px-3 py-1.5 text-right font-mono" title={m.price !== null ? `${eur(m.price)} je ${m.unit} · ${m.price_source}` : undefined}>
                {m.made ? "–" : eur(m.cost)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
