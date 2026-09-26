"use client";

import { Handle, NodeResizer, Position, type Node, type NodeProps } from "@xyflow/react";
import { useMemo } from "react";

import { HALL_KIND_LABELS, type SiteHall } from "@/lib/api";
import { hallTitle, miniPlan, type Rect } from "@/lib/site";
import { cn } from "@/lib/utils";

export const HEADER_H = 22;
export const MIN_W = 200;
export const MIN_H = 140;

export type HallBlockData = { hall: SiteHall; onResized: (rect: Rect) => void };
export type HallBlockType = Node<HallBlockData, "hall">;

const HANDLE = "!size-2.5 !rounded-none !border-primary !bg-card opacity-0 transition-opacity group-hover:opacity-100";

/** Halle im Standortplan: Grundriss mit Kopfzeile, verkleinertem Maschinenlayout und Toren. */
export function HallBlockNode({ data, selected, width, height }: NodeProps<HallBlockType>) {
  const { hall } = data;
  const w = width ?? hall.w;
  const h = height ?? hall.h;
  const body = { w, h: Math.max(0, h - HEADER_H) };
  const plan = useMemo(() => miniPlan(hall.machines, { w, h: Math.max(0, h - HEADER_H) }), [hall.machines, w, h]);

  return (
    <div
      className={cn(
        "group relative size-full border-[1.5px] bg-card",
        selected ? "border-primary shadow-[0_0_0_1px_var(--primary)]" : "border-line hover:border-primary",
      )}
    >
      <NodeResizer
        isVisible={!!selected}
        minWidth={MIN_W}
        minHeight={MIN_H}
        lineClassName="!border-primary"
        handleClassName="!size-2.5 !rounded-none !border-primary !bg-card"
        onResizeEnd={(_, p) => data.onResized({ x: p.x, y: p.y, w: p.width, h: p.height })}
      />
      <Handle type="target" position={Position.Left} className={HANDLE} />

      <div className="flex items-center gap-2 bg-nav px-2 text-white" style={{ height: HEADER_H }}>
        <span className="truncate font-mono text-[12px] font-semibold uppercase tracking-[0.04em]" title={hall.name}>
          {hallTitle(hall)}
        </span>
        {hall.open_diagnoses > 0 && (
          <span title="Laufende Fehlersuchen" className="ml-auto shrink-0 bg-danger px-1.5 font-mono text-[11px] leading-4">
            {hall.open_diagnoses}
          </span>
        )}
      </div>

      {plan.tiles.length > 0 ? (
        <svg width={body.w} height={body.h} className="block" aria-hidden>
          {plan.lanes.map((lane) => (
            <g key={lane.line}>
              <rect x={lane.x} y={lane.y} width={lane.w} height={lane.h} fill="var(--secondary)" />
              {lane.h > 16 && lane.w > 40 && (
                <text x={lane.x + 4} y={lane.y + 11} fontSize={11} className="fill-muted-foreground font-mono uppercase">
                  {lane.line}
                </text>
              )}
            </g>
          ))}
          {plan.tiles.map((tile) => (
            <rect key={tile.id} x={tile.x} y={tile.y} width={tile.w} height={tile.h} fill="var(--card)" stroke="var(--line)" strokeWidth={1} />
          ))}
        </svg>
      ) : (
        <div className="p-2.5 text-[12px] leading-snug text-muted-foreground">
          <span className="font-mono text-[11px] uppercase tracking-[0.06em]">{HALL_KIND_LABELS[hall.kind]}</span>
          <p className="mt-1 line-clamp-4">{hall.description || "Noch keine Maschinen."}</p>
        </div>
      )}

      {Array.from({ length: hall.docks }, (_, i) => (
        <span
          key={i}
          title={`Tor ${i + 1}`}
          className="absolute -right-[7px] w-1.5 border border-line bg-card"
          style={{ top: HEADER_H + ((i + 0.5) * body.h) / hall.docks - 8, height: 16 }}
        />
      ))}
      <Handle type="source" position={Position.Right} className={HANDLE} />
    </div>
  );
}
