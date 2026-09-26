"use client";

import { Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { Diagnosis } from "@/lib/api";
import { cn } from "@/lib/utils";

const OUTCOME: Record<Diagnosis["outcome"], { label: string; style: string }> = {
  open: { label: "läuft", style: "border-primary text-primary" },
  resolved: { label: "behoben", style: "border-ok text-ok" },
  unresolved: { label: "offen", style: "border-danger text-danger" },
};

const when = (iso: string) =>
  new Date(iso).toLocaleString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });

/** Instandhaltungslog: alle Fehlersuchen der Maschine, Haeufigkeit je Fehler oben. */
export function MaintenanceLog({
  items,
  onResume,
  onDelete,
}: {
  items: Diagnosis[];
  onResume: (diagnosis: Diagnosis) => void;
  onDelete: (diagnosis: Diagnosis) => void;
}) {
  const counts = items.reduce<Map<string, number>>((acc, d) => acc.set(d.title, (acc.get(d.title) ?? 0) + 1), new Map());
  const frequent = [...counts.entries()].filter(([, n]) => n > 1).sort((a, b) => b[1] - a[1]);

  return (
    <section className="border border-line bg-card">
      <div className="flex flex-wrap items-center gap-3 px-4 py-3">
        <h2 className="font-mono text-sm font-semibold uppercase tracking-[0.06em]">Instandhaltungslog</h2>
        <span className="text-xs text-muted-foreground">{items.length} Fehlersuchen</span>
        {frequent.map(([title, n]) => (
          <span key={title} className="border border-danger/40 px-1.5 text-[11px] text-danger" title="wiederkehrend">
            {n}× {title.split(" ")[0]}
          </span>
        ))}
      </div>
      {items.length === 0 ? (
        <p className="border-t border-line px-4 py-5 text-sm text-muted-foreground">
          Noch keine Fehlersuche. In der Fehlerliste bei einem Eintrag „Diagnose“ wählen.
        </p>
      ) : (
        <ul className="divide-y divide-border border-t border-line">
          {items.map((d) => {
            const ok = d.steps.filter((s) => s.status === "ok").length;
            const nok = d.steps.filter((s) => s.status === "nok").length;
            return (
              <li key={d.id} className="flex flex-wrap items-start gap-x-3 gap-y-1 px-4 py-2.5 text-[13px]">
                <span className="w-36 shrink-0 font-mono text-xs text-muted-foreground">{when(d.started_at)}</span>
                <span className={cn("shrink-0 border px-1.5 text-[11px]", OUTCOME[d.outcome].style)}>{OUTCOME[d.outcome].label}</span>
                <div className="min-w-0 flex-1">
                  <div className="truncate font-medium">{d.title}</div>
                  <div className="text-xs text-muted-foreground">
                    {ok} ok · {nok} Fehler · {d.steps.length} Schritte{d.finding ? ` — ${d.finding}` : ""}
                  </div>
                </div>
                {d.outcome === "open" && (
                  <Button size="xs" variant="outline" onClick={() => onResume(d)}>
                    fortsetzen
                  </Button>
                )}
                <Button size="icon-xs" variant="ghost" aria-label="Eintrag löschen" className="hover:text-danger" onClick={() => onDelete(d)}>
                  <Trash2 />
                </Button>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
