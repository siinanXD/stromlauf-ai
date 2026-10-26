"use client";

import "@xyflow/react/dist/style.css";

import { Handle, Position, ReactFlow, useReactFlow, type Node, type NodeProps, type NodeTypes } from "@xyflow/react";
import { useEffect, useMemo } from "react";

import type { RunStep } from "@/lib/api";
import { cn } from "@/lib/utils";

import { dauerText, flowOf, statusKlasse } from "./knoten";
import type { SchrittStatus } from "@/lib/api";

const NODE_W = 196;
const NODE_H = 88;
const ZEILE_Y = 66;

// Punkt in den kräftigen Tokens (>= 3:1 auf der Karte); der Zustand steht zusätzlich als Text im Knoten.
const PUNKT: Record<SchrittStatus, string> = {
  wartet: "bg-text-secondary",
  laeuft: "bg-accent-strong",
  fertig: "bg-ok-strong",
  fehler: "bg-error-strong",
};

type KnotenDaten = { step: RunStep; index: number; selected: boolean; onSelect: (step: RunStep) => void };

function SchrittKnoten({ data, positionAbsoluteX, positionAbsoluteY }: NodeProps<Node<KnotenDaten, "schritt">>) {
  const { step, selected, onSelect } = data;
  const { setCenter } = useReactFlow();
  const dauer = dauerText(step);
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
        onFocus={() => setCenter(positionAbsoluteX + NODE_W / 2, positionAbsoluteY + NODE_H / 2, { zoom: 1, duration: 150 })}
        className={cn(
          "nodrag nopan flex h-[88px] w-[196px] flex-col items-start gap-1 overflow-hidden rounded-md border-2 bg-card p-3 text-left",
          statusKlasse(step.status),
          selected && "ring-2 ring-ring",
        )}
      >
        <span className="flex w-full items-center gap-2">
          <span aria-hidden className={cn("size-2.5 shrink-0 rounded-full", PUNKT[step.status])} />
          <span className="truncate text-subhead font-semibold text-foreground">{step.label}</span>
        </span>
        <span className="w-full truncate text-footnote text-muted-foreground">{step.output || step.error || "–"}</span>
        <span className="font-mono text-caption-1 text-muted-foreground">{step.status}{dauer && ` · ${dauer}`}</span>
      </button>
      <Handle type="source" position={Position.Right} isConnectable={false} className="!opacity-0" />
    </>
  );
}

const NODE_TYPES: NodeTypes = { schritt: SchrittKnoten };

/** Der gewählte Schritt bleibt sichtbar, auch wenn das Panel die Breite verkleinert. */
function ZumGewaehlten({ steps, selected }: { steps: RunStep[]; selected: string | null }) {
  const { setCenter } = useReactFlow();
  useEffect(() => {
    const index = steps.findIndex((s) => s.key === selected);
    if (index < 0) return;
    const { nodes } = flowOf(steps);
    setCenter(nodes[index].position.x + NODE_W / 2, nodes[index].position.y + NODE_H / 2, { zoom: 1, duration: 150 });
    // nur bei Wechsel der Auswahl; steps ändern sich im Polling ständig
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected]);
  return null;
}

/** Die sieben Schritte eines Laufs als Reihe von Knoten; Klick oder Enter wählt einen Schritt. */
export function AblaufGraph({ steps, selected, onSelect }: { steps: RunStep[]; selected: string | null; onSelect: (step: RunStep) => void }) {
  const flow = useMemo(() => {
    const { nodes, edges } = flowOf(steps);
    return {
      nodes: nodes.map((node) => ({
        ...node,
        width: NODE_W,
        height: NODE_H,
        draggable: false,
        data: { ...node.data, selected: node.id === selected, onSelect },
      })),
      edges: edges.map((edge) => ({ ...edge, selectable: false, style: { stroke: "var(--color-line-strong)", strokeWidth: 1.5 } })),
    };
  }, [steps, selected, onSelect]);

  return (
    <div className="size-full bg-background" data-testid="ablauf-graph">
      <ReactFlow
        nodes={flow.nodes}
        edges={flow.edges}
        nodeTypes={NODE_TYPES}
        nodesDraggable={false}
        nodesConnectable={false}
        defaultViewport={{ x: 16, y: ZEILE_Y, zoom: 1 }}
        minZoom={1}
        maxZoom={1}
        nodesFocusable={false}
        zoomOnScroll={false}
        zoomOnPinch={false}
        zoomOnDoubleClick={false}
        preventScrolling={false}
        proOptions={{ hideAttribution: true }}
      >
        <ZumGewaehlten steps={steps} selected={selected} />
      </ReactFlow>
    </div>
  );
}
