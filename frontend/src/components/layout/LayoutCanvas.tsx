"use client";

import "@xyflow/react/dist/style.css";

import {
  Background,
  BackgroundVariant,
  Controls,
  Panel,
  ReactFlow,
  ReactFlowProvider,
  useNodesState,
  useReactFlow,
  type NodeTypes,
  type OnBeforeDelete,
} from "@xyflow/react";
import { Circle, Download, ImageIcon, MousePointer2, Square } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { layout as layoutApi, type Layout, type LayoutPart } from "@/lib/api";
import { cn } from "@/lib/utils";

import {
  FLOOR_ID,
  GRID_MAJOR_MM,
  GRID_MINOR_MM,
  NEW_PART_MM,
  floorNode,
  mm,
  nodeToPatch,
  partToNode,
  px,
  type CanvasNode,
  type ResizeBox,
} from "./geometry";
import { FloorNodeView, PartNode } from "./PartNode";
import { TitleBlock } from "./TitleBlock";

type Tool = "select" | "rect" | "circle";

const NODE_TYPES: NodeTypes = { part: PartNode, floor: FloorNodeView };

export interface LayoutCanvasProps {
  layout: Layout;
  machineName: string;
  selectedId: string | null;
  onSelect: (part: LayoutPart | null) => void;
  onChanged: () => void;
}

export function LayoutCanvas(props: LayoutCanvasProps) {
  return (
    <ReactFlowProvider>
      <Canvas {...props} />
    </ReactFlowProvider>
  );
}

function Canvas({ layout, machineName, selectedId, onSelect, onChanged }: LayoutCanvasProps) {
  const { screenToFlowPosition, fitView } = useReactFlow();
  const [tool, setTool] = useState<Tool>("select");
  const [showSketch, setShowSketch] = useState(false);
  const [reviewOpen, setReviewOpen] = useState(false);

  const saveBox = useCallback(
    (partId: string, box: ResizeBox) => {
      layoutApi
        .updatePart(partId, nodeToPatch({ position: { x: box.x, y: box.y }, width: box.width, height: box.height }))
        .catch((err: Error) => toast.error(`Speichern fehlgeschlagen: ${err.message}`))
        .finally(onChanged);
    },
    [onChanged],
  );

  const buildNodes = useCallback(
    (): CanvasNode[] => [floorNode(layout), ...layout.parts.map((p) => partToNode(p, p.id === selectedId, saveBox))],
    [layout, selectedId, saveBox],
  );
  const [nodes, setNodes, onNodesChange] = useNodesState<CanvasNode>(buildNodes());
  useEffect(() => setNodes(buildNodes()), [buildNodes, setNodes]);

  // Beim Wechsel der Draufsicht (oder erstem Laden) die ganze Grundflaeche einpassen
  useEffect(() => {
    const timer = window.setTimeout(() => fitView({ padding: 0.12 }), 60);
    return () => window.clearTimeout(timer);
  }, [layout.id, layout.width_mm, layout.depth_mm, fitView]);

  const proposals = useMemo(() => layout.parts.filter((p) => !p.confirmed), [layout.parts]);

  const onBeforeDelete: OnBeforeDelete<CanvasNode> = async ({ nodes: doomed }) => {
    const parts = doomed.filter((n) => n.id !== FLOOR_ID);
    if (!parts.length) return false;
    const names = parts.map((n) => (n.type === "part" ? n.data.part.tag || n.data.part.kind : "")).join(", ");
    if (!confirm(`${names} aus der Draufsicht löschen?`)) return false;
    await Promise.all(parts.map((n) => layoutApi.deletePart(n.id))).catch((err: Error) => toast.error(err.message));
    onSelect(null);
    onChanged();
    return false; // Neu laden uebernimmt die Anzeige
  };

  async function addPart(event: React.MouseEvent) {
    const point = screenToFlowPosition({ x: event.clientX, y: event.clientY });
    const circle = tool === "circle";
    setTool("select");
    try {
      const part = await layoutApi.createPart(layout.id, {
        kind: "Sonstiges",
        shape: circle ? "circle" : "rect",
        x_mm: Math.max(0, mm(point.x) - NEW_PART_MM / 2),
        y_mm: Math.max(0, mm(point.y) - NEW_PART_MM / 2),
        w_mm: NEW_PART_MM,
        h_mm: NEW_PART_MM,
      });
      onSelect(part);
      onChanged();
    } catch (err) {
      toast.error(`Teil anlegen fehlgeschlagen: ${(err as Error).message}`);
    }
  }

  async function review(part: LayoutPart, accept: boolean) {
    try {
      if (accept) await layoutApi.updatePart(part.id, { confirmed: true });
      else await layoutApi.deletePart(part.id);
    } catch (err) {
      toast.error((err as Error).message);
    }
    onChanged();
  }

  async function acceptAll() {
    await Promise.all(proposals.map((p) => layoutApi.updatePart(p.id, { confirmed: true }))).catch((err: Error) =>
      toast.error(err.message),
    );
    setReviewOpen(false);
    onChanged();
  }

  const gapMinor = px(GRID_MINOR_MM);
  const gapMajor = px(GRID_MAJOR_MM);

  return (
    <div className={cn("relative size-full bg-card", tool !== "select" && "[&_.react-flow__pane]:!cursor-crosshair")}>
      <ReactFlow<CanvasNode>
        nodes={nodes}
        nodeTypes={NODE_TYPES}
        onNodesChange={onNodesChange}
        onNodeClick={(_, node) => node.type === "part" && onSelect(node.data.part)}
        onPaneClick={(event) => (tool === "select" ? onSelect(null) : addPart(event))}
        onNodeDragStop={(_, node) => {
          if (node.id === FLOOR_ID) return;
          layoutApi
            .updatePart(node.id, nodeToPatch(node))
            .catch((err: Error) => toast.error(`Speichern fehlgeschlagen: ${err.message}`))
            .finally(onChanged);
        }}
        onBeforeDelete={onBeforeDelete}
        deleteKeyCode={["Delete", "Backspace"]}
        nodesConnectable={false}
        fitView
        fitViewOptions={{ padding: 0.12 }}
        minZoom={0.2}
        maxZoom={6}
        proOptions={{ hideAttribution: true }}
      >
        <Background id="minor" variant={BackgroundVariant.Lines} gap={gapMinor} color="var(--grid)" lineWidth={0.5} />
        <Background id="major" variant={BackgroundVariant.Lines} gap={gapMajor} color="#cdd5df" lineWidth={1} />
        <Controls showInteractive={false} className="!rounded-none !shadow-none [&_button]:!border-border [&_button]:!bg-card" />

        <Panel position="top-left" className="!m-3 flex gap-1.5">
          {(
            [
              ["select", "Auswahl", MousePointer2],
              ["rect", "Rechteck", Square],
              ["circle", "Kreis", Circle],
            ] as const
          ).map(([id, label, Icon]) => (
            <Button
              key={id}
              size="sm"
              variant={tool === id ? "default" : "outline"}
              className={cn(tool !== id && "bg-card")}
              onClick={() => setTool(id)}
            >
              <Icon className="size-3.5" />
              {label}
            </Button>
          ))}
          {layout.has_image && (
            <Button size="sm" variant={showSketch ? "default" : "outline"} className={cn(!showSketch && "bg-card")} onClick={() => setShowSketch((v) => !v)}>
              <ImageIcon className="size-3.5" />
              Skizze
            </Button>
          )}
          <Button size="sm" variant="outline" className="bg-card" asChild>
            <a href={layoutApi.exportUrl(layout.id)} download>
              <Download className="size-3.5" />
              JSON
            </a>
          </Button>
        </Panel>

        {proposals.length > 0 && (
          <Panel position="top-right" className="!m-3">
            <Button size="sm" variant="outline" className="border-primary bg-card text-primary" onClick={() => setReviewOpen((v) => !v)}>
              <span className="size-1.5 rounded-full bg-primary" />
              {proposals.length} Vorschläge prüfen
            </Button>
            {reviewOpen && (
              <div className="mt-1.5 w-80 border border-line bg-card text-sm">
                <ul className="max-h-72 overflow-y-auto">
                  {proposals.map((p) => (
                    <li key={p.id} className="flex items-center gap-2 border-b border-border px-3 py-1.5">
                      <button className="min-w-0 flex-1 truncate text-left" onClick={() => onSelect(p)}>
                        <span className="font-mono text-primary">{p.tag || "ohne BMK"}</span>{" "}
                        <span className="text-muted-foreground">
                          {p.kind}
                          {p.confidence != null && ` · ${Math.round(p.confidence * 100)} %`}
                        </span>
                      </button>
                      <Button size="xs" variant="outline" onClick={() => review(p, true)}>
                        OK
                      </Button>
                      <Button size="xs" variant="ghost" className="text-danger" onClick={() => review(p, false)}>
                        Verwerfen
                      </Button>
                    </li>
                  ))}
                </ul>
                <div className="p-2">
                  <Button size="sm" className="w-full" onClick={acceptAll}>
                    Alle bestätigen
                  </Button>
                </div>
              </div>
            )}
          </Panel>
        )}

        <Panel position="bottom-right" className="!m-3">
          <TitleBlock layout={layout} machineName={machineName} />
        </Panel>
      </ReactFlow>

      {showSketch && layout.has_image && (
        <div className="absolute bottom-3 left-14 z-10 w-[min(560px,60%)] border border-line bg-card p-1.5">
          <div className="mb-1 flex items-center justify-between px-1 text-xs text-muted-foreground">
            <span>Skizze (Quelle der Draufsicht)</span>
            <button className="hover:text-foreground" onClick={() => setShowSketch(false)}>
              schließen
            </button>
          </div>
          {/* eslint-disable-next-line @next/next/no-img-element -- Bild kommt vom Backend, keine Optimierung noetig */}
          <img src={layoutApi.imageUrl(layout.machine_id, layout.updated_at)} alt="Skizze der Maschine" className="w-full" />
        </div>
      )}
    </div>
  );
}
