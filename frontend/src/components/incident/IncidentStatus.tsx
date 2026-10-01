"use client";

import { Check } from "lucide-react";

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

/** Ausrufezeichen im roten Kreis (Figma "Icon/Exclamation"), in Schriftfarbe gezeichnet. */
function Exclamation({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="none" aria-hidden className={className}>
      <path d="M8 4.667V9M8 11.333v.007" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/**
 * Symbol zum Stand (Figma "Störfall-Zeile", Status): offen leerer Ring, erledigt gruener Kreis mit Haken, wird
 * angelegt blauer Bogen, nicht angelegt roter Kreis mit Ausrufezeichen. Die Form unterscheidet die Staende auch
 * ohne Farbe; rot ist nur der Fehler. size "sm" fuer Kopfzeile und schmale Leiste.
 */
export function StateIcon({ incident, size = "md", className }: { incident: Incident; size?: "md" | "sm"; className?: string }) {
  const state = incidentState(incident);
  const box = cn("grid shrink-0 place-items-center rounded-full", size === "md" ? "size-[26px]" : "size-3.5", className);
  const glyph = size === "md" ? "size-4" : "size-2.5";
  if (state === "pending")
    return <span className={cn(box, "animate-spin border-accent border-l-transparent", size === "md" ? "border-2" : "border-[1.5px]")} aria-hidden />;
  if (state === "failed")
    return (
      <span className={cn(box, "bg-error text-white")} aria-hidden>
        <Exclamation className={glyph} />
      </span>
    );
  if (state === "resolved")
    return (
      <span className={cn(box, "bg-ok text-white")} aria-hidden>
        <Check className={glyph} strokeWidth={3} />
      </span>
    );
  return <span className={cn(box, "border-line", size === "md" ? "border-2" : "border-[1.5px]")} aria-hidden />;
}
