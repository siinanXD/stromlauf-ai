"use client";

import { BaseEdge, useInternalNode, type Edge, type EdgeProps, type InternalNode } from "@xyflow/react";

import { FlowLabel, type FlowEdgeData } from "@/components/hall/FlowEdge";
import { borderPoint, type Rect } from "@/lib/site";

export type SiteFlowEdgeType = Edge<FlowEdgeData, "siteFlow">;

function centerBox(node: InternalNode): Rect {
  const w = node.measured.width ?? node.width ?? 0;
  const h = node.measured.height ?? node.height ?? 0;
  return { x: node.internals.positionAbsolute.x + w / 2, y: node.internals.positionAbsolute.y + h / 2, w, h };
}

/** Materialfluss zwischen Hallen: gerader Pfeil von Wand zu Wand, egal wie die Hallen liegen. */
export function SiteFlowEdge({ source, target, markerEnd, selected, data }: EdgeProps<SiteFlowEdgeType>) {
  const from = useInternalNode(source);
  const to = useInternalNode(target);
  if (!from || !to) return null;
  const a = centerBox(from);
  const b = centerBox(to);
  const start = borderPoint(a, b);
  const end = borderPoint(b, a);
  return (
    <>
      <BaseEdge
        path={`M ${start.x} ${start.y} L ${end.x} ${end.y}`}
        markerEnd={markerEnd}
        style={{ stroke: "var(--primary)", strokeWidth: selected ? 3 : 2 }}
      />
      <FlowLabel x={(start.x + end.x) / 2} y={(start.y + end.y) / 2} selected={!!selected} data={data} />
    </>
  );
}
