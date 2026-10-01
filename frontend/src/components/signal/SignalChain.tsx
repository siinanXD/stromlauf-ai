"use client";

import { ChevronDown, ChevronRight, Crosshair, FileText } from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";

import type { PageTarget } from "@/components/PageViewer";
import type { SignalMainData, SignalMainEdge, SignalMainNode } from "@/lib/api";
import { cn } from "@/lib/utils";

import { isPart, schematicTarget } from "./planTarget";
import { edgeText, provenanceOf } from "./provenance";
import { ProvenanceLine } from "./SignalLegend";
import { COLUMN_LABELS, KIND_LABELS, mainPath, nodeTitle, sheetText } from "./signalColumns";

export interface ChainBranch {
  node: SignalMainNode;
  /** Kante zwischen Abzweig und Hauptwegknoten; null, wenn die Antwort keine liefert. */
  edge: SignalMainEdge | null;
}

export interface ChainStep {
  node: SignalMainNode;
  /** Kante vom vorigen Hauptwegknoten; null beim ersten Schritt des Hauptwegs. */
  incoming: SignalMainEdge | null;
  branches: ChainBranch[];
}

export interface ChainModel {
  steps: ChainStep[];
  /** Hauptwegknoten vor bzw. nach dem gezeigten Ausschnitt (nur mit limit). */
  hiddenBefore: number;
  hiddenAfter: number;
}

function edgeBetween(edges: SignalMainEdge[], a: string, b: string): SignalMainEdge | null {
  return edges.find((e) => (e.source === a && e.target === b) || (e.source === b && e.target === a)) ?? null;
}

/**
 * Die Kette aus den Daten der Hauptweg-Sicht: je Hauptwegknoten ein Schritt mit der Kante davor und seinen
 * Abzweigen. Mit limit bleibt ein Ausschnitt um den Start, so wie ihn der Antwortblock zeigt.
 */
export function chainModel(data: SignalMainData, limit?: number): ChainModel {
  const path = mainPath(data);
  let from = 0;
  let to = path.length;
  if (limit !== undefined && path.length > limit) {
    const startIndex = Math.max(0, path.findIndex((node) => node.id === data.start));
    from = Math.min(Math.max(0, startIndex - Math.floor((limit - 1) / 2)), path.length - limit);
    to = from + limit;
  }
  const steps = path.slice(from, to).map((node, index) => ({
    node,
    incoming: from + index > 0 ? edgeBetween(data.edges, path[from + index - 1].id, node.id) : null,
    branches: data.nodes
      .filter((other) => !other.main && other.parent === node.id)
      .sort((a, b) => a.id.localeCompare(b.id))
      .map((branch) => ({ node: branch, edge: edgeBetween(data.edges, branch.id, node.id) })),
  }));
  return { steps, hiddenBefore: from, hiddenAfter: path.length - to };
}

const stepsText = (n: number) => (n === 1 ? "1 Schritt" : `${n} Schritte`);
const branchesText = (n: number) => (n === 1 ? "1 Abzweig" : `${n} Abzweige`);

/** Wie ein Abzweig am Hauptwegknoten haengt, in Worten. */
function relationText(branch: ChainBranch, parent: SignalMainNode): string {
  const name = nodeTitle(parent);
  if (!branch.edge) return `neben ${name}`;
  if (!branch.edge.directed) return `verbunden mit ${name}, Richtung offen`;
  return branch.edge.source === parent.id ? `kommt von ${name}` : `geht zu ${name}`;
}

function Connector({ edge }: { edge: SignalMainEdge }) {
  return (
    <div className="flex items-center gap-2 py-0.5 pl-[18px] text-[11px] text-muted-foreground">
      <ProvenanceLine provenance={provenanceOf(edge.via)} vertical className="text-foreground/70" />
      <span>
        <span className="sr-only">Herkunft: </span>
        {edgeText(edge)}
        {!edge.directed && " · Richtung offen"}
      </span>
    </div>
  );
}

const followClass =
  "flex w-12 shrink-0 items-center justify-center border-l border-line text-muted-foreground hover:bg-secondary hover:text-primary";

/**
 * Signalweg als senkrechte Liste, ohne Grafik-Bibliothek: je Hauptwegknoten eine Zeile mit Kennzeichen,
 * Klartext, Blatt und Herkunft der Verbindung davor. Der Abzweig-Zaehler klappt die Abzweige darunter auf.
 */
export function SignalChain({
  data,
  limit,
  defaultOpen,
  onOpenPart,
  onOpenPlan,
  onFollow,
}: {
  data: SignalMainData;
  /** Hoechstens so viele Hauptwegknoten, als Ausschnitt um den Start. */
  limit?: number;
  /** Knoten, deren Abzweige beim ersten Zeichnen offen sind. */
  defaultOpen?: string[];
  onOpenPart: (tag: string) => void;
  onOpenPlan?: (target: PageTarget) => void;
  /** Ohne: kein "Von hier weiter verfolgen". */
  onFollow?: (tag: string) => void;
}) {
  const model = useMemo(() => chainModel(data, limit), [data, limit]);
  const [open, setOpen] = useState<ReadonlySet<string>>(() => new Set(defaultOpen ?? []));
  const [code, setCode] = useState<string | null>(null);

  const toggle = (id: string) =>
    setOpen((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  /** Netzwerk: AWL-Code auf-/zuklappen; Bauteil: Detail oeffnen; Variable: nichts. */
  const activate = (node: SignalMainNode) => {
    if (node.kind === "network") setCode((current) => (current === node.id ? null : node.id));
    else if (isPart(node)) onOpenPart(node.id);
  };

  const nodeButton = (node: SignalMainNode, children: ReactNode, className: string) => {
    if (node.kind !== "network" && !isPart(node)) return <div className={className}>{children}</div>;
    return (
      <button
        type="button"
        className={cn(className, "text-left hover:bg-secondary")}
        onClick={() => activate(node)}
        aria-expanded={node.kind === "network" ? code === node.id : undefined}
        title={node.kind === "network" ? "AWL-Code zeigen" : `${nodeTitle(node)} öffnen`}
      >
        {children}
      </button>
    );
  };

  const followButton = (node: SignalMainNode) =>
    onFollow && node.id !== data.start ? (
      <button
        type="button"
        className={followClass}
        onClick={() => onFollow(node.id)}
        aria-label={`Von ${nodeTitle(node)} weiter verfolgen`}
        title="Von hier weiter verfolgen"
      >
        <Crosshair className="size-4" />
      </button>
    ) : null;

  return (
    <ol className="space-y-0" aria-label={`Signalweg ${data.start}`}>
      {model.hiddenBefore > 0 && (
        <li className="px-3 pb-1 text-[11px] text-muted-foreground">… {stepsText(model.hiddenBefore)} davor</li>
      )}
      {model.steps.map((step) => {
        const { node } = step;
        const start = node.id === data.start;
        const sheet = sheetText(node.ref);
        const plan = onOpenPlan ? schematicTarget(node, data.schematic) : null;
        const branchCount = Math.max(node.branches, step.branches.length);
        const expanded = open.has(node.id);
        return (
          <li key={node.id} data-signal-step={node.id}>
            {step.incoming && <Connector edge={step.incoming} />}
            <div className={cn("border bg-card", start ? "border-primary" : "border-line")}>
              <div className="flex">
                {nodeButton(
                  node,
                  <>
                    <span className="flex items-baseline gap-2">
                      <span className="font-mono text-sm font-semibold text-primary">{nodeTitle(node)}</span>
                      {node.column && <span className="text-[11px] text-muted-foreground">{COLUMN_LABELS[node.column]}</span>}
                      {start && <span className="ml-auto bg-primary-soft px-1.5 font-mono text-[10px] uppercase text-primary">Start</span>}
                    </span>
                    <span className="block truncate text-[13px]">{node.label || KIND_LABELS[node.kind]}</span>
                    {sheet && !plan && <span className="block font-mono text-[11px] text-muted-foreground">{sheet}</span>}
                  </>,
                  "min-h-12 min-w-0 flex-1 px-3 py-2",
                )}
                {followButton(node)}
              </div>
              {(plan || branchCount > 0) && (
                <div className="flex flex-wrap border-t border-line">
                  {plan && onOpenPlan && (
                    <button
                      type="button"
                      className="flex min-h-11 items-center gap-1.5 px-3 font-mono text-[12px] text-primary hover:bg-secondary"
                      onClick={() => onOpenPlan(plan)}
                      title="Planseite öffnen"
                    >
                      <FileText className="size-3.5" />
                      {sheet}
                    </button>
                  )}
                  {branchCount > 0 && (
                    <button
                      type="button"
                      className="flex min-h-11 items-center gap-1 px-3 text-[12px] text-muted-foreground hover:bg-secondary hover:text-foreground"
                      onClick={() => toggle(node.id)}
                      aria-expanded={expanded}
                    >
                      {expanded ? <ChevronDown className="size-3.5" /> : <ChevronRight className="size-3.5" />}
                      {branchesText(branchCount)}
                    </button>
                  )}
                </div>
              )}
              {expanded && (
                <ul className="border-t border-line bg-secondary/50" aria-label={`Abzweige an ${nodeTitle(node)}`}>
                  {step.branches.map((branch) => (
                    <li key={branch.node.id} data-signal-branch={branch.node.id} className="flex border-b border-dashed border-line last:border-b-0">
                      {nodeButton(
                        branch.node,
                        <>
                          <span className="flex items-baseline gap-2">
                            <span className="font-mono text-[13px] font-semibold text-primary">{nodeTitle(branch.node)}</span>
                            <span className="truncate text-[12px]">{branch.node.label || KIND_LABELS[branch.node.kind]}</span>
                          </span>
                          <span className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
                            {branch.edge && <ProvenanceLine provenance={provenanceOf(branch.edge.via)} className="w-6" />}
                            {relationText(branch, node)}
                            {branch.edge && ` · ${edgeText(branch.edge)}`}
                          </span>
                        </>,
                        "min-h-11 min-w-0 flex-1 px-3 py-1.5",
                      )}
                      {followButton(branch.node)}
                    </li>
                  ))}
                  {branchCount > step.branches.length && (
                    <li className="px-3 py-2 text-[11px] text-muted-foreground">
                      {step.branches.length ? "… und " : ""}
                      {branchesText(branchCount - step.branches.length)} ohne weitere Angaben
                    </li>
                  )}
                </ul>
              )}
              {[node, ...step.branches.map((b) => b.node)].map(
                (shown) =>
                  shown.kind === "network" &&
                  code === shown.id && (
                    <div key={`code-${shown.id}`} className="border-t border-line">
                      {shown.label && <p className="px-3 pt-2 text-[13px] font-medium">{shown.label}</p>}
                      <pre className="max-h-72 overflow-auto px-3 py-2 font-mono text-[12px] leading-5">{shown.detail || "Kein Code hinterlegt."}</pre>
                    </div>
                  ),
              )}
            </div>
          </li>
        );
      })}
      {model.hiddenAfter > 0 && (
        <li className="px-3 pt-1 text-[11px] text-muted-foreground">… {stepsText(model.hiddenAfter)} danach</li>
      )}
    </ol>
  );
}
