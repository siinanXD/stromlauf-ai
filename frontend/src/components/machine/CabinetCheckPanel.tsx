"use client";

import { useEffect, useState } from "react";

import { plant, type CabinetCheck } from "@/lib/api";

function Column({ title, hint, tags, empty }: { title: string; hint: string; tags: string[]; empty: string }) {
  return (
    <section aria-label={title} className="min-w-0">
      <h4 className="font-mono text-[11px] font-semibold uppercase tracking-[0.06em] text-muted-foreground">
        {title} ({tags.length})
      </h4>
      <p className="mb-2 text-xs text-muted-foreground">{hint}</p>
      {tags.length === 0 ? (
        <p className="text-sm text-muted-foreground">{empty}</p>
      ) : (
        <ul className="flex flex-wrap gap-1.5">
          {tags.map((tag) => (
            <li key={tag} className="border border-line bg-background px-2 py-0.5 font-mono text-[13px]">
              {tag}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

/** Abgleich Schrankfoto ↔ Stromlaufplan: was nur auf einer Seite vorkommt (SIN-979). `version` lädt nach jeder Änderung neu. */
export function CabinetCheckPanel({ machineId, version }: { machineId: string; version: string }) {
  const [check, setCheck] = useState<CabinetCheck | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let current = true;
    plant
      .cabinetCheck(machineId)
      .then((result) => current && (setCheck(result), setFailed(false)))
      .catch(() => current && setFailed(true));
    return () => {
      current = false;
    };
  }, [machineId, version]);

  if (failed) return <p className="text-sm text-muted-foreground">Der Abgleich mit dem Plan ist gerade nicht verfügbar.</p>;
  if (!check) return null;

  return (
    <section aria-label="Abgleich Schrank und Plan" className="border border-line bg-card p-4">
      <h3 className="mb-3 font-mono text-sm font-semibold uppercase tracking-[0.04em]">Abgleich mit dem Stromlaufplan</h3>
      <div className="grid gap-4 md:grid-cols-3">
        <Column title="Fehlt im Schrank" hint="Im Plan, aber im Schrankbild nicht markiert" tags={check.missing_in_cabinet} empty="Nichts fehlt." />
        <Column title="Fehlt im Plan" hint="Im Schrankbild markiert, im Plan nicht gefunden" tags={check.missing_in_plan} empty="Nichts fehlt." />
        <Column title="Stimmt überein" hint="In Schrankbild und Plan" tags={check.in_both} empty="Noch keine Übereinstimmung." />
      </div>
    </section>
  );
}
