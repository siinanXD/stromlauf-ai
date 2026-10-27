import type { Edge, Node } from "@xyflow/react";
import type { Run, RunStep, SchrittStatus } from "@/lib/api";

export type { SchrittStatus };

export interface SchrittNodeData extends Record<string, unknown> {
  step: RunStep;
  index: number;
}

const ABSTAND_X = 220;
const HAENGT_NACH_MS = 10 * 60 * 1000;

/** Sieben Schritte als Knoten in einer Reihe, verbunden von links nach rechts. */
export function flowOf(steps: RunStep[]): { nodes: Node<SchrittNodeData, "schritt">[]; edges: Edge[] } {
  const nodes = steps.map((step, index) => ({
    id: step.key,
    type: "schritt" as const,
    position: { x: index * ABSTAND_X, y: 0 },
    data: { step, index },
  }));
  const edges = steps.slice(1).map((step, i) => ({
    id: `${steps[i].key}>${step.key}`,
    source: steps[i].key,
    target: step.key,
  }));
  return { nodes, edges };
}

const KLASSEN: Record<SchrittStatus, string> = {
  wartet: "border-line-strong text-text-secondary",
  laeuft: "border-accent text-accent motion-safe:animate-pulse",
  fertig: "border-ok text-ok",
  fehler: "border-error text-error",
};

export const statusKlasse = (status: SchrittStatus): string => KLASSEN[status];

export const STATUS_LABELS: Record<SchrittStatus, string> = {
  wartet: "wartet",
  laeuft: "läuft",
  fertig: "fertig",
  fehler: "Fehler",
};

/**
 * Der Lauf läuft, aber seit mehr als 10 Minuten tut sich nichts: Bezugszeit ist der Start des
 * laufenden Schritts, ohne laufenden Schritt das jüngste Ende eines Schritts, sonst der Anlegezeitpunkt.
 */
export function haengt(run: Run, now: Date): boolean {
  if (run.status !== "laeuft") return false;
  const laufend = run.steps.find((s) => s.status === "laeuft");
  const enden = run.steps.flatMap((s) => (s.finished_at ? [new Date(s.finished_at).getTime()] : []));
  const bezug = laufend ? laufend.started_at : enden.length ? new Date(Math.max(...enden)).toISOString() : run.created_at;
  return !!bezug && now.getTime() - new Date(bezug).getTime() > HAENGT_NACH_MS;
}

/** Läufe, die noch abgefragt werden: alle laufenden, auch die scheinbar hängenden (bei mehreren Anlagen wartet Lesen nacheinander). */
export const zuPollen = (runs: Run[]): Run[] => runs.filter((r) => r.status === "laeuft");

/** "12,3 s" aus Start und Ende des Schritts, sonst leer. */
export function dauerText(step: RunStep): string {
  if (!step.started_at || !step.finished_at) return "";
  const sekunden = (new Date(step.finished_at).getTime() - new Date(step.started_at).getTime()) / 1000;
  return `${sekunden.toFixed(1).replace(".", ",")} s`;
}
