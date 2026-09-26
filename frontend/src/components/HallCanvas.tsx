"use client";

import "@xyflow/react/dist/style.css";

import {
  Background,
  BackgroundVariant,
  Controls,
  MarkerType,
  MiniMap,
  Panel,
  ReactFlow,
  useEdgesState,
  useNodesState,
  type Connection,
  type EdgeTypes,
  type NodeTypes,
} from "@xyflow/react";
import { useCallback, useEffect, useMemo } from "react";

import { FlowEdge, type FlowEdgeType } from "@/components/hall/FlowEdge";
import { MachineNode, TILE_H, TILE_W, type MachineNodeType } from "@/components/hall/MachineNode";
import type { Flow, Machine } from "@/lib/api";

const GRID = 24;
const NODE_TYPES: NodeTypes = { machine: MachineNode };
const EDGE_TYPES: EdgeTypes = { flow: FlowEdge };

const sameFlow = (a: Flow, b: Flow) => a.from_machine_id === b.from_machine_id && a.to_machine_id === b.to_machine_id;

/**
 * Hallen-Baukasten auf React Flow: Maschinen als Kacheln (Raster 24 px), Materialfluss durch Ziehen
 * vom rechten Griff einer Kachel auf eine andere. Positionen werden nach dem Loslassen gespeichert.
 */
export function HallCanvas({
  machines,
  flows,
  onMoved,
  onFlowsChanged,
  selectedId,
  onSelect,
}: {
  machines: Machine[];
  flows: Flow[];
  onMoved: (id: string, x: number, y: number) => void;
  onFlowsChanged: (flows: Flow[]) => void;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
}) {
  const buildNodes = useCallback(
    (): MachineNodeType[] =>
      machines.map((machine) => ({
        id: machine.id,
        type: "machine",
        position: { x: machine.pos_x, y: machine.pos_y },
        width: TILE_W,
        height: TILE_H,
        data: { machine },
        selected: machine.id === selectedId,
      })),
    [machines, selectedId],
  );
  const [nodes, setNodes, onNodesChange] = useNodesState<MachineNodeType>(buildNodes());
  useEffect(() => setNodes(buildNodes()), [buildNodes, setNodes]);

  const flowEdges = useMemo<FlowEdgeType[]>(
    () =>
      flows.map((flow) => ({
        id: `${flow.from_machine_id}-${flow.to_machine_id}`,
        type: "flow",
        source: flow.from_machine_id,
        target: flow.to_machine_id,
        markerEnd: { type: MarkerType.ArrowClosed, color: "var(--primary)", width: 18, height: 18 },
        data: {
          label: flow.label,
          onRename: (label: string) => onFlowsChanged(flows.map((f) => (sameFlow(f, flow) ? { ...f, label } : f))),
          onRemove: () => onFlowsChanged(flows.filter((f) => !sameFlow(f, flow))),
        },
      })),
    [flows, onFlowsChanged],
  );
  // Kanten im Zustand halten, damit React Flow die Auswahl (fuer ✕ und Entf) speichern kann
  const [edges, setEdges, onEdgesChange] = useEdgesState<FlowEdgeType>(flowEdges);
  useEffect(() => setEdges(flowEdges), [flowEdges, setEdges]);

  function connect(connection: Connection) {
    const flow = { from_machine_id: connection.source, to_machine_id: connection.target, label: "" };
    if (flow.from_machine_id === flow.to_machine_id || flows.some((f) => sameFlow(f, flow))) return;
    onFlowsChanged([...flows, flow]);
  }

  return (
    <div className="relative size-full bg-card">
      <ReactFlow<MachineNodeType, FlowEdgeType>
        nodes={nodes}
        edges={edges}
        nodeTypes={NODE_TYPES}
        edgeTypes={EDGE_TYPES}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={(_, node) => onSelect(node.id)}
        onPaneClick={() => onSelect(null)}
        onNodeDragStop={(_, node) => onMoved(node.id, Math.max(0, node.position.x), Math.max(0, node.position.y))}
        onConnect={connect}
        onEdgesDelete={(deleted) => onFlowsChanged(flows.filter((f) => !deleted.some((e) => e.source === f.from_machine_id && e.target === f.to_machine_id)))}
        onBeforeDelete={async ({ nodes: doomed }) => doomed.length === 0}
        deleteKeyCode={["Delete", "Backspace"]}
        snapToGrid
        snapGrid={[GRID, GRID]}
        connectionLineStyle={{ stroke: "var(--primary)", strokeWidth: 2, strokeDasharray: "6 4" }}
        fitView
        fitViewOptions={{ padding: 0.2, maxZoom: 1.2 }}
        minZoom={0.3}
        maxZoom={2}
        proOptions={{ hideAttribution: true }}
      >
        <Background variant={BackgroundVariant.Lines} gap={GRID} color="var(--grid)" lineWidth={0.5} />
        <Background id="major" variant={BackgroundVariant.Lines} gap={GRID * 8} color="#cdd5df" lineWidth={1} />
        <Controls showInteractive={false} className="!rounded-none !shadow-none [&_button]:!border-border [&_button]:!bg-card" />
        <MiniMap
          pannable
          zoomable
          className="!rounded-none !border !border-line !bg-card max-md:!hidden"
          nodeColor={(node) => (node.id === selectedId ? "var(--primary)" : "#cdd5df")}
          maskColor="rgba(20, 38, 61, 0.08)"
        />
        <Panel position="top-left" className="!m-3 max-w-[calc(100%-1.5rem)] border border-line bg-card px-3 py-1.5 text-xs text-muted-foreground">
          <span className="md:hidden">Ziehen: anordnen · Griff → Kachel: Fluss</span>
          <span className="max-md:hidden">
            Kacheln ziehen zum Anordnen · Materialfluss: vom rechten Griff auf eine andere Kachel ziehen · Pfeil anklicken zum Löschen
          </span>
        </Panel>
      </ReactFlow>
      {machines.length === 0 && (
        <p className="pointer-events-none absolute left-6 top-16 max-w-md text-sm text-muted-foreground">
          Noch keine Maschinen. Rechts eine anlegen, dann hier anordnen und den Materialfluss zeichnen.
        </p>
      )}
    </div>
  );
}
