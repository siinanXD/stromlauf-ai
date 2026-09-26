"use client";

import { NodeResizer, type NodeProps } from "@xyflow/react";

import { cn } from "@/lib/utils";

import type { FloorNode, PartNode as PartNodeType } from "./geometry";

const SMALL_PX = 40; // darunter steht die Beschriftung neben dem Teil

export function PartNode({ data, selected, width = 0, height = 0 }: NodeProps<PartNodeType>) {
  const { part, onResizeEnd } = data;
  const circle = part.shape === "circle";
  const emergency = part.kind === "Not-Halt";
  const belt = part.kind === "Band/Förderer";
  const proposal = !part.confirmed;
  const frame = part.kind === "Rahmen";
  const small = Math.min(width, height) < SMALL_PX;
  const title = part.tag || part.label || part.kind;

  return (
    <>
      <NodeResizer
        isVisible={selected}
        minWidth={4}
        minHeight={4}
        color="var(--primary)"
        handleClassName="!size-2 !rounded-none !border-primary !bg-card"
        lineClassName="!border-primary"
        onResizeEnd={(_, params) => onResizeEnd?.(part.id, params)}
      />
      <div
        className={cn(
          "relative size-full border-[1.5px] border-line bg-card",
          circle && "rounded-full",
          belt && "bg-[repeating-linear-gradient(90deg,transparent_0,transparent_11px,rgba(20,38,61,0.25)_11px,rgba(20,38,61,0.25)_12px)] bg-accent",
          part.kind === "Rahmen" && "bg-transparent",
          emergency && "border-[#8f1424] bg-danger",
          proposal && "border-dashed border-primary bg-primary/5",
          selected && "border-2 border-primary",
          selected && !emergency && !belt && "bg-primary/10",
        )}
        style={{ transform: part.rotation_deg ? `rotate(${part.rotation_deg}deg)` : undefined }}
        title={[part.tag, part.label, part.kind].filter(Boolean).join(" · ")}
      >
        {frame && (
          <div className="pointer-events-none absolute left-0 top-full mt-1 whitespace-nowrap text-[11px] text-muted-foreground">
            {part.label || part.tag || part.kind}
          </div>
        )}
        {!small && !frame && (
          <div className="pointer-events-none absolute left-1.5 top-1 max-w-[calc(100%-0.5rem)] leading-tight">
            <div className={cn("truncate font-mono text-[13px] font-semibold", selected || proposal ? "text-primary" : "text-foreground")}>
              {proposal && part.tag ? `${title} ?` : title}
            </div>
            {part.tag && part.label && !belt && <div className="truncate text-[10px] text-muted-foreground">{part.label}</div>}
            {proposal && (
              <div className="text-[10px] text-muted-foreground">
                Vorschlag{part.confidence != null ? ` · ${Math.round(part.confidence * 100)} %` : ""}
              </div>
            )}
          </div>
        )}
      </div>
      {small && !frame && (
        <div
          className={cn(
            "pointer-events-none absolute left-full top-1/2 ml-1.5 -translate-y-1/2 whitespace-nowrap font-mono text-[12px]",
            selected || proposal ? "font-semibold text-primary" : "text-foreground",
            circle && "left-1/2 top-auto bottom-full mb-1 ml-0 -translate-x-1/2 translate-y-0",
          )}
        >
          {proposal ? `${title} ?` : title}
        </div>
      )}
    </>
  );
}

/** Grundflaeche der Maschine: gestrichelter Rahmen, darunter liegt das Raster. */
export function FloorNodeView({ data }: NodeProps<FloorNode>) {
  return (
    <div className="pointer-events-none size-full border border-dashed border-muted-foreground/70">
      {!data.width_mm && (
        <span className="absolute left-2 top-2 text-xs text-muted-foreground">Masse unbekannt – im Panel eintragen</span>
      )}
    </div>
  );
}
