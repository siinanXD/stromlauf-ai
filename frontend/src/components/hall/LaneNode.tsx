"use client";

import type { Node, NodeProps } from "@xyflow/react";

export type LaneNodeType = Node<{ line: string }, "lane">;

/** Linien- bzw. Sektorband hinter den Kacheln; nicht anklickbar, folgt den Kacheln der Linie. */
export function LaneNode({ data }: NodeProps<LaneNodeType>) {
  return (
    <div className="size-full bg-secondary">
      <span className="block truncate px-2.5 pt-1 font-mono text-[11px] font-semibold uppercase tracking-[0.06em] text-muted-foreground">
        {data.line}
      </span>
    </div>
  );
}
