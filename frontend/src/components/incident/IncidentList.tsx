"use client";

import { Plus, Search } from "lucide-react";
import { useState, type KeyboardEvent } from "react";

import { cn } from "@/lib/utils";

import { countByOutcome, outcomeOf, visibleIncidents, type Incident, type IncidentFilter } from "./incidents";
import { stateLabel, StateIcon } from "./IncidentStatus";

/**
 * Enter im Eingabefeld legt den Stoerfall an (Shift+Enter und eine laufende Wortbildung der Tastatur nicht).
 * true, wenn angelegt wurde: der Aufrufer leert dann das Feld.
 */
export function handleComposerKey(
  event: Pick<KeyboardEvent<HTMLInputElement>, "key" | "shiftKey" | "preventDefault"> & { nativeEvent?: { isComposing?: boolean } },
  text: string,
  onCreate: (text: string) => void,
): boolean {
  if (event.key !== "Enter" || event.shiftKey || event.nativeEvent?.isComposing) return false;
  event.preventDefault();
  const message = text.trim();
  if (!message) return false;
  onCreate(message);
  return true;
}

function Skeleton() {
  return (
    <ul className="space-y-1 rounded-lg bg-card p-1 lg:bg-transparent lg:p-0" aria-busy="true" aria-label="Störfälle werden geladen">
      {Array.from({ length: 4 }, (_, i) => (
        <li key={i} className="flex items-center gap-3 p-3">
          <span className="size-[26px] shrink-0 animate-pulse rounded-full bg-bg-fill" />
          <span className="flex-1 space-y-1.5">
            <span className={cn("block h-4 animate-pulse rounded-xs bg-bg-fill", i % 2 ? "w-2/3" : "w-5/6")} />
            <span className="block h-3 w-1/3 animate-pulse rounded-xs bg-bg-fill" />
          </span>
        </li>
      ))}
    </ul>
  );
}

/** Filter-Pille (Figma "Filter"): 32 px sichtbar, Trefferflaeche per before: 44 px. */
const PILL =
  "relative rounded-full px-3.5 py-1.5 text-subhead before:absolute before:inset-x-0 before:-inset-y-1.5 before:content-[''] focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none";

/**
 * Stoerfaelle der Maschine: oben das Eingabefeld "Meldung oder Frage" (Enter legt sofort an), darunter offen und
 * erledigt, neuester Stand zuerst. Erledigte lassen sich nach Titel und Befund durchsuchen.
 */
export function IncidentList({
  incidents,
  loading,
  failed,
  onRetry,
  activeId,
  filter,
  onFilter,
  onCreate,
  onSelect,
  onRetryIncident,
  unavailable,
  composerDisabled = false,
}: {
  incidents: Incident[];
  loading: boolean;
  failed: boolean;
  onRetry: () => void;
  activeId: string | null;
  filter: IncidentFilter;
  onFilter: (filter: IncidentFilter) => void;
  onCreate: (text: string) => void;
  onSelect: (id: string) => void;
  /** Nicht angelegter Stoerfall: Meldung erneut senden. */
  onRetryIncident?: (id: string) => void;
  /** Ohne verknuepfte Doku gibt es keine Stoerfaelle: Grund und naechste Aktion statt Eingabefeld. */
  unavailable?: { reason: string; action?: { label: string; onClick: () => void } };
  /** Platzhalter, solange die Maschine laedt: gleiche Form, Eingabe noch gesperrt. */
  composerDisabled?: boolean;
}) {
  const [text, setText] = useState("");
  const [search, setSearch] = useState("");
  const counts = countByOutcome(incidents);
  const shown = visibleIncidents(incidents, filter, filter === "resolved" ? search : "");

  return (
    <div className="flex h-full min-h-0 flex-col" data-testid="incident-list">
      <div className="space-y-3 px-4 pt-3 pb-3 lg:pt-4">
        {unavailable ? (
          <div className="rounded-lg bg-card p-4 text-subhead shadow-card" data-testid="incidents-unavailable">
            <p className="text-muted-foreground">{unavailable.reason}</p>
            {unavailable.action && (
              <button type="button" onClick={unavailable.action.onClick} className="mt-3 min-h-11 rounded-md bg-primary px-4 font-semibold text-primary-foreground">
                {unavailable.action.label}
              </button>
            )}
          </div>
        ) : (
          // Meldung-Eingabe (Figma): gefuelltes Feld mit blauem Plus, Enter legt den Stoerfall an
          <label className="flex h-11 cursor-text items-center gap-2 rounded-md bg-bg-fill px-3 focus-within:ring-3 focus-within:ring-ring/50 has-disabled:cursor-default has-disabled:opacity-60">
            <span className="grid size-[22px] shrink-0 place-items-center rounded-full bg-accent text-white" aria-hidden>
              <Plus className="size-3.5" strokeWidth={3} />
            </span>
            <span className="sr-only">Meldung oder Frage</span>
            <input
              value={text}
              onChange={(event) => setText(event.target.value)}
              onKeyDown={(event) => {
                if (handleComposerKey(event, text, onCreate)) setText("");
              }}
              placeholder="Meldung oder Frage"
              disabled={composerDisabled}
              enterKeyHint="send"
              autoComplete="off"
              className="h-full min-w-0 flex-1 bg-transparent text-body outline-none"
              data-testid="incident-input"
            />
          </label>
        )}
        <div className="flex gap-2" role="group" aria-label="Störfälle filtern">
          {(["open", "resolved"] as const).map((value) => (
            <button
              key={value}
              type="button"
              aria-pressed={filter === value}
              onClick={() => onFilter(value)}
              className={cn(PILL, filter === value ? "bg-primary-soft font-semibold text-primary" : "bg-bg-fill text-muted-foreground hover:text-foreground")}
            >
              {value === "open" ? "Offen" : "Erledigt"} {counts[value]}
            </button>
          ))}
        </div>
        {filter === "resolved" && counts.resolved > 0 && (
          <label className="flex h-11 items-center gap-2 rounded-md bg-bg-fill px-3 focus-within:ring-3 focus-within:ring-ring/50">
            <span className="sr-only">Erledigte Störfälle durchsuchen</span>
            <Search className="size-4 shrink-0 text-muted-foreground" aria-hidden />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Titel oder Befund suchen"
              className="h-full min-w-0 flex-1 bg-transparent text-body outline-none"
            />
          </label>
        )}
      </div>

      <div className="relative min-h-0 flex-1 overflow-y-auto px-4 pb-4">
        {loading && incidents.length === 0 ? (
          <Skeleton />
        ) : failed && incidents.length === 0 ? (
          <div className="space-y-3 py-2 text-subhead" role="status">
            <p className="text-muted-foreground">Die Störfälle konnten nicht geladen werden.</p>
            <button type="button" onClick={onRetry} className="min-h-11 rounded-md bg-bg-fill px-4 font-semibold text-primary hover:bg-muted">
              Erneut versuchen
            </button>
          </div>
        ) : shown.length === 0 ? (
          <p className="py-2 text-subhead text-muted-foreground" data-testid="incidents-empty">
            {filter === "open"
              ? unavailable
                ? "Noch keine Störfälle."
                : "Keine offenen Störfälle. Tippe oben eine Meldung vom Bedienpanel oder ein Symptom ein und drücke Enter."
              : search.trim()
                ? `Kein erledigter Störfall passt zu „${search.trim()}“.`
                : "Noch nichts erledigt. Erledigte Störfälle bleiben hier mit ihrem Befund und helfen bei der nächsten Meldung."}
          </p>
        ) : (
          // Handy: Zeilen in einer weissen Karte mit Trennern; PC: Zeilen direkt auf dem grauen Grund (Figma)
          <ul
            className="rounded-lg bg-card p-1 lg:space-y-0.5 lg:bg-transparent lg:p-0 [&>li+li]:border-t-[0.5px] [&>li+li]:border-border lg:[&>li+li]:border-t-0"
            aria-label={filter === "open" ? "Offene Störfälle" : "Erledigte Störfälle"}
          >
            {shown.map((incident) => {
              const active = incident.id === activeId;
              const resolved = outcomeOf(incident) === "resolved";
              return (
                <li key={incident.id}>
                  <button
                    type="button"
                    onClick={() => onSelect(incident.id)}
                    aria-current={active ? "true" : undefined}
                    data-incident={incident.id}
                    data-pending={incident.pending ? "true" : undefined}
                    data-failed={incident.failed ? "true" : undefined}
                    className={cn(
                      "flex min-h-11 w-full items-center gap-3 rounded-md p-3 text-left focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none",
                      active ? "bg-primary-soft" : "hover:bg-bg-fill",
                    )}
                  >
                    <StateIcon incident={incident} />
                    <span className="min-w-0 flex-1 space-y-0.5">
                      <span className="line-clamp-2 text-body">{incident.title}</span>
                      <span className={cn("block text-footnote", incident.failed ? "text-danger" : "text-muted-foreground")}>{stateLabel(incident)}</span>
                      {resolved && incident.finding && <span className="line-clamp-2 text-footnote text-muted-foreground">Befund: {incident.finding}</span>}
                    </span>
                  </button>
                  {incident.failed && onRetryIncident && (
                    <button
                      type="button"
                      onClick={() => onRetryIncident(incident.id)}
                      className="mb-1 ml-[50px] min-h-11 rounded-md px-2 text-subhead font-semibold text-primary hover:bg-bg-fill"
                      aria-label={`„${incident.title}“ erneut senden`}
                    >
                      Erneut versuchen
                    </button>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
