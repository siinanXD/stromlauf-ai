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

/** Der Lauf läuft, und sein laufender Schritt ist seit mehr als 10 Minuten dabei. */
export function haengt(run: Run, now: Date): boolean {
  if (run.status !== "laeuft") return false;
  const start = run.steps.find((s) => s.status === "laeuft")?.started_at;
  return !!start && now.getTime() - new Date(start).getTime() > HAENGT_NACH_MS;
}

/** "12,3 s" aus Start und Ende des Schritts, sonst leer. */
export function dauerText(step: RunStep): string {
  if (!step.started_at || !step.finished_at) return "";
  const sekunden = (new Date(step.finished_at).getTime() - new Date(step.started_at).getTime()) / 1000;
  return `${sekunden.toFixed(1).replace(".", ",")} s`;
}
