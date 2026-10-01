"use client";

import { PanelLeftOpen } from "lucide-react";

import { cn } from "@/lib/utils";

import { visibleIncidents, type Incident, type IncidentFilter } from "./incidents";
import { stateLabel, StateIcon } from "./IncidentStatus";
import type { Level } from "./view";

/** Kuerzel fuer die schmale Leiste: die ersten zwei Zeichen ohne Leerzeichen ("-K1 zieht …" -> "-K"). */
export function railInitials(title: string): string {
  return title.replace(/\s+/g, "").slice(0, 2).toUpperCase() || "?";
}

/**
 * Spalten der Stoerfall-Liste: ab 1024 px neben Chat und Detail. Ist das Detail offen, wird sie unter 1280 px zur
 * schmalen Leiste, damit der Chat nicht zu eng wird; ab 1280 px und ohne Detail ist sie voll da.
 */
export function listColumnLayout(level: Level, detailOpen: boolean) {
  return {
    column: cn(
      "min-h-0 w-full flex-col bg-background lg:flex lg:shrink-0 lg:border-r-[0.5px] lg:border-border 2xl:w-[300px]",
      detailOpen ? "lg:w-[68px] xl:w-[260px]" : "lg:w-[260px]",
      level === "list" ? "flex" : "hidden",
    ),
    rail: detailOpen,
    railClass: "hidden h-full min-h-0 lg:flex xl:hidden",
    listClass: cn("flex h-full min-h-0 w-full flex-col", detailOpen && "lg:hidden xl:flex"),
  };
}

/** Schmale Leiste: Stand als Symbol, Kuerzel, Titel als Name und Tooltip; jeder Eintrag 44 px gross. */
export function IncidentRail({
  incidents,
  filter,
  activeId,
  onSelect,
  onExpand,
}: {
  incidents: Incident[];
  filter: IncidentFilter;
  activeId: string | null;
  onSelect: (id: string) => void;
  /** Detail schliessen: die Liste wird wieder breit. */
  onExpand: () => void;
}) {
  const shown = visibleIncidents(incidents, filter);
  return (
    <nav aria-label="Störfälle" className="flex min-h-0 w-full flex-col items-center gap-1 overflow-y-auto py-2" data-testid="incident-rail">
      <button
        type="button"
        onClick={onExpand}
        aria-label="Störfall-Liste zeigen und Detail schließen"
        title="Liste zeigen"
        className="grid size-11 shrink-0 place-items-center rounded-full text-primary hover:bg-bg-fill"
      >
        <PanelLeftOpen className="size-5" aria-hidden />
      </button>
      <ul className="flex flex-col items-center gap-1.5">
        {shown.map((incident) => {
          const active = incident.id === activeId;
          return (
            <li key={incident.id}>
              <button
                type="button"
                onClick={() => onSelect(incident.id)}
                aria-current={active ? "true" : undefined}
                aria-label={`${incident.title}, ${stateLabel(incident, false)}`}
                title={incident.title}
                data-incident={incident.id}
                className={cn("relative grid size-11 place-items-center rounded-md", active ? "bg-primary-soft text-primary" : "bg-bg-fill text-muted-foreground hover:text-foreground")}
              >
                <span className="text-footnote font-semibold" aria-hidden>
                  {railInitials(incident.title)}
                </span>
                <StateIcon incident={incident} size="sm" className="absolute -top-0.5 -right-0.5 ring-2 ring-background" />
              </button>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
