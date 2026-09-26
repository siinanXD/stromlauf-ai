"use client";

import "@xyflow/react/dist/style.css";

import {
  Background,
  BackgroundVariant,
  Controls,
  MarkerType,
  Panel,
  ReactFlow,
  useEdgesState,
  useNodesState,
  type Connection,
  type EdgeTypes,
  type NodeTypes,
} from "@xyflow/react";
import { useCallback, useEffect, useMemo } from "react";

import { HallBlockNode, type HallBlockType } from "@/components/site/HallBlockNode";
import { SiteFlowEdge, type SiteFlowEdgeType } from "@/components/site/SiteFlowEdge";
import type { SiteData, SiteFlow } from "@/lib/api";
import type { Rect } from "@/lib/site";

const GRID = 20;
const NODE_TYPES: NodeTypes = { hall: HallBlockNode };
const EDGE_TYPES: EdgeTypes = { siteFlow: SiteFlowEdge };

const sameFlow = (a: SiteFlow, b: SiteFlow) => a.from_hall_id === b.from_hall_id && a.to_hall_id === b.to_hall_id;

/**
 * Standortplan auf React Flow: Hallen als Grundriss-Bloecke (ziehen, Groesse aendern), Materialfluss
 * zwischen Hallen durch Ziehen vom rechten Griff auf eine andere Halle.
 */
export function SiteCanvas({
  site,
  selectedId,
  onSelect,
  onRect,
  onFlowsChanged,
}: {
  site: SiteData;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  onRect: (id: string, rect: Rect) => void;
  onFlowsChanged: (flows: SiteFlow[]) => void;
}) {
  const buildNodes = useCallback(
    (): HallBlockType[] =>
      site.halls.map((hall) => ({
        id: hall.id,
        type: "hall",
        position: { x: hall.x, y: hall.y },
        width: hall.w,
        height: hall.h,
        data: { hall, onResized: (rect: Rect) => onRect(hall.id, rect) },
        selected: hall.id === selectedId,
      })),
    [site.halls, selectedId, onRect],
  );
  const [nodes, setNodes, onNodesChange] = useNodesState<HallBlockType>(buildNodes());
  useEffect(() => setNodes(buildNodes()), [buildNodes, setNodes]);

  const flowEdges = useMemo<SiteFlowEdgeType[]>(
    () =>
      site.flows.map((flow) => ({
        id: `${flow.from_hall_id}-${flow.to_hall_id}`,
        type: "siteFlow",
        source: flow.from_hall_id,
        target: flow.to_hall_id,
        markerEnd: { type: MarkerType.ArrowClosed, color: "var(--primary)", width: 18, height: 18 },
        data: {
          label: flow.label,
          onRename: (label: string) => onFlowsChanged(site.flows.map((f) => (sameFlow(f, flow) ? { ...f, label } : f))),
          onRemove: () => onFlowsChanged(site.flows.filter((f) => !sameFlow(f, flow))),
        },
      })),
    [site.flows, onFlowsChanged],
  );
  const [edges, setEdges, onEdgesChange] = useEdgesState<SiteFlowEdgeType>(flowEdges);
  useEffect(() => setEdges(flowEdges), [flowEdges, setEdges]);

  function connect(connection: Connection) {
    const flow = { from_hall_id: connection.source, to_hall_id: connection.target, label: "" };
    if (flow.from_hall_id === flow.to_hall_id || site.flows.some((f) => sameFlow(f, flow))) return;
    onFlowsChanged([...site.flows, flow]);
  }

  const machines = site.halls.reduce((sum, hall) => sum + hall.machine_count, 0);

  return (
    <div className="relative size-full bg-card">
      <ReactFlow<HallBlockType, SiteFlowEdgeType>
        nodes={nodes}
        edges={edges}
        nodeTypes={NODE_TYPES}
        edgeTypes={EDGE_TYPES}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={(_, node) => onSelect(node.id)}
        onPaneClick={() => onSelect(null)}
        onNodeDragStop={(_, grabbed, dragged) => {
          dragged.forEach((node) =>
            onRect(node.id, { x: node.position.x, y: node.position.y, w: node.width ?? node.data.hall.w, h: node.height ?? node.data.hall.h }),
          );
          // Auswahl erst nach dem Loslassen: ein Panelwechsel waehrend des Ziehens verschiebt die Flaeche
          onSelect(grabbed.id);
        }}
        onConnect={connect}
        onEdgesDelete={(deleted) => onFlowsChanged(site.flows.filter((f) => !deleted.some((e) => e.source === f.from_hall_id && e.target === f.to_hall_id)))}
        onBeforeDelete={async ({ nodes: doomed }) => doomed.length === 0}
        deleteKeyCode={["Delete", "Backspace"]}
        selectionKeyCode={null}
        multiSelectionKeyCode={null}
        snapToGrid
        snapGrid={[GRID, GRID]}
        connectionLineStyle={{ stroke: "var(--primary)", strokeWidth: 2, strokeDasharray: "6 4" }}
        fitView
        fitViewOptions={{ padding: 0.08 }}
        minZoom={0.1}
        maxZoom={1.5}
        proOptions={{ hideAttribution: true }}
      >
        <Background variant={BackgroundVariant.Lines} gap={GRID} color="var(--grid)" lineWidth={0.5} />
        <Background id="major" variant={BackgroundVariant.Lines} gap={GRID * 10} color="#cdd5df" lineWidth={1} />
        <Controls showInteractive={false} className="!rounded-none !shadow-none [&_button]:!border-border [&_button]:!bg-card" />
        <Panel position="bottom-right" className="!m-3 max-md:!hidden">
          <div className="grid w-72 grid-cols-[auto_1fr] border-[1.5px] border-line bg-card font-mono text-[11px]">
            <div className="border-b border-r border-line px-2 py-1 text-muted-foreground">BLATT</div>
            <div className="border-b border-line px-2 py-1 text-[13px] font-semibold">WERK</div>
            <div className="border-r border-line px-2 py-1 font-semibold">STANDORT</div>
            <div className="px-2 py-1 text-muted-foreground">
              {site.halls.length} Hallen · {machines} Maschinen
            </div>
          </div>
        </Panel>
      </ReactFlow>
      {site.halls.length === 0 && (
        <p className="pointer-events-none absolute left-6 top-6 max-w-md text-sm text-muted-foreground">
          Noch keine Hallen. Oben eine anlegen, dann hier anordnen und den Materialfluss zwischen den Hallen ziehen.
        </p>
      )}
    </div>
  );
}
