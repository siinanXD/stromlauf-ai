"use client";

import { ChevronDown, ChevronRight, Crosshair } from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";

import type { PageTarget } from "@/components/PageViewer";
import type { SignalMainData, SignalMainEdge, SignalMainNode } from "@/lib/api";
import { cn } from "@/lib/utils";

import { isPart, schematicTarget } from "./planTarget";
import { edgeText, provenanceOf } from "./provenance";
import { PROVENANCE_BORDER, ProvenanceLine } from "./SignalLegend";
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

/** Kleiner Textknopf (Blatt, AWL, Abzweige): 32 px sichtbar, Trefferflaeche per before: 44 px. */
const LINK =
  "relative inline-flex min-h-8 items-center gap-1 text-footnote text-primary before:absolute before:inset-x-0 before:-inset-y-1.5 before:content-[''] hover:underline focus-visible:rounded-xs focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none";

/**
 * Signalweg als senkrechte Kette (Figma "Signal-Schritt"), ohne Grafik-Bibliothek: links die Schiene mit Punkt
 * (Start blau, Ende schwarz) und der Linie zum naechsten Schritt, deren Strichart die Herkunft zeigt (Tabelle
 * durchgezogen, Leitung gestrichelt, Lage/Modell gepunktet); rechts Kennzeichen, Spalte, Klartext, Blatt als Link
 * und die Herkunft als Text. Der Abzweig-Zaehler klappt die Abzweige darunter auf.
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

  const toggleCode = (id: string) => setCode((current) => (current === id ? null : id));

  /** Kennzeichen und Klartext; bei Bauteilen ein Knopf zum Bauteil-Detail. */
  const title = (node: SignalMainNode, children: ReactNode, className: string) =>
    isPart(node) ? (
      <button type="button" className={cn(className, "rounded-xs text-left hover:opacity-80 focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none")} onClick={() => onOpenPart(node.id)} title={`${nodeTitle(node)} öffnen`}>
        {children}
      </button>
    ) : (
      <div className={className}>{children}</div>
    );

  const followButton = (node: SignalMainNode) =>
    onFollow && node.id !== data.start ? (
      <button
        type="button"
        className="grid size-11 shrink-0 place-items-center rounded-full text-muted-foreground hover:bg-bg-fill hover:text-primary"
        onClick={() => onFollow(node.id)}
        aria-label={`Von ${nodeTitle(node)} weiter verfolgen`}
        title="Von hier weiter verfolgen"
      >
        <Crosshair className="size-5" />
      </button>
    ) : null;

  const codeLink = (node: SignalMainNode) => (
    <button type="button" className={LINK} onClick={() => toggleCode(node.id)} aria-expanded={code === node.id}>
      {code === node.id ? "AWL ausblenden" : "AWL anzeigen"}
    </button>
  );

  return (
    <ol className="space-y-0" aria-label={`Signalweg ${data.start}`}>
      {model.hiddenBefore > 0 && <li className="pb-2 pl-9 text-footnote text-muted-foreground">… {stepsText(model.hiddenBefore)} davor</li>}
      {model.steps.map((step, index) => {
        const { node } = step;
        const start = node.id === data.start;
        const outgoing = model.steps[index + 1]?.incoming ?? null;
        const end = index === model.steps.length - 1 && model.hiddenAfter === 0;
        const sheet = sheetText(node.ref);
        const plan = onOpenPlan ? schematicTarget(node, data.schematic) : null;
        const branchCount = Math.max(node.branches, step.branches.length);
        const expanded = open.has(node.id);
        return (
          <li key={node.id} data-signal-step={node.id} className="flex gap-3">
            <div className="flex w-6 shrink-0 flex-col items-center gap-1 self-stretch px-0.5 py-1" aria-hidden>
              <span className={cn("shrink-0 rounded-full", start ? "size-3.5 bg-accent" : cn("mt-0.5 size-2.5 border-2", end ? "border-foreground" : "border-line"))} />
              {outgoing && <span className={cn("w-0 flex-1 border-l-2 border-line", PROVENANCE_BORDER[provenanceOf(outgoing.via)])} />}
            </div>
            <div className="min-w-0 flex-1 pb-3.5">
              <div className="flex items-start gap-1">
                <div className="min-w-0 flex-1">
                  {title(
                    node,
                    <>
                      <span className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
                        <span className={cn("font-mono text-tag font-medium", start ? "text-primary" : "text-foreground")}>{nodeTitle(node)}</span>
                        {node.column && <span className="rounded-sm bg-bg-fill px-2 py-0.5 text-caption-2 text-muted-foreground">{COLUMN_LABELS[node.column]}</span>}
                        {start && <span className="sr-only">Start</span>}
                      </span>
                      <span className="mt-0.5 block text-subhead">{node.label || KIND_LABELS[node.kind]}</span>
                    </>,
                    "block w-full pt-0.5",
                  )}
                  {plan && onOpenPlan ? (
                    <button type="button" className={LINK} onClick={() => onOpenPlan(plan)} title="Planseite öffnen">
                      {sheet}
                    </button>
                  ) : (
                    sheet && <span className="block text-footnote text-muted-foreground">{sheet}</span>
                  )}
                  {node.kind === "network" && <div>{codeLink(node)}</div>}
                  {outgoing && (
                    <span className="block text-caption-1 text-muted-foreground">
                      <span className="sr-only">Herkunft: </span>
                      {edgeText(outgoing)}
                      {!outgoing.directed && " · Richtung offen"}
                    </span>
                  )}
                  {branchCount > 0 && (
                    <button type="button" className={cn(LINK, "hover:no-underline")} onClick={() => toggle(node.id)} aria-expanded={expanded}>
                      {expanded ? <ChevronDown className="size-4" aria-hidden /> : <ChevronRight className="size-4" aria-hidden />}
                      {branchesText(branchCount)}
                    </button>
                  )}
                </div>
                {followButton(node)}
              </div>
              {expanded && (
                <ul className="mt-1 divide-y-[0.5px] divide-border rounded-md bg-bg-grouped" aria-label={`Abzweige an ${nodeTitle(node)}`}>
                  {step.branches.map((branch) => (
                    <li key={branch.node.id} data-signal-branch={branch.node.id} className="flex items-center gap-1 pl-3">
                      {title(
                        branch.node,
                        <>
                          <span className="flex items-baseline gap-2">
                            <span className="font-mono text-tag-sm font-medium">{nodeTitle(branch.node)}</span>
                            <span className="truncate text-footnote">{branch.node.label || KIND_LABELS[branch.node.kind]}</span>
                          </span>
                          <span className="flex items-center gap-1.5 text-caption-1 text-muted-foreground">
                            {branch.edge && <ProvenanceLine provenance={provenanceOf(branch.edge.via)} className="border-muted-foreground" />}
                            {relationText(branch, node)}
                            {branch.edge && ` · ${edgeText(branch.edge)}`}
                          </span>
                        </>,
                        "block min-h-11 min-w-0 flex-1 py-2",
                      )}
                      {branch.node.kind === "network" && codeLink(branch.node)}
                      {followButton(branch.node)}
                    </li>
                  ))}
                  {branchCount > step.branches.length && (
                    <li className="px-3 py-2 text-caption-1 text-muted-foreground">
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
                    <div key={`code-${shown.id}`} className="mt-1 rounded-md bg-bg-grouped">
                      {shown.label && <p className="px-3 pt-2 text-footnote font-semibold">{shown.label}</p>}
                      <pre className="max-h-72 overflow-auto px-3 py-2 font-mono text-caption-1">{shown.detail || "Kein Code hinterlegt."}</pre>
                    </div>
                  ),
              )}
            </div>
          </li>
        );
      })}
      {model.hiddenAfter > 0 && <li className="pl-9 text-footnote text-muted-foreground">… {stepsText(model.hiddenAfter)} danach</li>}
    </ol>
  );
}
