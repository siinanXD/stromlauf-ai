"use client";

import { useEffect, useState } from "react";

import { costs, PURPOSE_LABELS, type MachineCosts } from "@/lib/api";
import { costText } from "@/lib/format";

/** Monatskosten einer Maschine im Kopf der Maschinenansicht; Tooltip zeigt die Aufteilung je Zweck. */
export function MachineCostChip({ machineId, refreshKey = 0 }: { machineId: string; refreshKey?: number }) {
  const [data, setData] = useState<MachineCosts | null>(null);

  useEffect(() => {
    let cancelled = false;
    costs
      .machine(machineId)
      .then((result) => !cancelled && setData(result))
      .catch(() => !cancelled && setData(null));
    return () => {
      cancelled = true;
    };
  }, [machineId, refreshKey]);

  if (!data) return null;
  const lines = Object.entries(data.month.by_purpose).map(
    ([purpose, bucket]) => `${PURPOSE_LABELS[purpose] ?? purpose}: ${costText(bucket.cents)} (${bucket.calls})`,
  );
  const title = [
    `Diesen Monat ${data.month.calls} KI-Aufrufe`,
    ...lines,
    `Gesamt seit Anlage: ${costText(data.total.cents)}`,
    data.workspace.cap_cents !== null ? `Workspace-Limit: ${costText(data.workspace.month_cents)} von ${costText(data.workspace.cap_cents)}` : "",
  ]
    .filter(Boolean)
    .join("\n");
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-footnote whitespace-nowrap ${
        data.workspace.exceeded ? "bg-error-soft text-danger" : "bg-bg-fill text-muted-foreground"
      }`}
      title={title}
      data-testid="machine-cost-chip"
    >
      KI diesen Monat {costText(data.month.cents)}
      {data.workspace.exceeded && " · Limit erreicht"}
    </span>
  );
}
