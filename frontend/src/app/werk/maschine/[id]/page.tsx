"use client";

import { AlertTriangle, Boxes } from "lucide-react";
import dynamic from "next/dynamic";
import { useParams, usePathname, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { IncidentWorkspace, type Navigate } from "@/components/incident/IncidentWorkspace";
import { parentView, STOERFAELLE, viewFromParams, viewToQuery, type AufbauTab, type MachineView } from "@/components/incident/view";
import { MachineCostChip } from "@/components/machine/MachineCostChip";
import { MACHINE_TYPE_LABELS, plant, type AnswerMeta, type MachineDetail, type MachineMap } from "@/lib/api";
import { cn } from "@/lib/utils";


// Der Aufbau (Tabs mit Tabellen, Editoren, Draufsicht) laedt erst, wenn er geoeffnet wird
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
 * Schaltschrank, Draufsicht, Signalweg, Dokumente, Fehlerliste, Kennzahlen, Ablauf). Bereich, Tab, Stoerfall und
 * Detail stehen in der URL; jede neue Ebene ist ein Eintrag in der Historie, die Zurueck-Geste geht eine Ebene
 * zurueck. Beim Oeffnen laden nur Maschine und Stoerfaelle.
 */
export default function MachinePage() {
  const { id } = useParams<{ id: string }>();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const view = useMemo(() => viewFromParams(searchParams), [searchParams]);
  const [loaded, setLoaded] = useState<MachineDetail | null>(null);
  const [failed, setFailed] = useState(false);
  const [mapState, setMapState] = useState<{ id: string; map: MachineMap | null } | null>(null);
  const [referencedTags, setReferencedTags] = useState<string[]>([]);
  const mapRequested = useRef<string | null>(null);

  const machine = loaded?.id === id ? loaded : null;
  const map = mapState?.id === id ? mapState.map : undefined;

  const loadMachine = useCallback(
    () =>
      plant
        .getMachine(id)
        .then((result) => {
          setLoaded(result);
          setFailed(false);
        })
        .catch(() => setFailed(true)),
    [id],
  );
  const loadMap = useCallback(() => {
    mapRequested.current = id;
    return plant
      .machineMap(id)
      .then((result) => setMapState({ id, map: result }))
      .catch(() => setMapState({ id, map: null }));
  }, [id]);

  useEffect(() => {
    void loadMachine();
  }, [loadMachine]);

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

  if (!machine) {
    return (
      <AppShell breadcrumb={[{ label: "Werk", href: "/werk" }, { label: "…" }]}>
        {failed ? (
          <div className="space-y-3 p-8" role="status">
            <p className="text-muted-foreground">Die Maschine konnte nicht geladen werden.</p>
            <button type="button" onClick={() => void loadMachine()} className="min-h-11 rounded-lg border border-border px-3 font-medium hover:border-primary">
              Erneut versuchen
            </button>
          </div>
        ) : (
          <div className="flex h-full flex-col" aria-busy="true">
            <span className="sr-only">Lade Maschine …</span>
            <div className="h-14 border-b border-border bg-card" />
            <div className="flex min-h-0 flex-1 gap-3 p-3">
              <div className="w-full animate-pulse rounded-lg bg-secondary lg:w-[280px]" />
              <div className="hidden flex-1 animate-pulse rounded-lg bg-secondary/60 lg:block" />
            </div>
          </div>
        )}
      </AppShell>
    );
  }

  const openPart = view.detail?.kind === "part" ? view.detail.tag : (view.tag ?? "");
  const areaButton = (area: MachineView["area"], label: string, Icon: typeof AlertTriangle) => (
    <button
      type="button"
      aria-pressed={view.area === area}
      onClick={() => (area === "aufbau" ? navigate({ ...STOERFAELLE, area: "aufbau" }, "push") : navigate(STOERFAELLE, "push"))}
      className={cn(
        "flex min-h-11 items-center gap-1.5 rounded-md px-3 text-[13px]",
        view.area === area ? "bg-primary-soft font-semibold text-foreground" : "text-muted-foreground hover:bg-secondary hover:text-foreground",
      )}
      data-testid={`area-${area}`}
    >
      <Icon className="size-4" aria-hidden />
      {label}
    </button>
  );

  return (
    <AppShell
      breadcrumb={[
        { label: "Werk", href: "/werk" },
        { label: machine.hall_name || "Halle", href: `/werk/halle/${machine.hall_id}` },
        { label: machine.name },
      ]}
    >
      <div className="flex h-full min-h-0 flex-col overflow-x-hidden" data-testid="machine-page" data-area={view.area} data-open-part={openPart}>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-border bg-card px-3 py-1.5 md:px-6">
          <h1 className="min-w-0 truncate text-[18px] font-semibold tracking-tight md:text-[20px]">{machine.name}</h1>
          <span className="hidden rounded-md bg-secondary px-1.5 py-0.5 text-[11px] text-muted-foreground sm:inline">{MACHINE_TYPE_LABELS[machine.machine_type]}</span>
          <span className="hidden text-[11px] text-muted-foreground xl:inline">
            {machine.source_name ?? "keine Doku verknüpft"} · {machine.document_count} Dokumente
          </span>
          <nav aria-label="Bereiche der Maschine" className="ml-auto flex items-center gap-1">
            {areaButton("stoerfaelle", "Störfälle", AlertTriangle)}
            {areaButton("aufbau", "Aufbau", Boxes)}
          </nav>
          <span className="hidden md:inline">
            <MachineCostChip machineId={id} refreshKey={0} />
          </span>
        </div>

        {view.area === "aufbau" ? (
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
          />
        )}
      </div>
    </AppShell>
  );
}
