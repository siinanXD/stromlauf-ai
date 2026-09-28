"use client";

import { ChevronDown, ChevronUp, Maximize2, X } from "lucide-react";
import { useParams, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { AppShell } from "@/components/AppShell";
import { DiagnosisRunner } from "@/components/diagnosis/DiagnosisRunner";
import { MaintenanceLog } from "@/components/diagnosis/MaintenanceLog";
import { LayoutCanvas } from "@/components/layout/LayoutCanvas";
import { CabinetsTab } from "@/components/machine/CabinetsTab";
import { DocumentsTab } from "@/components/machine/DocumentsTab";
import { FaultBanner } from "@/components/machine/FaultBanner";
import { FaultDialog } from "@/components/machine/FaultDialog";
import { FaultTable } from "@/components/machine/FaultTable";
import { FlowTab } from "@/components/machine/FlowTab";
import { LayoutEmptyState } from "@/components/machine/LayoutEmptyState";
import { MachineChatTab } from "@/components/machine/MachineChatTab";
import { MachineCostChip } from "@/components/machine/MachineCostChip";
import { PartPanel } from "@/components/machine/PartPanel";
import { SpecsTab } from "@/components/machine/SpecsTab";
import { SchemaMap } from "@/components/model/SchemaMap";
import { PageViewer, type PageTarget } from "@/components/PageViewer";
import { SignalPath } from "@/components/signal/SignalPath";
import {
  api,
  diagnoses as diagnosesApi,
  layout as layoutApi,
  MACHINE_TYPE_LABELS,
  plant,
  type AnswerMeta,
  type Diagnosis,
  type Fault,
  type FaultInput,
  type KnowledgeSource,
  type Layout,
  type LayoutPart,
  type MachineDetail,
  type MachineMap,
} from "@/lib/api";
import { faultHits, sameTag } from "@/lib/faults";
import { cn } from "@/lib/utils";

/** Tabs des Modell-Panels; "mehr" buendelt die Nebenansichten hinter einem Menue. */
type TabId = "schema" | "draufsicht" | "schaltschrank" | "signalweg" | "dokumente" | "ablauf" | "fehler" | "kennzahlen";
const MAIN_TABS: { id: TabId; label: string }[] = [
  { id: "schema", label: "Schema" },
  { id: "draufsicht", label: "Draufsicht" },
  { id: "schaltschrank", label: "Schaltschrank" },
  { id: "signalweg", label: "Signalweg" },
  { id: "dokumente", label: "Dokumente" },
];
const MORE_TABS: { id: TabId; label: string }[] = [
  { id: "ablauf", label: "Ablauf" },
  { id: "fehler", label: "Fehler" },
  { id: "kennzahlen", label: "Kennzahlen" },
];
const TAB_IDS = new Set<string>([...MAIN_TABS, ...MORE_TABS].map((t) => t.id));

function tabFromUrl(value: string | null): TabId {
  if (value === "chat") return "schema"; // alte Links: der Chat ist jetzt immer da
  return value && TAB_IDS.has(value) ? (value as TabId) : "schema";
}

/**
 * Maschinenansicht, chat-first (MB-4): oben das Modell der Maschine (einklappbar, am Handy ein Streifen),
 * darunter der Chat mit festem Composer. Jede Antwort markiert ihre Bauteile im Modell.
 */
export default function MachinePage() {
  const { id } = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const urlTag = searchParams.get("tag");
  const urlTab = searchParams.get("tab");
  const [machine, setMachine] = useState<MachineDetail | null>(null);
  const [layout, setLayout] = useState<Layout | null | undefined>(undefined);
  const [map, setMap] = useState<MachineMap | null | undefined>(undefined);
  const [sources, setSources] = useState<KnowledgeSource[]>([]);
  const [tab, setTab] = useState<TabId>(() => tabFromUrl(urlTab));
  const [panel, setPanel] = useState<"strip" | "open" | "full">("open");
  const [signalTag, setSignalTag] = useState<string>(urlTag ?? "");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedTag, setSelectedTag] = useState<string | null>(urlTag);
  const [referencedTags, setReferencedTags] = useState<string[]>([]);
  const [faultFilter, setFaultFilter] = useState<string | null>(null);
  const [activeFault, setActiveFault] = useState<Fault | null>(null);
  const [editing, setEditing] = useState<Fault | "new" | null>(null);
  const [pageTarget, setPageTarget] = useState<PageTarget | null>(null);
  const [imageBust, setImageBust] = useState(0);
  const [detecting, setDetecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [diagnosisLog, setDiagnosisLog] = useState<Diagnosis[]>([]);
  const [activeDiagnosis, setActiveDiagnosis] = useState<Diagnosis | null>(null);
  const [schematic, setSchematic] = useState<{ document_id: string; filename: string } | null>(null);

  const loadMachine = useCallback(() => plant.getMachine(id).then(setMachine).catch((err: Error) => setError(err.message)), [id]);
  const loadMap = useCallback(() => plant.machineMap(id).then(setMap).catch(() => setMap(null)), [id]);
  const loadLayout = useCallback(
    () =>
      layoutApi
        .get(id)
        .then(setLayout)
        .catch(() => setLayout(null)),
    [id],
  );
  const loadDiagnoses = useCallback(() => diagnosesApi.list(id).then(setDiagnosisLog).catch(() => {}), [id]);

  useEffect(() => {
    loadDiagnoses();
    loadMachine();
    loadLayout();
    loadMap();
    api.listSources().then(setSources).catch(() => {});
  }, [loadMachine, loadLayout, loadMap, loadDiagnoses]);

  // ?tag=-M1 aus Suche oder Chat: Bauteil markieren und die passende Ansicht waehlen
  const [appliedTag, setAppliedTag] = useState<string | null | undefined>(undefined);
  if (layout !== undefined && appliedTag !== urlTag) {
    setAppliedTag(urlTag);
    if (urlTag) {
      setSelectedTag(urlTag);
      setSignalTag(urlTag);
      const hit = layout?.parts.find((p) => sameTag(p.tag, urlTag));
      if (urlTab === "signalweg") setTab("signalweg");
      else if (hit) {
        setSelectedId(hit.id);
        setTab("draufsicht");
      }
    }
  }

  const sourceId = machine?.source_id ?? null;
  useEffect(() => {
    if (!sourceId) return;
    api
      .listDocuments(sourceId)
      .then((docs) => {
        const doc = docs.find((d) => d.doc_type === "schematic" && d.filename.toLowerCase().endsWith(".pdf"));
        setSchematic(doc ? { document_id: doc.id, filename: doc.filename } : null);
      })
      .catch(() => {});
  }, [sourceId]);

  async function startDiagnosis(fault: Fault) {
    try {
      const diagnosis = await diagnosesApi.start(id, fault.id);
      setActiveDiagnosis(diagnosis);
      setTab("fehler");
      setPanel("full");
      loadDiagnoses();
    } catch (err) {
      toast.error((err as Error).message);
    }
  }

  const selected: LayoutPart | null = layout?.parts.find((p) => p.id === selectedId) ?? null;
  const hits = activeFault ? faultHits(activeFault, layout, machine?.cabinets ?? []) : null;
  const highlightTags = useMemo(() => [...(activeFault?.tags ?? []), ...referencedTags], [activeFault, referencedTags]);

  /** Bauteil aus Modell, Antwort-Chip oder Fehlerliste oeffnen: markieren und die beste Ansicht zeigen (MB-5 bringt das Datenblatt). */
  const openPart = useCallback(
    (tag: string) => {
      setSelectedTag(tag);
      setSignalTag(tag);
      const inLayout = layout?.parts.find((p) => sameTag(p.tag, tag));
      const inCabinet = (machine?.cabinets ?? []).some((c) => c.hotspots.some((h) => sameTag(h.tag, tag)));
      if (inLayout) {
        setSelectedId(inLayout.id);
        setTab("draufsicht");
      } else if (inCabinet) setTab("schaltschrank");
      else setTab("schema");
      setPanel((p) => (p === "strip" ? "open" : p));
    },
    [layout, machine],
  );

  const showInModel = useCallback((tags: string[]) => {
    setReferencedTags(tags);
    setTab("schema");
    setPanel((p) => (p === "strip" ? "open" : p));
  }, []);

  const onMeta = useCallback((meta: AnswerMeta) => setReferencedTags(meta.referenced_tags), []);

  const showFault = useCallback((fault: Fault) => {
    setActiveFault((current) => (current?.id === fault.id ? null : fault));
    if (fault.tags[0]) setSelectedTag(fault.tags[0]);
  }, []);

  const editFault = useCallback((fault: Fault | "new") => setEditing(fault), []);
  const deleteFault = useCallback(
    async (fault: Fault) => {
      if (!confirm(`Fehlereintrag „${fault.code || fault.symptom}“ löschen?`)) return;
      await plant.deleteFault(fault.id).catch((err: Error) => toast.error(err.message));
      loadMachine();
    },
    [loadMachine],
  );

  async function saveFault(body: FaultInput) {
    try {
      if (editing === "new") await plant.createFault(id, body);
      else if (editing) await plant.updateFault(editing.id, body);
      setEditing(null);
      loadMachine();
    } catch (err) {
      toast.error(`Speichern fehlgeschlagen: ${(err as Error).message}`);
    }
  }

  async function detect() {
    if (!layout) return;
    if (!confirm("Claude Vision liest die Skizze und schlägt Teile vor. Das kostet API-Tokens. Fortfahren?")) return;
    setDetecting(true);
    try {
      const result = await layoutApi.detect(layout.id);
      setLayout(result);
      toast.success(`${result.parts.filter((p) => !p.confirmed).length} Vorschläge erkannt`);
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setDetecting(false);
    }
  }

  function selectTab(next: TabId) {
    setTab(next);
    if (MORE_TABS.some((t) => t.id === next)) setPanel("full");
    else setPanel((p) => (p === "strip" ? "open" : p));
  }

  if (!machine) {
    return (
      <AppShell breadcrumb={[{ label: "Werk", href: "/werk" }, { label: "…" }]}>
        <p className="p-8 text-muted-foreground">{error ?? "Lade Maschine …"}</p>
      </AppShell>
    );
  }

  const canDetect = Boolean(layout && (layout.has_image || (layout.document_id && layout.page)));
  const isMore = MORE_TABS.some((t) => t.id === tab);
  const panelHeight = panel === "strip" ? "h-[70px]" : panel === "full" ? "h-[min(72vh,760px)]" : isMore ? "h-[min(60vh,560px)]" : "h-[220px] xl:h-[300px]";

  const panelBody = (
    <>
      {tab === "schema" && (
        <SchemaMap map={map} referencedTags={highlightTags} selectedTag={selectedTag} onOpenPart={openPart} compact={panel === "strip"} onExpand={panel === "full" ? undefined : () => setPanel("full")} />
      )}
      {tab === "draufsicht" &&
        (layout === undefined ? (
          <p className="p-3 text-muted-foreground">Lade Draufsicht …</p>
        ) : layout === null ? (
          <div className="h-full">
            <LayoutEmptyState machine={machine} onCreated={loadLayout} />
          </div>
        ) : (
          <div className="grid h-full min-h-0 grid-cols-[minmax(0,1fr)] gap-3 p-3 lg:grid-cols-[minmax(0,1fr)_340px]">
            <div className="relative min-h-[180px] rounded-xl border border-border">
              <LayoutCanvas
                layout={layout}
                machineName={machine.name}
                selectedId={selectedId}
                highlightTags={highlightTags}
                onSelect={(part) => {
                  setSelectedId(part?.id ?? null);
                  if (part?.tag) setSelectedTag(part.tag);
                }}
                onChanged={loadLayout}
                onDetect={canDetect ? detect : undefined}
                detecting={detecting}
              />
            </div>
            <div className="hidden min-h-0 overflow-y-auto lg:block">
              <PartPanel
                machine={machine}
                layout={layout}
                part={selected}
                onChanged={loadLayout}
                onOpenPage={setPageTarget}
                onShowFaults={(tag) => {
                  setFaultFilter(tag);
                  selectTab("fehler");
                }}
                onShowSignal={(tag) => {
                  setSignalTag(tag);
                  selectTab("signalweg");
                }}
              />
            </div>
          </div>
        ))}
      {tab === "schaltschrank" && (
        <div className="h-full overflow-auto p-3">
          <CabinetsTab machine={machine} highlightTag={selectedTag} highlightTags={highlightTags} onChanged={loadMachine} onOpenPage={setPageTarget} />
        </div>
      )}
      {tab === "signalweg" &&
        (machine.source_id ? (
          <div className="h-full min-h-0 p-3">
            <SignalPath sourceId={machine.source_id} initialTag={signalTag || selected?.tag || ""} onOpen={setPageTarget} />
          </div>
        ) : (
          <p className="p-3 text-sm text-muted-foreground">Keine Dokumentation verknüpft. Unter „Dokumente“ eine Wissensquelle wählen.</p>
        ))}
      {tab === "dokumente" && (
        <div className="h-full overflow-auto p-3">
          <DocumentsTab
            machine={machine}
            sources={sources}
            imageBust={imageBust}
            onUpdate={async (body) => {
              await plant.updateMachine(id, body).catch((err: Error) => toast.error(err.message));
              loadMachine();
              loadMap();
            }}
            onUploadImage={async (file) => {
              if (!file) return;
              await plant.uploadMachineImage(id, file).catch((err: Error) => toast.error(err.message));
              setImageBust(Date.now());
              loadMachine();
            }}
            onOpenPage={setPageTarget}
          />
        </div>
      )}
      {tab === "ablauf" && (
        <div className="h-full overflow-auto p-3">
          <FlowTab machineId={machine.id} hasSource={Boolean(machine.source_id)} highlightTags={highlightTags} />
        </div>
      )}
      {tab === "fehler" && (
        <div className="h-full space-y-4 overflow-auto p-3">
          {activeDiagnosis && (
            <DiagnosisRunner
              key={activeDiagnosis.id}
              diagnosis={activeDiagnosis}
              schematic={schematic}
              onChanged={setActiveDiagnosis}
              onClose={() => {
                setActiveDiagnosis(null);
                loadDiagnoses();
                loadMachine();
              }}
              onOpen={setPageTarget}
            />
          )}
          <FaultTable
            onDiagnose={startDiagnosis}
            onShow={showFault}
            activeFaultId={activeFault?.id ?? null}
            faults={machine.faults}
            tagFilter={faultFilter}
            onTagFilter={setFaultFilter}
            onTagClick={openPart}
            onEdit={editFault}
            onDelete={deleteFault}
          />
          <MaintenanceLog
            items={diagnosisLog}
            onResume={setActiveDiagnosis}
            onDelete={async (d) => {
              if (!confirm(`Fehlersuche „${d.title}“ aus dem Log löschen?`)) return;
              await diagnosesApi.remove(d.id).catch((err: Error) => toast.error(err.message));
              if (activeDiagnosis?.id === d.id) setActiveDiagnosis(null);
              loadDiagnoses();
            }}
          />
        </div>
      )}
      {tab === "kennzahlen" && (
        <div className="h-full overflow-auto p-3">
          <SpecsTab machineId={machine.id} onSaved={loadMachine} />
        </div>
      )}
    </>
  );

  return (
    <AppShell
      breadcrumb={[
        { label: "Werk", href: "/werk" },
        { label: machine.hall_name || "Halle", href: `/werk/halle/${machine.hall_id}` },
        { label: machine.name },
      ]}
    >
      <div className="flex h-full min-h-0 flex-col overflow-x-hidden" data-testid="machine-page" data-open-part={selectedTag ?? ""}>
        {/* Kopf: Name, Chips, Monatskosten */}
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-border bg-card px-4 py-2 md:px-6">
          <h1 className="min-w-0 truncate text-[20px] font-semibold tracking-tight">{machine.name}</h1>
          <span className="rounded-md bg-secondary px-1.5 py-0.5 text-[11px] text-muted-foreground">{MACHINE_TYPE_LABELS[machine.machine_type]}</span>
          {machine.hall_name && <span className="hidden rounded-md bg-secondary px-1.5 py-0.5 text-[11px] text-muted-foreground sm:inline">{machine.hall_name}</span>}
          <span className="hidden text-[11px] text-muted-foreground md:inline">
            {machine.source_name ?? "keine Doku verknüpft"} · {machine.document_count} Dokumente · {map ? `${map.part_count} Bauteile im Modell` : "kein Modell"}
          </span>
          <span className="ml-auto">
            <MachineCostChip machineId={id} refreshKey={imageBust} />
          </span>
        </div>

        {error && <p className="mx-4 mt-2 rounded-lg border border-danger/40 bg-danger/5 px-3 py-2 text-sm text-danger md:mx-6">{error}</p>}
        {activeFault && hits && (
          <FaultBanner
            fault={activeFault}
            hits={hits}
            hasFlow={Boolean(machine.source_id)}
            onTab={(target) => {
              if (target === "draufsicht" && hits.partIds[0]) setSelectedId(hits.partIds[0]);
              selectTab(target);
            }}
            onTag={openPart}
            onDiagnose={(fault) => startDiagnosis(fault)}
            onClose={() => setActiveFault(null)}
          />
        )}

        {/* Modell-Panel */}
        <section aria-label="Maschinenmodell" data-testid="model-panel" data-panel={panel} className={cn("flex shrink-0 flex-col border-b border-border bg-background transition-[height] duration-200", panelHeight)}>
          <div className="tab-scroller flex w-0 min-w-full flex-wrap items-center gap-x-1 border-b border-border bg-card px-2 sm:flex-nowrap sm:overflow-x-auto sm:[scrollbar-width:none]">
            <div role="tablist" aria-label="Ansichten des Modells" className="flex shrink-0 items-center gap-1">
              {MAIN_TABS.map((t) => (
                <button
                  key={t.id}
                  role="tab"
                  aria-selected={tab === t.id}
                  onClick={() => selectTab(t.id)}
                  className={cn("shrink-0 border-b-2 px-2.5 py-2 text-[13px]", tab === t.id ? "border-primary font-semibold text-primary" : "border-transparent text-muted-foreground hover:text-foreground")}
                >
                  {t.label}
                </button>
              ))}
            </div>
            <label className="shrink-0 text-[13px] text-muted-foreground">
              <span className="sr-only">Weitere Ansichten</span>
              <select value={isMore ? tab : ""} onChange={(e) => e.target.value && selectTab(e.target.value as TabId)} className={cn("h-8 rounded-md border border-transparent bg-transparent px-1", isMore && "font-semibold text-primary")} aria-label="Mehr">
                <option value="">Mehr …</option>
                {MORE_TABS.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.label}
                    {t.id === "fehler" && machine.fault_count ? ` (${machine.fault_count})` : ""}
                  </option>
                ))}
              </select>
            </label>
            <span className="ml-auto flex shrink-0 items-center gap-1">
              {panel !== "full" && (
                <button type="button" onClick={() => setPanel("full")} className="rounded-md p-1.5 text-muted-foreground hover:text-foreground" aria-label="Modell vergrößern">
                  <Maximize2 className="size-4" />
                </button>
              )}
              <button
                type="button"
                onClick={() => setPanel((p) => (p === "strip" ? "open" : p === "open" ? "strip" : "open"))}
                className="rounded-md p-1.5 text-muted-foreground hover:text-foreground"
                aria-label={panel === "strip" ? "Modell aufklappen" : panel === "full" ? "Modell verkleinern" : "Modell einklappen"}
                data-testid="panel-toggle"
              >
                {panel === "strip" ? <ChevronDown className="size-4" /> : panel === "full" ? <X className="size-4" /> : <ChevronUp className="size-4" />}
              </button>
            </span>
          </div>
          <div className="scroll-contain min-h-0 flex-1 overflow-hidden">{panelBody}</div>
        </section>

        {/* Chat */}
        <div className="min-h-0 flex-1">
          <MachineChatTab
            machine={machine}
            onOpenPage={setPageTarget}
            activeReference={pageTarget?.reference ? `${pageTarget.documentId}${pageTarget.reference}` : null}
            onMeta={onMeta}
            onOpenPart={openPart}
            onShowInModel={showInModel}
            onGoToDocuments={() => selectTab("dokumente")}
          />
        </div>
      </div>

      <FaultDialog fault={editing} onClose={() => setEditing(null)} onSave={saveFault} />
      {pageTarget && <PageViewer target={pageTarget} onClose={() => setPageTarget(null)} />}
    </AppShell>
  );
}
