"use client";

import { CheckCircle2, CircleAlert, CircleDot, Loader2 } from "lucide-react";

import { cn } from "@/lib/utils";

import { outcomeOf, relativeTime, type Incident } from "./incidents";

export type IncidentState = "pending" | "failed" | "resolved" | "open";

export function incidentState(incident: Incident): IncidentState {
  if (incident.failed) return "failed";
  if (incident.pending) return "pending";
  return outcomeOf(incident);
}

/** Stand als Text (nie nur ueber Farbe): "wird angelegt …", "nicht angelegt", "Erledigt · heute 14:03". */
export function stateLabel(incident: Incident, withTime = true): string {
  const state = incidentState(incident);
  if (state === "pending") return "wird angelegt …";
  if (state === "failed") return "nicht angelegt";
  const label = state === "resolved" ? "Erledigt" : "Offen";
  return withTime ? `${label} · ${relativeTime(incident.updated_at)}` : label;
}

/** Symbol zum Stand; nur "nicht angelegt" ist rot (ein Fehler), der Rest grau. */
export function StateIcon({ incident, className }: { incident: Incident; className?: string }) {
  const state = incidentState(incident);
  const base = cn("size-4 shrink-0", className);
  if (state === "pending") return <Loader2 className={cn(base, "animate-spin text-muted-foreground")} aria-hidden />;
  if (state === "failed") return <CircleAlert className={cn(base, "text-danger")} aria-hidden />;
  if (state === "resolved") return <CheckCircle2 className={cn(base, "text-muted-foreground")} aria-hidden />;
  return <CircleDot className={cn(base, "text-muted-foreground")} aria-hidden />;
}
