"use client";

import "@xyflow/react/dist/style.css";

import { Handle, Position, ReactFlow, type Node, type NodeProps, type NodeTypes } from "@xyflow/react";
import { useMemo } from "react";

import type { RunStep } from "@/lib/api";
import { cn } from "@/lib/utils";

import { dauerText, flowOf, statusKlasse } from "./knoten";

type KnotenDaten = { step: RunStep; index: number; selected: boolean; onSelect: (step: RunStep) => void };

function SchrittKnoten({ data }: NodeProps<Node<KnotenDaten, "schritt">>) {
  const { step, selected, onSelect } = data;
  return (
    <>
      <Handle type="target" position={Position.Left} isConnectable={false} className="!opacity-0" />
      <button
        type="button"
        data-testid={`schritt-${step.key}`}
        data-status={step.status}
        aria-label={`${step.label}: ${step.status}`}
        aria-pressed={selected}
        onClick={() => onSelect(step)}
        className={cn(
          "nodrag nopan flex h-[88px] w-[196px] flex-col items-start gap-1 overflow-hidden rounded-md border-2 bg-card p-3 text-left",
          statusKlasse(step.status),
          selected && "ring-2 ring-ring",
        )}
      >
        <span className="flex w-full items-center gap-2">
          <span aria-hidden className="size-2 shrink-0 rounded-full bg-current" />
          <span className="truncate text-subhead font-semibold text-foreground">{step.label}</span>
        </span>
        <span className="w-full truncate text-footnote text-muted-foreground">{step.output || step.error || "–"}</span>
        <span className="font-mono text-caption-1 text-muted-foreground">{dauerText(step) || " "}</span>
      </button>
      <Handle type="source" position={Position.Right} isConnectable={false} className="!opacity-0" />
    </>
  );
}

const NODE_TYPES: NodeTypes = { schritt: SchrittKnoten };

/** Die sieben Schritte eines Laufs als Reihe von Knoten; Klick oder Enter wählt einen Schritt. */
export function AblaufGraph({ steps, selected, onSelect }: { steps: RunStep[]; selected: string | null; onSelect: (step: RunStep) => void }) {
  const flow = useMemo(() => {
    const { nodes, edges } = flowOf(steps);
    return {
      nodes: nodes.map((node) => ({
        ...node,
        width: 196,
        height: 88,
        draggable: false,
        data: { ...node.data, selected: node.id === selected, onSelect },
      })),
      edges: edges.map((edge) => ({ ...edge, selectable: false, style: { stroke: "var(--color-line-strong)", strokeWidth: 1.5 } })),
    };
  }, [steps, selected, onSelect]);

  return (
    <div className="size-full bg-background" data-testid="ablauf-graph">
      <ReactFlow
        key={selected === null ? "ohne-panel" : "mit-panel"}
        nodes={flow.nodes}
        edges={flow.edges}
        nodeTypes={NODE_TYPES}
        nodesDraggable={false}
        nodesConnectable={false}
        fitView
        fitViewOptions={{ padding: 0.1, maxZoom: 1 }}
        minZoom={0.2}
        proOptions={{ hideAttribution: true }}
      />
    </div>
  );
}
