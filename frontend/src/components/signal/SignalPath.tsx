"use client";

import "@xyflow/react/dist/style.css";

import {
  Background,
  BackgroundVariant,
  Controls,
  Handle,
  MarkerType,
  Position,
  ReactFlow,
  type Edge,
  type Node,
  type NodeProps,
  type NodeTypes,
} from "@xyflow/react";
import { Route, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import type { PageTarget } from "@/components/PageViewer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { signalPath, type SignalNode, type SignalPathData } from "@/lib/api";
import { cn } from "@/lib/utils";

const COL_W = 230;
const ROW_H = 84;
const NODE_W = 190;

type SignalNodeData = { node: SignalNode; start: boolean };
type SignalFlowNode = Node<SignalNodeData, "signal">;

const KIND_LABEL: Record<SignalNode["kind"], string> = {
  device: "Betriebsmittel",
  pin: "Anschluss",
  terminal: "Klemme",
  address: "SPS-Adresse",
  network: "Netzwerk",
  variable: "Variable",
};

function title(node: SignalNode) {
  if (node.kind === "network") return node.ref;
  if (node.kind === "variable") return node.id.split("#").pop() ?? node.id;
  return node.id;
}

function SignalNodeView({ data }: NodeProps<SignalFlowNode>) {
  const { node, start } = data;
  return (
    <div
      className={cn(
        "flex h-full flex-col justify-center border px-2.5 py-1.5",
        start ? "border-primary bg-primary text-primary-foreground" : "border-line bg-card",
        node.kind === "network" && !start && "border-dashed",
        node.kind === "variable" && !start && "border-border bg-secondary",
      )}
      title={[KIND_LABEL[node.kind], node.label, node.ref].filter(Boolean).join(" · ")}
    >
      <Handle type="target" position={Position.Left} className="!opacity-0" isConnectable={false} />
      <div className="flex items-baseline justify-between gap-2">
        <span className={cn("truncate font-mono text-[13px] font-semibold", !start && node.kind !== "variable" && "text-primary")}>{title(node)}</span>
        {node.ref && node.kind !== "network" && <span className={cn("font-mono text-[10px]", start ? "text-white/80" : "text-muted-foreground")}>{node.ref}</span>}
      </div>
      <div className={cn("truncate text-[11px]", start ? "text-white/85" : "text-muted-foreground")}>{node.label || KIND_LABEL[node.kind]}</div>
      <Handle type="source" position={Position.Right} className="!opacity-0" isConnectable={false} />
    </div>
  );
}

const NODE_TYPES: NodeTypes = { signal: SignalNodeView };

function layout(data: SignalPathData): { nodes: SignalFlowNode[]; edges: Edge[] } {
  const byLevel = new Map<number, SignalNode[]>();
  data.nodes.forEach((node) => byLevel.set(node.level, [...(byLevel.get(node.level) ?? []), node]));
  const tallest = Math.max(...[...byLevel.values()].map((list) => list.length));
  const minLevel = Math.min(...byLevel.keys());
  const nodes = [...byLevel.entries()].flatMap(([level, list]) =>
    list.map((node, index) => ({
      id: node.id,
      type: "signal" as const,
      position: { x: (level - minLevel) * COL_W, y: (index + (tallest - list.length) / 2) * ROW_H },
      width: NODE_W,
      height: 58,
      data: { node, start: node.id === data.start },
      draggable: false,
    })),
  );
  const edges = data.edges.map((edge) => ({
    id: `${edge.source}->${edge.target}`,
    source: edge.source,
    target: edge.target,
    type: "smoothstep",
    style: { stroke: "var(--primary)", strokeWidth: 1.5 },
    markerEnd: { type: MarkerType.ArrowClosed, color: "var(--primary)", width: 14, height: 14 },
  }));
  return { nodes, edges };
}

/**
 * Signalweg eines Kennzeichens: links die Quellen, rechts die Folgen. Klick auf Geraet/Klemme oeffnet
 * das Blatt, Klick auf ein Netzwerk zeigt den AWL-Code, Doppelklick verfolgt ab diesem Knoten weiter.
 */
export function SignalPath({ sourceId, initialTag, onOpen }: { sourceId: string; initialTag: string; onOpen: (target: PageTarget) => void }) {
  const [tag, setTag] = useState(initialTag);
  const [input, setInput] = useState(initialTag);
  const [data, setData] = useState<SignalPathData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [code, setCode] = useState<SignalNode | null>(null);

  const [seenInitial, setSeenInitial] = useState(initialTag);
  if (seenInitial !== initialTag) {
    setSeenInitial(initialTag);
    setTag(initialTag);
    setInput(initialTag);
  }

  useEffect(() => {
    if (!tag.trim()) return;
    let cancelled = false;
    signalPath(tag, sourceId)
      .then((result) => {
        if (cancelled) return;
        setData(result);
        setError(null);
        setCode(null);
      })
      .catch((err: Error) => {
        if (cancelled) return;
        setData(null);
        setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, [tag, sourceId]);

  const flow = useMemo(() => (data ? layout(data) : null), [data]);

  function open(node: SignalNode) {
    if (node.kind === "network") {
      setCode(node);
      return;
    }
    if (data?.schematic && /^\/\d+\.\d+$/.test(node.ref)) {
      onOpen({
        documentId: data.schematic.document_id,
        filename: data.schematic.filename,
        reference: node.ref,
        label: `Stromlaufplan ${node.ref} · ${node.id}`,
        // Anschluss -K1:A1 gehoert zum Geraet -K1
        tag: node.kind === "device" ? node.id : node.kind === "pin" ? node.id.split(":")[0] : null,
      });
    }
  }

  return (
    <div className="flex h-full flex-col border border-line bg-card">
      <form
        className="flex flex-wrap items-center gap-2 border-b border-line px-3 py-2"
        onSubmit={(event) => {
          event.preventDefault();
          setTag(input.trim());
        }}
      >
        <Route className="size-4 text-primary" />
        <Input value={input} onChange={(e) => setInput(e.target.value)} placeholder="-S1, -X3:1, E0.0 …" className="h-8 w-44 font-mono" aria-label="Kennzeichen" />
        <Button size="sm" type="submit" disabled={!input.trim()}>
          Verfolgen
        </Button>
        <span className="text-xs text-muted-foreground max-md:hidden">
          Links Quellen, rechts Folgen · Klick öffnet Blatt bzw. AWL · Doppelklick verfolgt ab dort
        </span>
      </form>
      <div className="relative min-h-0 flex-1">
        {error && <p className="p-6 text-sm text-muted-foreground">{error}</p>}
        {!error && !flow && <p className="p-6 text-sm text-muted-foreground">{tag ? "Lade Signalweg …" : "Kennzeichen eingeben, z. B. -S1."}</p>}
        {flow && (
          <ReactFlow
            key={data?.start}
            nodes={flow.nodes}
            edges={flow.edges}
            nodeTypes={NODE_TYPES}
            onNodeClick={(_, node) => open((node.data as SignalNodeData).node)}
            onNodeDoubleClick={(_, node) => {
              setInput(node.id);
              setTag(node.id);
            }}
            nodesConnectable={false}
            fitView
            fitViewOptions={{ padding: 0.15 }}
            minZoom={0.2}
            proOptions={{ hideAttribution: true }}
          >
            <Background variant={BackgroundVariant.Lines} gap={24} color="var(--grid)" lineWidth={0.5} />
            <Controls showInteractive={false} className="!rounded-none !shadow-none [&_button]:!border-border [&_button]:!bg-card" />
          </ReactFlow>
        )}
        {code && (
          <aside className="absolute inset-y-0 right-0 z-10 flex w-[min(380px,90%)] flex-col border-l border-line bg-card">
            <div className="flex items-center justify-between bg-nav px-3 py-2 text-white">
              <span className="font-mono text-xs font-semibold">{code.ref}</span>
              <button onClick={() => setCode(null)} aria-label="Schließen">
                <X className="size-4" />
              </button>
            </div>
            <p className="px-3 pt-2 text-[13px] font-medium">{code.label}</p>
            <pre className="min-h-0 flex-1 overflow-auto px-3 py-2 font-mono text-[12px] leading-5">{code.detail}</pre>
          </aside>
        )}
      </div>
    </div>
  );
}
