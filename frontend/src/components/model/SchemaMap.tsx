"use client";

import { Maximize2 } from "lucide-react";
import { useCallback, useMemo, useRef } from "react";

import { PartChip } from "@/components/chat/PartChip";
import type { MachineMap } from "@/lib/api";
import { highlightFor, isReferenced, orderZones, zoneTitle } from "@/lib/model";
import { cn } from "@/lib/utils";

/**
 * Modell "Schema": Zonen (Einbauorte) als Karten mit Bauteil-Chips, Verbinder als Fusszeile je Zone.
 * Die Zonen sind eine Liste mit aria-label; Pfeiltasten wandern durch die Chips, Klick oeffnet das Bauteil.
 * `compact` = Streifen am Handy (waagerecht scrollende Zonen).
 */
export function SchemaMap({
  map,
  referencedTags,
  selectedTag,
  onOpenPart,
  compact = false,
  onExpand,
}: {
  map: MachineMap | null | undefined;
  referencedTags: string[];
  selectedTag?: string | null;
  onOpenPart: (tag: string) => void;
  compact?: boolean;
  onExpand?: () => void;
}) {
  const listRef = useRef<HTMLUListElement>(null);
  const highlight = useMemo(() => highlightFor(map, referencedTags), [map, referencedTags]);
  const zones = useMemo(() => (map ? orderZones(map.zones, referencedTags) : []), [map, referencedTags]);

  // Pfeiltasten: durch alle Chips des Modells, Home/End an Anfang und Ende
  const onKeyDown = useCallback((event: React.KeyboardEvent) => {
    const keys = ["ArrowRight", "ArrowLeft", "ArrowDown", "ArrowUp", "Home", "End"];
    if (!keys.includes(event.key) || !listRef.current) return;
    const chips = [...listRef.current.querySelectorAll<HTMLButtonElement>("button.part-chip")];
    const index = chips.indexOf(document.activeElement as HTMLButtonElement);
    if (index < 0) return;
    event.preventDefault();
    const next =
      event.key === "Home" ? 0 : event.key === "End" ? chips.length - 1 : event.key === "ArrowRight" || event.key === "ArrowDown" ? Math.min(chips.length - 1, index + 1) : Math.max(0, index - 1);
    chips[next]?.focus();
  }, []);

  if (map === undefined) return <p className="p-3 text-sm text-muted-foreground">Lade Modell …</p>;
  if (!map || map.zones.length === 0) {
    return (
      <p className="p-3 text-sm text-muted-foreground" data-testid="schema-empty">
        Noch kein Modell: keine Kennzeichen in der Doku, keine Stückliste, keine Draufsicht. Dokumente hochladen, dann entstehen hier die Zonen der Maschine.
      </p>
    );
  }

  return (
    <div className={cn("flex h-full min-h-0 flex-col", compact ? "gap-1" : "gap-2")}>
      <div className="flex items-center gap-2 px-3 pt-2 text-[11px] text-muted-foreground">
        <span className="font-mono">{map.part_count} Bauteile · {map.zones.length} Zonen</span>
        {referencedTags.length > 0 && (
          <span className="rounded-md bg-signal-soft px-1.5 py-0.5 font-medium text-signal-foreground" data-testid="highlight-count">
            {highlight.placed.length} {highlight.placed.length === 1 ? "Bauteil" : "Bauteile"} aus der Antwort markiert
            {highlight.unplaced.length > 0 && ` · ${highlight.unplaced.join(", ")} nicht im Modell`}
          </span>
        )}
        <span className="ml-auto hidden items-center gap-2 sm:flex">
          <span className="inline-block size-2.5 rounded-sm border border-signal bg-signal-soft" aria-hidden />
          <span>referenziert</span>
        </span>
        {onExpand && (
          <button type="button" onClick={onExpand} className="rounded-md border border-border p-1 hover:border-primary" aria-label="Modell vergrößern">
            <Maximize2 className="size-3.5" />
          </button>
        )}
      </div>
      <ul
        ref={listRef}
        aria-label="Zonen der Maschine"
        onKeyDown={onKeyDown}
        className={cn(
          "scroll-contain min-h-0 w-0 min-w-full flex-1 gap-2 px-3 pb-3",
          compact ? "flex snap-x overflow-x-auto [scrollbar-width:thin]" : "grid content-start overflow-y-auto sm:grid-cols-2 xl:grid-cols-3",
        )}
      >
        {zones.map((zone) => {
          const lit = highlight.zoneIds.includes(zone.id);
          const links = map.connectors.filter((c) => c.source === zone.id || c.target === zone.id);
          return (
            <li
              key={zone.id}
              data-zone={zone.id}
              data-lit={lit ? "true" : "false"}
              aria-label={`Zone ${zoneTitle(zone)}, ${zone.parts.length} Bauteile`}
              className={cn(
                "rounded-xl border bg-card p-2.5 transition-colors",
                compact ? "w-56 shrink-0 snap-start" : "",
                lit ? "border-signal shadow-[0_0_0_1px_var(--signal)]" : "border-border",
              )}
            >
              <div className="mb-1.5 flex items-baseline gap-2">
                <span className="font-mono text-[13px] font-semibold">{zone.code === "?" || zone.code === "anlage" ? zone.name : zone.code}</span>
                {zone.name && zone.code !== "?" && zone.code !== "anlage" && <span className="truncate text-xs text-muted-foreground">{zone.name}</span>}
                <span className="ml-auto font-mono text-[11px] text-muted-foreground">{zone.parts.length}</span>
              </div>
              <div className={cn("flex flex-wrap gap-1", compact && "max-h-16 overflow-hidden")}>
                {zone.parts.map((part) => (
                  <PartChip
                    key={part.tag}
                    tag={part.tag}
                    label={compact ? undefined : part.label || part.kind}
                    referenced={isReferenced(part.tag, referencedTags)}
                    active={selectedTag ? isReferenced(part.tag, [selectedTag]) : false}
                    onClick={() => onOpenPart(part.tag)}
                    className="max-w-[12rem]"
                  />
                ))}
              </div>
              {!compact && links.length > 0 && (
                <ul className="mt-2 flex flex-wrap gap-1 border-t border-border pt-1.5" aria-label={`Verbindungen von ${zoneTitle(zone)}`}>
                  {links.map((link) => (
                    <li key={`${link.source}-${link.target}-${link.label}`} className="rounded-md bg-secondary px-1.5 py-0.5 font-mono text-[11px] text-muted-foreground">
                      {link.source === zone.id ? `→ ${link.target}` : `← ${link.source}`}
                      {link.label && ` · ${link.label}`}
                    </li>
                  ))}
                </ul>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
