"use client";

import dynamic from "next/dynamic";
import { useParams, usePathname, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { startInitialLoad, takeMachine } from "@/components/incident/initialLoad";
import { IncidentList } from "@/components/incident/IncidentList";
import { listColumnLayout } from "@/components/incident/IncidentRail";
import { IncidentWorkspace, type Navigate } from "@/components/incident/IncidentWorkspace";
import { levelOf, parentView, STOERFAELLE, viewFromParams, viewToQuery, type AufbauTab, type MachineView } from "@/components/incident/view";
import { MachineCostChip } from "@/components/machine/MachineCostChip";
import { MACHINE_TYPE_LABELS, plant, type AnswerMeta, type MachineDetail, type MachineMap } from "@/lib/api";
import { cn } from "@/lib/utils";

// Der Aufbau (Tabs mit Tabellen und Editoren) laedt erst, wenn er geoeffnet wird
const AufbauArea = dynamic(() => import("./AufbauArea").then((m) => m.AufbauArea), {
  loading: () => <div className="flex-1 animate-pulse bg-secondary/40" aria-busy="true" />,
});

/** Eintrag in der Browser-Historie, den diese Seite selbst angelegt hat: woher er kam (Query der vorigen Ebene). */
interface LevelState {
  werkFrom?: string;
}

const sameView = (a: MachineView, b: MachineView) => viewToQuery(a) === viewToQuery(b);

/**
 * Maschinenseite mit zwei Bereichen: Stoerfaelle (Standard; Liste | Chat | Detail) und Aufbau (Modell,
 * Schaltschrank, Signalweg, Dokumente, Fehlerliste, Kennzahlen). Bereich, Tab, Stoerfall und
 * Detail stehen in der URL; jede neue Ebene ist ein Eintrag in der Historie, die Zurueck-Geste geht eine Ebene
 * zurueck. Beim Oeffnen laden nur Maschine und Stoerfaelle.
 */
export default function MachinePage() {
  const { id } = useParams<{ id: string }>();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const view = useMemo(() => viewFromParams(searchParams), [searchParams]);
  // Maschine und Stoerfaelle sofort und gleichzeitig anfragen, noch vor den Effekten von Kopfzeile und Kostenchip
  useState(() => startInitialLoad(id));
  const [listReady, setListReady] = useState(false);
  const [loaded, setLoaded] = useState<MachineDetail | null>(null);
  const [failed, setFailed] = useState(false);
  const [mapState, setMapState] = useState<{ id: string; map: MachineMap | null } | null>(null);
  const [referencedTags, setReferencedTags] = useState<string[]>([]);
  const mapRequested = useRef<string | null>(null);

  const machine = loaded?.id === id ? loaded : null;
  const map = mapState?.id === id ? mapState.map : undefined;

  const showMachine = useCallback(
    (request: Promise<MachineDetail>) =>
      request
        .then((result) => {
          setLoaded(result);
          setFailed(false);
        })
        .catch(() => setFailed(true)),
    [],
  );
  const loadMachine = useCallback(() => showMachine(plant.getMachine(id)), [id, showMachine]);
  const loadMap = useCallback(() => {
    mapRequested.current = id;
    return plant
      .machineMap(id)
      .then((result) => setMapState({ id, map: result }))
      .catch(() => setMapState({ id, map: null }));
  }, [id]);

  useEffect(() => {
    void showMachine(takeMachine(id));
  }, [id, showMachine]);

  // Das Modell braucht nur der Aufbau und das Bauteil-Detail
  const needsMap = view.area === "aufbau" || view.detail?.kind === "part";
  useEffect(() => {
    if (needsMap && mapRequested.current !== id) void loadMap();
  }, [needsMap, id, loadMap]);

  const navigate = useCallback<Navigate>(
    (next, mode) => {
      const url = `${pathname}${viewToQuery(next)}`;
      if (mode === "push") {
        const state: LevelState = { werkFrom: window.location.search };
        window.history.pushState(state, "", url);
      } else {
        const state: LevelState = { werkFrom: (window.history.state as LevelState | null)?.werkFrom };
        window.history.replaceState(state, "", url);
      }
    },
    [pathname],
  );

  /** Eine Ebene zurueck: wie die Zurueck-Geste, wenn der vorige Eintrag genau die Ebene darueber ist. */
  const goBack = useCallback(() => {
    const parent = parentView(view);
    const from = (window.history.state as LevelState | null)?.werkFrom;
    if (typeof from === "string" && sameView(viewFromParams(new URLSearchParams(from)), parent)) window.history.back();
    else navigate(parent, "replace");
  }, [view, navigate]);

  const goToAufbau = useCallback((tab: AufbauTab) => navigate({ ...STOERFAELLE, area: "aufbau", tab }, "push"), [navigate]);
  const selectTab = useCallback((tab: AufbauTab) => navigate({ ...view, area: "aufbau", tab }, "replace"), [navigate, view]);
  const showInModel = useCallback(
    (tags: string[]) => {
      setReferencedTags(tags);
      navigate({ ...STOERFAELLE, area: "aufbau", tab: "schema" }, "push");
    },
    [navigate],
  );
  const onMeta = useCallback((meta: AnswerMeta) => setReferencedTags(Array.isArray(meta.referenced_tags) ? meta.referenced_tags : []), []);
  const onListReady = useCallback(() => setListReady(true), []);

  const openPart = view.detail?.kind === "part" ? view.detail.tag : (view.tag ?? "");
  // Segment (Figma "Segment"): 32 px hoch wie iOS, die Trefferflaeche reicht per before: auf 44 px
  const areaButton = (area: MachineView["area"], label: string) => (
    <button
      type="button"
      aria-pressed={view.area === area}
      onClick={() => (area === "aufbau" ? navigate({ ...STOERFAELLE, area: "aufbau" }, "push") : navigate(STOERFAELLE, "push"))}
      className={cn(
        "relative flex h-7 flex-1 items-center justify-center rounded-[7px] text-subhead text-foreground before:absolute before:inset-x-0 before:-inset-y-2 before:content-['']",
        view.area === area ? "bg-popover font-semibold shadow-card" : "hover:bg-bg-fill",
      )}
      data-testid={`area-${area}`}
    >
      {label}
    </button>
  );

  const level = levelOf(view);
  const noop = () => {};
  // Platzhalter in der Form der fertigen Seite: Liste mit Eingabe und Filter, daneben der Chat (nichts springt)
  const placeholder =
    view.area === "aufbau" ? (
      <div className="flex-1 animate-pulse bg-secondary/40" aria-busy="true" />
    ) : (
      <div className="flex min-h-0 flex-1" aria-busy="true">
        <div className={listColumnLayout(level, false).column}>
          <IncidentList incidents={[]} loading failed={false} onRetry={noop} activeId={null} filter="open" onFilter={noop} onCreate={noop} onSelect={noop} composerDisabled />
        </div>
        <div className={cn("min-h-0 min-w-0 flex-1 flex-col lg:flex", level === "chat" ? "flex" : "hidden")}>
          <div className="flex-1 animate-pulse bg-secondary/40" />
        </div>
      </div>
    );

  return (
    <AppShell
      breadcrumb={
        machine
          ? [{ label: "Maschinen", href: "/werk/maschinen" }, { label: machine.hall_name || "Halle" }, { label: machine.name }]
          : [{ label: "Maschinen", href: "/werk/maschinen" }, { label: "…" }]
      }
    >
      <div className="flex h-full min-h-0 flex-col overflow-x-hidden" data-testid="machine-page" data-area={view.area} data-open-part={openPart}>
        {/* Kopf (Figma "Kopfzeile"): Halle und Art ueber dem Namen, rechts das Segment; am Handy darunter in voller Breite */}
        {/* Am Handy hat ein offener Stoerfall seine eigene Nav-Leiste; der Kopf gehoert zur Liste */}
        <div
          className={cn(
            "flex flex-wrap items-center gap-x-4 gap-y-3 border-b-[0.5px] border-border bg-bg-bar px-4 pt-2 pb-3 backdrop-blur-bar md:flex-nowrap md:px-6 md:py-3",
            view.area === "stoerfaelle" && level !== "list" && "max-lg:hidden",
          )}
        >
          <div className="min-w-0 flex-1 basis-full md:basis-auto">
            {machine ? (
              <>
                <p className="truncate text-footnote text-muted-foreground">
                  {[machine.hall_name || "Halle", MACHINE_TYPE_LABELS[machine.machine_type]].join(" · ")}
                  <span className="hidden xl:inline">
                    {" · "}
                    {machine.source_name ?? "keine Doku verknüpft"} · {machine.document_count} Dokumente
                  </span>
                </p>
                <h1 className="truncate text-large-title md:text-title-2">{machine.name}</h1>
              </>
            ) : (
              <>
                <span className="block h-[18px] w-32 animate-pulse rounded-xs bg-bg-fill" aria-hidden />
                <h1 className="text-large-title md:text-title-2">
                  <span className="mt-1 inline-block h-8 w-56 animate-pulse rounded-sm bg-bg-fill align-middle md:h-6 md:w-48" aria-hidden />
                  <span className="sr-only">{failed ? "Maschine" : "Lade Maschine …"}</span>
                </h1>
              </>
            )}
          </div>
          {/* Kostenchip erst nach der Liste, damit seine Anfrage die Stoerfaelle nicht aufhaelt; links der Bereiche,
              damit beim Erscheinen nichts verrutscht */}
          {machine && (listReady || view.area === "aufbau") && (
            <span className="hidden shrink-0 md:inline">
              <MachineCostChip machineId={id} refreshKey={0} />
            </span>
          )}
          <nav aria-label="Bereiche der Maschine" className="flex h-8 w-full shrink-0 gap-0.5 rounded-sm bg-bg-fill p-0.5 md:w-60">
            {areaButton("stoerfaelle", "Störfälle")}
            {areaButton("aufbau", "Aufbau")}
          </nav>
        </div>

        {!machine ? (
          failed ? (
            <div className="space-y-3 p-8" role="status">
              <p className="text-body text-muted-foreground">Die Maschine konnte nicht geladen werden.</p>
              <button type="button" onClick={() => void loadMachine()} className="min-h-11 rounded-md bg-bg-fill px-4 text-subhead font-semibold text-primary hover:bg-muted">
                Erneut versuchen
              </button>
            </div>
          ) : (
            placeholder
          )
        ) : view.area === "aufbau" ? (
          <AufbauArea
            key={machine.id}
            machine={machine}
            tab={view.tab}
            urlTag={view.tag}
            onTab={selectTab}
            map={map}
            referencedTags={referencedTags}
            onMachineChanged={() => void loadMachine()}
            onMapChanged={() => void loadMap()}
          />
        ) : (
          <IncidentWorkspace
            key={machine.id}
            machine={machine}
            view={view}
            navigate={navigate}
            goBack={goBack}
            map={map}
            referencedTags={referencedTags}
            onMeta={onMeta}
            onShowInModel={showInModel}
            onGoToAufbau={goToAufbau}
            onMachineChanged={() => void loadMachine()}
            onListReady={onListReady}
          />
        )}
      </div>
    </AppShell>
  );
}
