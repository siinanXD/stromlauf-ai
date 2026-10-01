"use client";

import "@xyflow/react/dist/style.css";

import {
  Background,
  BackgroundVariant,
  BaseEdge,
  Controls,
  EdgeLabelRenderer,
  Handle,
  MarkerType,
  Panel,
  Position,
  ReactFlow,
  getSmoothStepPath,
  type Edge,
  type EdgeProps,
  type EdgeTypes,
  type Node,
  type NodeProps,
  type NodeTypes,
} from "@xyflow/react";
import { useMemo, useState } from "react";

import type { SignalMainData, SignalMainNode } from "@/lib/api";
import { cn } from "@/lib/utils";

import { PROVENANCE_CAP, PROVENANCE_DASH, edgeText, onlyProven, provenanceOf, type Provenance } from "./provenance";
import { SignalLegend } from "./SignalLegend";
import { COLUMN_LABELS, KIND_LABELS, nodeTitle, orderInColumns, visibleColumns, type GridPosition } from "./signalColumns";

const COL_W = 236;
const ROW_H = 92;
const NODE_W = 192;
const NODE_H = 64;
const HEADER_Y = -52;

type SignalNodeData = { node: SignalMainNode; start: boolean; selected: boolean };
type HeaderNodeData = { label: string };
type SignalFlowNode = Node<SignalNodeData, "signal">;
type HeaderFlowNode = Node<HeaderNodeData, "header">;
type ProvenanceEdgeData = { provenance: Provenance; from: string | null; to: string | null };
type ProvenanceFlowEdge = Edge<ProvenanceEdgeData, "provenance">;

const SIDES = [
  ["l", Position.Left],
  ["r", Position.Right],
  ["t", Position.Top],
  ["b", Position.Bottom],
] as const;

/** Je Seite ein Ein- und ein Ausgang; die Kante waehlt die Seiten nach der Lage der Knoten im Raster. */
function Handles() {
  return (
    <>
      {SIDES.flatMap(([side, position]) => [
        <Handle key={`${side}-t`} id={`${side}-t`} type="target" position={position} className="!opacity-0" isConnectable={false} />,
        <Handle key={`${side}-s`} id={`${side}-s`} type="source" position={position} className="!opacity-0" isConnectable={false} />,
      ])}
    </>
  );
}

function handlesFor(source: GridPosition, target: GridPosition): [string, string] {
  if (source.x < target.x) return ["r-s", "l-t"];
  if (source.x > target.x) return ["l-s", "r-t"];
  return source.y <= target.y ? ["b-s", "t-t"] : ["t-s", "b-t"];
}

function SignalNodeView({ data }: NodeProps<SignalFlowNode>) {
  const { node, start, selected } = data;
  return (
    <div
      className={cn(
        "flex h-full cursor-pointer flex-col justify-center border px-2.5 py-1.5",
        selected ? "border-2 border-primary bg-primary-soft" : node.main ? "border-line bg-card" : "border-border bg-secondary",
      )}
      title={[KIND_LABELS[node.kind], node.label, node.ref].filter(Boolean).join(" · ")}
    >
      <Handles />
      <div className="flex items-baseline justify-between gap-2">
        <span className={cn("truncate font-mono text-[13px] font-semibold", node.main ? "text-foreground" : "text-muted-foreground")}>
          {nodeTitle(node)}
        </span>
        {start ? (
          <span className="font-mono text-[10px] uppercase text-primary">Start</span>
        ) : (
          node.branches > 0 && (
            <span className="font-mono text-[10px] text-muted-foreground" title={`${node.branches} Abzweige`}>
              +{node.branches}
            </span>
          )
        )}
      </div>
      <div className="truncate text-[11px] text-muted-foreground">{node.label || KIND_LABELS[node.kind]}</div>
      {node.ref && node.kind !== "network" && <div className="truncate font-mono text-[10px] text-muted-foreground">{node.ref}</div>}
    </div>
  );
}

function HeaderNodeView({ data }: NodeProps<HeaderFlowNode>) {
  return (
    <div className="w-full border-b-2 border-line pb-1 font-mono text-[11px] font-semibold uppercase tracking-[0.06em] text-muted-foreground">
      {data.label}
    </div>
  );
}

/** Anschlussnummer am Kantenende, neben dem Griff und nach aussen versetzt. */
function PinLabel({ x, y, position, text }: { x: number; y: number; position: Position; text: string }) {
  const shift = {
    [Position.Right]: "translate(4px, -100%)",
    [Position.Left]: "translate(calc(-100% - 4px), -100%)",
    [Position.Top]: "translate(4px, calc(-100% - 2px))",
    [Position.Bottom]: "translate(4px, 2px)",
  }[position];
  return (
    <div
      className="nodrag nopan pointer-events-none absolute border border-line bg-card px-1 font-mono text-[10px] leading-4 text-foreground"
      style={{ transform: `translate(${x}px, ${y}px) ${shift}` }}
    >
      {text}
    </div>
  );
}

/** Kante mit Strichart nach Herkunft und den Anschlussnummern an ihren Enden. */
function ProvenanceEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
  markerEnd,
  style,
}: EdgeProps<ProvenanceFlowEdge>) {
  const [path] = getSmoothStepPath({ sourceX, sourceY, sourcePosition, targetX, targetY, targetPosition, borderRadius: 6 });
  const provenance = data?.provenance ?? "lage";
  return (
    <>
      <BaseEdge
        id={id}
        path={path}
        markerEnd={markerEnd}
        style={{ ...style, strokeDasharray: PROVENANCE_DASH[provenance], strokeLinecap: PROVENANCE_CAP[provenance] }}
      />
      {(data?.from || data?.to) && (
        <EdgeLabelRenderer>
          {data.from && <PinLabel x={sourceX} y={sourceY} position={sourcePosition} text={data.from} />}
          {data.to && <PinLabel x={targetX} y={targetY} position={targetPosition} text={data.to} />}
        </EdgeLabelRenderer>
      )}
    </>
  );
}

const NODE_TYPES: NodeTypes = { signal: SignalNodeView, header: HeaderNodeView };
const EDGE_TYPES: EdgeTypes = { provenance: ProvenanceEdge };

/** Knoten und Kanten fuer xyflow: Lage aus allen Daten, damit "nur Belegtes" nichts verschiebt. */
function flowElements(all: SignalMainData, shown: SignalMainData, selected: string | null) {
  const grid = orderInColumns(all);
  const columns = visibleColumns(all);
  const headers: HeaderFlowNode[] = columns.map((column, index) => ({
    id: `header:${column}`,
    type: "header",
    position: { x: index * COL_W, y: HEADER_Y },
    width: NODE_W,
    data: { label: COLUMN_LABELS[column] },
    draggable: false,
    selectable: false,
    focusable: false,
  }));
  const nodes: SignalFlowNode[] = shown.nodes.flatMap((node) => {
    const at = grid.get(node.id);
    if (!at) return [];
    return [
      {
        id: node.id,
        type: "signal" as const,
        position: { x: at.x * COL_W, y: at.y * ROW_H },
        width: NODE_W,
        height: NODE_H,
        data: { node, start: node.id === all.start, selected: node.id === selected },
        draggable: false,
        ariaLabel: `${nodeTitle(node)}, ${node.label || KIND_LABELS[node.kind]}`,
      },
    ];
  });
  const main = new Set(all.nodes.filter((node) => node.main).map((node) => node.id));
  const edges: ProvenanceFlowEdge[] = shown.edges.flatMap((edge, index) => {
    const from = grid.get(edge.source);
    const to = grid.get(edge.target);
    if (!from || !to) return [];
    const [sourceHandle, targetHandle] = handlesFor(from, to);
    const onMain = main.has(edge.source) && main.has(edge.target);
    const color = onMain ? "var(--foreground)" : "var(--muted-foreground)";
    return [
      {
        id: `${index}:${edge.source}->${edge.target}`,
        type: "provenance" as const,
        source: edge.source,
        target: edge.target,
        sourceHandle,
        targetHandle,
        data: { provenance: provenanceOf(edge.via), from: edge.pins?.from ?? null, to: edge.pins?.to ?? null },
        style: { stroke: color, strokeWidth: onMain ? 1.75 : 1.25 },
        markerEnd: edge.directed ? { type: MarkerType.ArrowClosed, color, width: 14, height: 14 } : undefined,
        ariaLabel: `${edge.source} nach ${edge.target}: ${edgeText(edge)}${edge.directed ? "" : ", Richtung offen"}`,
        selectable: false,
      },
    ];
  });
  return { nodes: [...headers, ...nodes] as Node[], edges };
}

/**
 * Signalweg als Grafik in festen Spalten (Feld bis Verbraucher). Strichart zeigt die Herkunft, Anschluesse stehen an
 * den Kantenenden. Ein Klick waehlt einen Knoten; was dann passiert (Planseite, Bauteil, weiter verfolgen),
 * entscheidet die Ansicht darum.
 */
export function SignalGraph({
  data,
  selected,
  onSelect,
}: {
  data: SignalMainData;
  selected: string | null;
  onSelect: (node: SignalMainNode) => void;
}) {
  const [proven, setProven] = useState(false);
  const shown = useMemo(() => (proven ? onlyProven(data) : data), [data, proven]);
  const flow = useMemo(() => flowElements(data, shown, selected), [data, shown, selected]);

  return (
    <div className="relative size-full">
      <ReactFlow
        key={data.start}
        nodes={flow.nodes}
        edges={flow.edges}
        nodeTypes={NODE_TYPES}
        edgeTypes={EDGE_TYPES}
        onNodeClick={(_, node) => {
          if (node.type === "signal") onSelect((node.data as SignalNodeData).node);
        }}
        nodesConnectable={false}
        nodesDraggable={false}
        fitView
        fitViewOptions={{ padding: 0.12 }}
        minZoom={0.2}
        proOptions={{ hideAttribution: true }}
      >
        <Background variant={BackgroundVariant.Lines} gap={24} color="var(--grid)" lineWidth={0.5} />
        <Controls position="bottom-right" showInteractive={false} className="!rounded-none !shadow-none [&_button]:!border-border [&_button]:!bg-card" />
        <Panel position="bottom-left" className="!m-2">
          <SignalLegend onlyProven={proven} onOnlyProvenChange={setProven} />
        </Panel>
      </ReactFlow>
    </div>
  );
}
