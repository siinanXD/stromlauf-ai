"use client";

import { Search } from "lucide-react";
import { useState, type KeyboardEvent } from "react";

import { Input } from "@/components/ui/input";
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
    <ul className="space-y-2 p-3" aria-busy="true" aria-label="Störfälle werden geladen">
      {Array.from({ length: 4 }, (_, i) => (
        <li key={i} className="h-14 animate-pulse rounded-lg bg-secondary" />
      ))}
    </ul>
  );
}

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
      <div className="space-y-2 border-b border-border p-3">
        {unavailable ? (
          <div className="rounded-lg border border-dashed border-border p-3 text-sm" data-testid="incidents-unavailable">
            <p className="text-muted-foreground">{unavailable.reason}</p>
            {unavailable.action && (
              <button type="button" onClick={unavailable.action.onClick} className="mt-2 min-h-11 rounded-lg bg-primary px-3 text-sm font-medium text-primary-foreground">
                {unavailable.action.label}
              </button>
            )}
          </div>
        ) : (
          <label className="block">
            <span className="sr-only">Meldung oder Frage</span>
            <Input
              value={text}
              onChange={(event) => setText(event.target.value)}
              onKeyDown={(event) => {
                if (handleComposerKey(event, text, onCreate)) setText("");
              }}
              placeholder="Meldung oder Frage"
              disabled={composerDisabled}
              enterKeyHint="send"
              autoComplete="off"
              className="h-11 bg-background text-[15px]"
              data-testid="incident-input"
            />
          </label>
        )}
        <div className="flex gap-1" role="group" aria-label="Störfälle filtern">
          {(["open", "resolved"] as const).map((value) => (
            <button
              key={value}
              type="button"
              aria-pressed={filter === value}
              onClick={() => onFilter(value)}
              className={cn(
                "min-h-11 flex-1 rounded-md border px-2 text-[13px]",
                filter === value ? "border-primary bg-primary-soft font-semibold text-foreground" : "border-border text-muted-foreground hover:text-foreground",
              )}
            >
              {value === "open" ? "Offen" : "Erledigt"} ({counts[value]})
            </button>
          ))}
        </div>
        {filter === "resolved" && counts.resolved > 0 && (
          <label className="relative block">
            <span className="sr-only">Erledigte Störfälle durchsuchen</span>
            <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" aria-hidden />
            <Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Titel oder Befund suchen" className="h-11 pl-8" />
          </label>
        )}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {loading && incidents.length === 0 ? (
          <Skeleton />
        ) : failed && incidents.length === 0 ? (
          <div className="space-y-2 p-4 text-sm" role="status">
            <p className="text-muted-foreground">Die Störfälle konnten nicht geladen werden.</p>
            <button type="button" onClick={onRetry} className="min-h-11 rounded-lg border border-border px-3 font-medium hover:border-primary">
              Erneut versuchen
            </button>
          </div>
        ) : shown.length === 0 ? (
          <p className="p-4 text-sm text-muted-foreground" data-testid="incidents-empty">
            {filter === "open"
              ? unavailable
                ? "Noch keine Störfälle."
                : "Keine offenen Störfälle. Tippe oben eine Meldung vom Bedienpanel oder ein Symptom ein und drücke Enter."
              : search.trim()
                ? `Kein erledigter Störfall passt zu „${search.trim()}“.`
                : "Noch nichts erledigt. Erledigte Störfälle bleiben hier mit ihrem Befund und helfen bei der nächsten Meldung."}
          </p>
        ) : (
          <ul className="space-y-1 p-2" aria-label={filter === "open" ? "Offene Störfälle" : "Erledigte Störfälle"}>
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
                      "flex min-h-14 w-full items-start gap-2 rounded-lg border px-2.5 py-2 text-left",
                      active ? "border-primary bg-primary-soft" : "border-transparent hover:bg-secondary",
                    )}
                  >
                    <StateIcon incident={incident} className="mt-0.5" />
                    <span className="min-w-0 flex-1">
                      <span className="line-clamp-2 text-[14px] font-medium leading-snug">{incident.title}</span>
                      <span className={cn("block text-xs", incident.failed ? "text-danger" : "text-muted-foreground")}>{stateLabel(incident)}</span>
                      {resolved && incident.finding && <span className="block truncate text-xs text-muted-foreground">Befund: {incident.finding}</span>}
                    </span>
                  </button>
                  {incident.failed && onRetryIncident && (
                    <button
                      type="button"
                      onClick={() => onRetryIncident(incident.id)}
                      className="ml-8 min-h-11 rounded-md px-2 text-xs font-medium text-primary hover:underline"
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
