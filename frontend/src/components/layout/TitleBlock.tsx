import type { Layout } from "@/lib/api";

import { formatMm } from "./geometry";

/** Schriftfeld wie auf einer Zeichnung: Maschine, Blatt, Ansicht, Masse. */
export function TitleBlock({ layout, machineName }: { layout: Layout; machineName: string }) {
  const size = layout.width_mm && layout.depth_mm ? `${formatMm(layout.width_mm)} × ${formatMm(layout.depth_mm)} mm` : "Masse offen";
  return (
    <div className="grid w-64 grid-cols-[1fr_auto] border border-line bg-card font-mono text-[11px]">
      <div className="truncate border-b border-r border-line px-2 py-1.5 text-[13px] font-semibold">{machineName}</div>
      <div className="border-b border-line px-2 py-1.5 text-muted-foreground">Blatt 1/1</div>
      <div className="border-r border-line px-2 py-1.5 text-muted-foreground">Draufsicht · {size}</div>
      <div className="px-2 py-1.5 text-muted-foreground">{layout.scale_note || "–"}</div>
    </div>
  );
}
