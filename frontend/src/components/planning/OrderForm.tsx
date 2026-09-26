"use client";

import { Plus, X } from "lucide-react";

import type { ArticleInfo, QuantityUnit } from "@/lib/api";
import { plural } from "@/lib/format";

export interface DraftPosition {
  key: string;
  article_id: string;
  quantity: string;
  unit: QuantityUnit;
}

export interface OrderDraft {
  customer: string;
  received_at: string; // datetime-local "YYYY-MM-DDTHH:MM"
  due_date: string; // "YYYY-MM-DD" oder leer
  positions: DraftPosition[];
}

const FIELD = "h-8 w-full min-w-0 border border-border bg-background px-2 text-[13px]";
const LABEL = "text-[11px] text-muted-foreground";

let counter = 0;
export const newPosition = (articleId: string, quantity = "10", unit: QuantityUnit = "pallet"): DraftPosition => ({
  key: `p${++counter}`,
  article_id: articleId,
  quantity,
  unit,
});

/** Auftrag: Kunde, Eingang, Wunschtermin, Positionen (Artikel, Menge, Einheit). */
export function OrderForm({ articles, draft, onChange }: { articles: ArticleInfo[]; draft: OrderDraft; onChange: (draft: OrderDraft) => void }) {
  const lines = [...new Set(articles.map((a) => a.line))];
  const setPosition = (key: string, change: Partial<DraftPosition>) =>
    onChange({ ...draft, positions: draft.positions.map((p) => (p.key === key ? { ...p, ...change } : p)) });

  return (
    <form className="space-y-3" onSubmit={(event) => event.preventDefault()}>
      <div className="font-mono text-[11px] font-semibold uppercase tracking-[0.06em] text-muted-foreground">Auftrag</div>
      <label className="block">
        <span className={LABEL}>Kunde</span>
        <input value={draft.customer} onChange={(e) => onChange({ ...draft, customer: e.target.value })} placeholder="Muster Handel GmbH" className={FIELD} />
      </label>
      <div className="grid grid-cols-2 gap-2">
        <label className="block">
          <span className={LABEL}>Eingang</span>
          <input
            type="datetime-local"
            value={draft.received_at}
            onChange={(e) => e.target.value && onChange({ ...draft, received_at: e.target.value })}
            className={`${FIELD} px-1 font-mono text-[12px]`}
          />
        </label>
        <label className="block">
          <span className={LABEL}>Wunschtermin</span>
          <input type="date" value={draft.due_date} onChange={(e) => onChange({ ...draft, due_date: e.target.value })} className={`${FIELD} px-1 font-mono text-[12px]`} />
        </label>
      </div>

      <div className="pt-1 font-mono text-[11px] font-semibold uppercase tracking-[0.06em] text-muted-foreground">Positionen</div>
      <ul className="space-y-2">
        {draft.positions.map((position, index) => {
          const article = articles.find((a) => a.id === position.article_id);
          const missing = !(Number(position.quantity) > 0);
          return (
            <li key={position.key} className="space-y-1.5 border border-border bg-secondary/60 p-2">
              <div className="flex items-center gap-1.5">
                <span className="font-mono text-[11px] text-muted-foreground">{index + 1}</span>
                <select
                  aria-label={`Artikel Position ${index + 1}`}
                  value={position.article_id}
                  onChange={(e) => setPosition(position.key, { article_id: e.target.value })}
                  className={FIELD}
                >
                  {lines.map((line) => (
                    <optgroup key={line} label={line}>
                      {articles
                        .filter((a) => a.line === line)
                        .map((a) => (
                          <option key={a.id} value={a.id}>
                            {a.name}
                          </option>
                        ))}
                    </optgroup>
                  ))}
                </select>
                {draft.positions.length > 1 && (
                  <button
                    type="button"
                    aria-label={`Position ${index + 1} entfernen`}
                    onClick={() => onChange({ ...draft, positions: draft.positions.filter((p) => p.key !== position.key) })}
                    className="grid size-7 shrink-0 place-items-center text-muted-foreground hover:text-danger"
                  >
                    <X className="size-3.5" />
                  </button>
                )}
              </div>
              <div className="flex gap-1.5 pl-4">
                <input
                  aria-label={`Menge Position ${index + 1}`}
                  inputMode="decimal"
                  value={position.quantity}
                  onChange={(e) => setPosition(position.key, { quantity: e.target.value.replace(",", ".") })}
                  className={`${FIELD} font-mono ${missing ? "border-foreground" : ""}`}
                />
                <select
                  aria-label={`Einheit Position ${index + 1}`}
                  value={position.unit}
                  onChange={(e) => setPosition(position.key, { unit: e.target.value as QuantityUnit })}
                  className="h-8 w-32 shrink-0 border border-border bg-background px-2 text-[13px]"
                >
                  <option value="unit">{plural(article?.unit_name ?? "Paket")}</option>
                  <option value="pallet">Paletten</option>
                </select>
              </div>
              {missing && <p className="pl-4 text-[11px] text-muted-foreground">Menge größer 0 eingeben</p>}
            </li>
          );
        })}
      </ul>
      <button
        type="button"
        onClick={() => onChange({ ...draft, positions: [...draft.positions, newPosition(articles[0]?.id ?? "")] })}
        className="flex items-center gap-1 text-[13px] text-primary hover:underline"
      >
        <Plus className="size-3.5" />
        Position
      </button>
      <p className="border-l-[3px] border-nav bg-secondary px-2.5 py-1.5 text-[11px] leading-snug text-muted-foreground">
        Annahme: freie Kapazität, keine anderen Aufträge, Rohstoffe vorrätig. Warteschlangen und Bestände kommen mit der Simulation.
      </p>
    </form>
  );
}
