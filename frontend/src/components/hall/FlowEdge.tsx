"use client";

import { BaseEdge, EdgeLabelRenderer, getSmoothStepPath, type Edge, type EdgeProps } from "@xyflow/react";
import { X } from "lucide-react";

import { cn } from "@/lib/utils";

export type FlowEdgeData = {
  label: string;
  onRename: (label: string) => void;
  onRemove: () => void;
};
export type FlowEdgeType = Edge<FlowEdgeData, "flow">;

/** Materialfluss-Pfeil mit Beschriftung; Doppelklick benennt um, ausgewaehlt erscheint ✕. */
export function FlowEdge({ sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, markerEnd, selected, data }: EdgeProps<FlowEdgeType>) {
  const [path, labelX, labelY] = getSmoothStepPath({ sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, borderRadius: 0 });
  return (
    <>
      <BaseEdge path={path} markerEnd={markerEnd} style={{ stroke: "var(--primary)", strokeWidth: selected ? 3 : 2 }} />
      <EdgeLabelRenderer>
        <div
          className="nodrag nopan pointer-events-auto absolute flex items-center gap-1"
          style={{ transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)` }}
        >
          <button
            type="button"
            title="Doppelklick: Beschriftung ändern"
            onDoubleClick={() => {
              const label = window.prompt("Beschriftung des Materialflusses", data?.label ?? "");
              if (label !== null) data?.onRename(label.trim());
            }}
            className={cn(
              "border bg-card px-1.5 font-mono text-[11px]",
              selected ? "border-primary text-primary" : "border-line text-muted-foreground",
              !data?.label && !selected && "hidden",
            )}
          >
            {data?.label || "Beschriftung …"}
          </button>
          {selected && (
            <button type="button" aria-label="Materialfluss löschen" onClick={() => data?.onRemove()} className="grid size-5 place-items-center border border-line bg-card text-muted-foreground hover:text-danger">
              <X className="size-3" />
            </button>
          )}
        </div>
      </EdgeLabelRenderer>
    </>
  );
}
