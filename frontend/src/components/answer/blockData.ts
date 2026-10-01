/**
 * Welche Antwortbloecke eine Antwort hat, in der festen Reihenfolge der Spec. Rein und defensiv: alte Antworten
 * ohne die neuen meta-Felder (part_kinds, signal_start, plan_spots) bekommen keine neuen Bloecke.
 */
import type { AnswerMeta, CabinetEvidence, PlanSpot } from "@/lib/api";

import type { BlockKind } from "./blocks/Block";

export const BLOCK_ORDER: BlockKind[] = ["faults", "text", "parts", "signal", "plan", "cabinet", "citations"];

export const MAX_PLAN_SPOTS = 4;

export interface MetaBlockData {
  parts: { tags: string[]; kinds: Record<string, string> } | null;
  signal: string | null;
  plan: PlanSpot[] | null;
  cabinet: CabinetEvidence[] | null;
}

const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);

function validSpot(spot: unknown): spot is PlanSpot {
  return isRecord(spot) && typeof spot.tag === "string" && typeof spot.document_id === "string" && typeof spot.page === "number";
}

export function metaBlockData(meta: AnswerMeta | undefined, sourceId: string | null | undefined): MetaBlockData {
  if (!meta) return { parts: null, signal: null, plan: null, cabinet: null };
  const tags = Array.isArray(meta.referenced_tags) ? meta.referenced_tags.filter((t) => typeof t === "string" && t) : [];

  const kinds = isRecord(meta.part_kinds) ? (meta.part_kinds as Record<string, string>) : null;
  const parts = kinds && tags.length > 0 ? { tags, kinds } : null;

  const start = typeof meta.signal_start === "string" ? meta.signal_start.trim() : "";
  const signal = sourceId && start ? start : null;

  const spots = Array.isArray(meta.plan_spots) ? meta.plan_spots.filter(validSpot).slice(0, MAX_PLAN_SPOTS) : [];
  const plan = spots.length > 0 ? spots : null;

  const evidence = Array.isArray(meta.evidence) ? meta.evidence : [];
  const cabinets = evidence.filter((e): e is CabinetEvidence => isRecord(e) && e.kind === "cabinet");
  const cabinet = cabinets.length > 0 ? cabinets : null;

  return { parts, signal, plan, cabinet };
}
