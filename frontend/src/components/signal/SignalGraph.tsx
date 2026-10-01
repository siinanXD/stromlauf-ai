"use client";

import "@xyflow/react/dist/style.css";

import {
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
import { Switch } from "./SignalLegend";
import { COLUMN_LABELS, KIND_LABELS, nodeTitle, orderInColumns, sheetShort, visibleColumns, type GridPosition } from "./signalColumns";

// Figma "Desktop · Signalweg Vollbild": Karten 158 px breit, 38 px Verbindung dazwischen
const COL_W = 196;
const ROW_H = 140;
const NODE_W = 158;
const NODE_H = 116;
const HEADER_Y = -26;

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

/**
 * Karte eines Knotens: Kennzeichen, Klartext, Blatt, Abzweige. Start blau-hell mit blauem Kennzeichen, gewaehlt mit
 * blauem Rahmen (beides wie in Figma); "Start" und "gewählt" stehen zusaetzlich im Namen fuer Screenreader.
 */
function SignalNodeView({ data }: NodeProps<SignalFlowNode>) {
  const { node, start, selected } = data;
  const sheet = node.kind === "network" ? "AWL" : sheetShort(node.ref);
  return (
    <div
      className={cn(
        "flex h-full cursor-pointer flex-col gap-1 overflow-hidden rounded-[14px] border-2 p-3 shadow-card",
        start ? "bg-primary-soft" : node.main ? "bg-card" : "bg-bg-grouped shadow-none",
        selected ? "border-accent" : node.main ? "border-transparent" : "border-dashed border-line",
      )}
      title={[KIND_LABELS[node.kind], node.label, node.ref].filter(Boolean).join(" · ")}
    >
      <Handles />
      <span className={cn("truncate font-mono text-tag font-medium", start ? "text-primary" : node.main ? "text-foreground" : "text-muted-foreground")}>{nodeTitle(node)}</span>
      <span className="line-clamp-2 text-footnote text-muted-foreground">{node.label || KIND_LABELS[node.kind]}</span>
      {sheet && <span className="truncate text-caption-1 text-primary">{sheet}</span>}
      {!start && node.branches > 0 && (
        <span className="w-fit rounded-full bg-bg-fill px-2 py-0.5 text-caption-2 text-muted-foreground">
          +{node.branches} {node.branches === 1 ? "Abzweig" : "Abzweige"}
        </span>
      )}
    </div>
  );
}

function HeaderNodeView({ data }: NodeProps<HeaderFlowNode>) {
  return <div className="w-full text-caption-2 text-muted-foreground uppercase">{data.label}</div>;
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
      className="nodrag nopan pointer-events-none absolute rounded-xs bg-background/85 px-0.5 font-mono text-tag-sm font-medium text-primary"
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
        ariaLabel: [nodeTitle(node), node.label || KIND_LABELS[node.kind], node.id === all.start ? "Start" : null, node.id === selected ? "gewählt" : null]
          .filter(Boolean)
          .join(", "),
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
    const color = onMain ? "var(--color-text-secondary)" : "var(--color-line-strong)";
    return [
      {
        id: `${index}:${edge.source}->${edge.target}`,
        type: "provenance" as const,
        source: edge.source,
        target: edge.target,
        sourceHandle,
        targetHandle,
        data: { provenance: provenanceOf(edge.via), from: edge.pins?.from ?? null, to: edge.pins?.to ?? null },
        style: { stroke: color, strokeWidth: onMain ? 2 : 1.5 },
        markerEnd: edge.directed ? { type: MarkerType.ArrowClosed, color, width: 12, height: 12 } : undefined,
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
    <div className="relative size-full bg-background">
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
        fitViewOptions={{ padding: 0.1, maxZoom: 1 }}
        minZoom={0.2}
        proOptions={{ hideAttribution: true }}
      >
        <Controls
          position="bottom-right"
          showInteractive={false}
          className="!overflow-hidden !rounded-md !shadow-card [&_button]:!size-11 [&_button]:!border-border [&_button]:!bg-card [&_button_svg]:!fill-foreground"
        />
        <Panel position="bottom-left" className="!m-3">
          <div className="rounded-md bg-card px-3 shadow-card">
            <Switch checked={proven} onChange={setProven} label="Nur Belegtes zeigen" className="gap-4 text-subhead" />
          </div>
        </Panel>
      </ReactFlow>
    </div>
  );
}
