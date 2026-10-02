"use client";

import { Route } from "lucide-react";
import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { BlockSkeleton } from "@/components/answer/blocks/Block";
import { DiagnosisRunner } from "@/components/diagnosis/DiagnosisRunner";
import { MaintenanceLog } from "@/components/diagnosis/MaintenanceLog";
import { MAIN_TABS, MORE_TABS, type AufbauTab } from "@/components/incident/view";
import { CabinetsTab } from "@/components/machine/CabinetsTab";
import { DocumentsTab } from "@/components/machine/DocumentsTab";
import { FaultBanner } from "@/components/machine/FaultBanner";
import { FaultDialog } from "@/components/machine/FaultDialog";
import { FaultTable } from "@/components/machine/FaultTable";
import { SpecsTab } from "@/components/machine/SpecsTab";
import { SchemaMap } from "@/components/model/SchemaMap";
import { PageViewer, type PageTarget } from "@/components/PageViewer";
import { CabinetLightbox } from "@/components/part/CabinetLightbox";
import { PartSheet } from "@/components/part/PartSheet";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  api,
  diagnoses as diagnosesApi,
  plant,
  type Diagnosis,
  type Fault,
  type FaultInput,
  type KnowledgeSource,
  type MachineDetail,
  type MachineMap,
} from "@/lib/api";
import type { DetailRef } from "@/lib/detail";
import { faultHits } from "@/lib/faults";
import { cn } from "@/lib/utils";

const SignalView = dynamic(() => import("@/components/signal/SignalView").then((m) => m.SignalView), {
  ssr: false,
  loading: () => <BlockSkeleton rows={5} label="Signalweg wird geladen" />,
});

type Confirm = { kind: "deleteFault"; fault: Fault } | { kind: "deleteDiagnosis"; diagnosis: Diagnosis };

/**
 * Bereich Aufbau der Maschinenseite: Modell, Schaltschrank, Signalweg, Dokumente und hinter "Mehr"
 * Fehlerliste und Kennzahlen. Jeder Tab laedt seine Daten erst, wenn er offen ist.
 */
export function AufbauArea({
  machine,
  tab,
  urlTag,
  onTab,
  map,
  referencedTags,
  onMachineChanged,
  onMapChanged,
}: {
  machine: MachineDetail;
  tab: AufbauTab | null;
  urlTag: string | null;
  onTab: (tab: AufbauTab) => void;
  map: MachineMap | null | undefined;
  referencedTags: string[];
  onMachineChanged: () => void;
  onMapChanged: () => void;
}) {
  const id = machine.id;
  const [sources, setSources] = useState<KnowledgeSource[]>([]);
  const [signalTag, setSignalTag] = useState<string>(urlTag ?? "");
  const [signalInput, setSignalInput] = useState<string>(urlTag ?? "");
  const [selectedTag, setSelectedTag] = useState<string | null>(urlTag);
  const [sheetTag, setSheetTag] = useState<string | null>(null);
  const [lightbox, setLightbox] = useState<{ cabinetId: string; hotspotId: string | null } | null>(null);
  const [faultFilter, setFaultFilter] = useState<string | null>(null);
  const [activeFault, setActiveFault] = useState<Fault | null>(null);
  const [editing, setEditing] = useState<Fault | "new" | null>(null);
  const [pageTarget, setPageTarget] = useState<PageTarget | null>(null);
  const [imageBust, setImageBust] = useState(0);
  const [diagnosisLog, setDiagnosisLog] = useState<Diagnosis[]>([]);
  const [activeDiagnosis, setActiveDiagnosis] = useState<Diagnosis | null>(null);
  const [schematic, setSchematic] = useState<{ document_id: string; filename: string } | null>(null);
  const [confirm, setConfirm] = useState<Confirm | null>(null);

  const loadDiagnoses = useCallback(() => diagnosesApi.list(id).then(setDiagnosisLog).catch(() => {}), [id]);

  // ?tag=-M1 aus Suche oder "im Werk zeigen": Bauteil im Modell markieren, ohne Tab das Modell
  const current: AufbauTab = tab ?? "schema";

  const sourceId = machine.source_id;
  useEffect(() => {
    if (current === "dokumente") api.listSources().then(setSources).catch(() => {});
    if (current !== "fehler") return;
    void loadDiagnoses();
    if (!sourceId) return;
    api
      .listDocuments(sourceId)
      .then((docs) => {
        const doc = docs.find((d) => d.doc_type === "schematic" && d.filename.toLowerCase().endsWith(".pdf"));
        setSchematic(doc ? { document_id: doc.id, filename: doc.filename } : null);
      })
      .catch(() => {});
  }, [current, sourceId, loadDiagnoses]);

  async function startDiagnosis(fault: Fault) {
    try {
      const diagnosis = await diagnosesApi.start(id, fault.id);
      setActiveDiagnosis(diagnosis);
      onTab("fehler");
      void loadDiagnoses();
    } catch {
      toast.error("Die Fehlersuche konnte nicht gestartet werden. Erneut versuchen.");
    }
  }

  const hits = activeFault ? faultHits(activeFault, machine.cabinets) : null;
  const highlightTags = useMemo(() => [...(activeFault?.tags ?? []), ...referencedTags], [activeFault, referencedTags]);

  /**
   * Bauteil aus Modell oder Fehlerliste oeffnen: Datenblatt-Sheet und Markierung, der Tab bleibt (wer im Modell
   * blaettert, bleibt dort; Foto und Signalweg sind im Sheet einen Tipp entfernt).
   */
  const openPart = useCallback((tag: string) => {
    setSelectedTag(tag);
    setSignalTag(tag);
    setSignalInput(tag);
    setSheetTag(tag);
  }, []);

  const showSignal = useCallback(
    (tag: string) => {
      setSignalTag(tag);
      setSignalInput(tag);
      onTab("signalweg");
    },
    [onTab],
  );

  /** Detail-Wunsch aus der Signalweg-Ansicht: im Aufbau als Sheet, Seite, Foto oder Fehlerliste. */
  const openFromSignal = useCallback(
    (detail: DetailRef) => {
      if (detail.kind === "part") openPart(detail.tag);
      else if (detail.kind === "plan") setPageTarget(detail.target);
      else if (detail.kind === "signal") showSignal(detail.tag);
      else if (detail.kind === "cabinet") setLightbox({ cabinetId: detail.cabinetId, hotspotId: detail.hotspotId ?? null });
      else {
        const fault = machine.faults.find((f) => f.id === detail.faultId);
        if (fault) setActiveFault(fault);
        onTab("fehler");
      }
    },
    [machine.faults, onTab, openPart, showSignal],
  );

  const showFault = useCallback((fault: Fault) => {
    setActiveFault((active) => (active?.id === fault.id ? null : fault));
    if (fault.tags[0]) setSelectedTag(fault.tags[0]);
  }, []);

  async function saveFault(body: FaultInput) {
    try {
      if (editing === "new") await plant.createFault(id, body);
      else if (editing) await plant.updateFault(editing.id, body);
      setEditing(null);
      onMachineChanged();
    } catch {
      toast.error("Speichern hat nicht geklappt. Erneut versuchen.");
    }
  }

  async function runConfirmed(action: Confirm) {
    setConfirm(null);
    if (action.kind === "deleteFault") {
      await plant.deleteFault(action.fault.id).catch(() => toast.error("Löschen hat nicht geklappt."));
      onMachineChanged();
    } else {
      await diagnosesApi.remove(action.diagnosis.id).catch(() => toast.error("Löschen hat nicht geklappt."));
      if (activeDiagnosis?.id === action.diagnosis.id) setActiveDiagnosis(null);
      void loadDiagnoses();
    }
  }

  const isMore = MORE_TABS.some((t) => t.id === current);

  return (
    <section aria-label="Aufbau der Maschine" data-testid="model-panel" data-tab={current} className="flex min-h-0 flex-1 flex-col bg-background">
      <div className="tab-scroller flex w-0 min-w-full flex-wrap items-center gap-x-1 border-b border-border bg-card px-2 sm:flex-nowrap sm:overflow-x-auto sm:[scrollbar-width:none]">
        <div role="tablist" aria-label="Ansichten des Aufbaus" className="flex shrink-0 flex-wrap items-center gap-1">
          {MAIN_TABS.map((t) => (
            <button
              key={t.id}
              role="tab"
              aria-selected={current === t.id}
              onClick={() => onTab(t.id)}
              className={cn("min-h-11 shrink-0 border-b-2 px-2.5 text-[13px]", current === t.id ? "border-primary font-semibold text-primary" : "border-transparent text-muted-foreground hover:text-foreground")}
            >
              {t.label}
            </button>
          ))}
        </div>
        <label className="shrink-0 text-[13px] text-muted-foreground">
          <span className="sr-only">Weitere Ansichten</span>
          <select value={isMore ? current : ""} onChange={(e) => e.target.value && onTab(e.target.value as AufbauTab)} className={cn("h-11 rounded-md border border-transparent bg-transparent px-1", isMore && "font-semibold text-primary")} aria-label="Mehr">
            <option value="">Mehr …</option>
            {MORE_TABS.map((t) => (
              <option key={t.id} value={t.id}>
                {t.label}
                {t.id === "fehler" && machine.fault_count ? ` (${machine.fault_count})` : ""}
              </option>
            ))}
          </select>
        </label>
      </div>

      {activeFault && hits && (
        <FaultBanner
          fault={activeFault}
          hits={hits}
          onTab={onTab}
          onTag={openPart}
          onDiagnose={(fault) => void startDiagnosis(fault)}
          onClose={() => setActiveFault(null)}
        />
      )}

      <div className="scroll-contain min-h-0 flex-1 overflow-hidden">
        {current === "schema" && (
          <div className="h-full overflow-auto">
            <SchemaMap map={map} referencedTags={highlightTags} selectedTag={selectedTag} onOpenPart={openPart} />
          </div>
        )}
        {current === "schaltschrank" && (
          <div className="h-full overflow-auto p-3">
            <CabinetsTab machine={machine} highlightTag={selectedTag} highlightTags={highlightTags} onChanged={onMachineChanged} onOpenPage={setPageTarget} />
          </div>
        )}
        {current === "signalweg" &&
          (machine.source_id ? (
            <div className="flex h-full min-h-0 flex-col gap-2 p-3">
              <form
                className="flex max-w-md items-center gap-2"
                onSubmit={(event) => {
                  event.preventDefault();
                  if (signalInput.trim()) setSignalTag(signalInput.trim());
                }}
              >
                <label className="min-w-0 flex-1">
                  <span className="sr-only">Kennzeichen für den Signalweg</span>
                  <Input value={signalInput} onChange={(e) => setSignalInput(e.target.value)} placeholder="Kennzeichen, z. B. -K1 oder E0.3" className="h-11" />
                </label>
                <Button type="submit" variant="outline" className="h-11">
                  <Route /> Verfolgen
                </Button>
              </form>
              <div className="min-h-0 flex-1 overflow-auto">
                {signalTag ? (
                  <SignalView sourceId={machine.source_id} tag={signalTag} variant="auto" onOpenDetail={openFromSignal} />
                ) : (
                  <p className="p-1 text-sm text-muted-foreground">Kennzeichen eingeben oder im Modell ein Bauteil wählen, dann zeigt der Signalweg, wovon es abhängt und was es schaltet.</p>
                )}
              </div>
            </div>
          ) : (
            <p className="p-3 text-sm text-muted-foreground">Keine Dokumentation verknüpft. Unter „Dokumente“ eine Wissensquelle wählen.</p>
          ))}
        {current === "dokumente" && (
          <div className="h-full overflow-auto p-3">
            <DocumentsTab
              machine={machine}
              sources={sources}
              imageBust={imageBust}
              onUpdate={async (body) => {
                await plant.updateMachine(id, body).catch(() => toast.error("Speichern hat nicht geklappt. Erneut versuchen."));
                onMachineChanged();
                onMapChanged();
              }}
              onUploadImage={async (file) => {
                if (!file) return;
                await plant.uploadMachineImage(id, file).catch(() => toast.error("Hochladen hat nicht geklappt. Erneut versuchen."));
                setImageBust(Date.now());
                onMachineChanged();
              }}
              onOpenPage={setPageTarget}
            />
          </div>
        )}
        {current === "fehler" && (
          <div className="h-full space-y-4 overflow-auto p-3">
            {activeDiagnosis && (
              <DiagnosisRunner
                key={activeDiagnosis.id}
                diagnosis={activeDiagnosis}
                schematic={schematic}
                onChanged={setActiveDiagnosis}
                onClose={() => {
                  setActiveDiagnosis(null);
                  void loadDiagnoses();
                  onMachineChanged();
                }}
                onOpen={setPageTarget}
              />
            )}
            <FaultTable
              onDiagnose={(fault) => void startDiagnosis(fault)}
              onShow={showFault}
              activeFaultId={activeFault?.id ?? null}
              faults={machine.faults}
              tagFilter={faultFilter}
              onTagFilter={setFaultFilter}
              onTagClick={openPart}
              onEdit={setEditing}
              onDelete={(fault) => setConfirm({ kind: "deleteFault", fault })}
            />
            <MaintenanceLog items={diagnosisLog} onResume={setActiveDiagnosis} onDelete={(d) => setConfirm({ kind: "deleteDiagnosis", diagnosis: d })} />
          </div>
        )}
        {current === "kennzahlen" && (
          <div className="h-full overflow-auto p-3">
            <SpecsTab machineId={machine.id} onSaved={onMachineChanged} />
          </div>
        )}
      </div>

      <FaultDialog fault={editing} onClose={() => setEditing(null)} onSave={saveFault} />
      <Dialog open={confirm !== null} onOpenChange={(open) => !open && setConfirm(null)}>
        <DialogContent showCloseButton={false}>
          <DialogHeader>
            <DialogTitle>{confirm?.kind === "deleteFault" ? "Fehlereintrag löschen?" : "Fehlersuche aus dem Log löschen?"}</DialogTitle>
            <DialogDescription>
              {confirm?.kind === "deleteFault"
                ? `„${confirm.fault.code || confirm.fault.symptom}“ wird aus der Fehlerliste gelöscht.`
                : confirm?.kind === "deleteDiagnosis"
                  ? `„${confirm.diagnosis.title}“ wird aus dem Log gelöscht.`
                  : ""}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button type="button" variant="outline" className="h-11" onClick={() => setConfirm(null)}>
              Abbrechen
            </Button>
            <Button type="button" className="h-11" onClick={() => confirm && void runConfirmed(confirm)}>
              Löschen
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      {pageTarget && <PageViewer target={pageTarget} onClose={() => setPageTarget(null)} />}
      {sheetTag && !lightbox && (
        <PartSheet
          tag={sheetTag}
          machine={machine}
          map={map}
          onClose={() => setSheetTag(null)}
          onOpenPage={(target) => {
            setSheetTag(null);
            setPageTarget(target);
          }}
          onOpenPart={(tag) => {
            setSelectedTag(tag);
            setSignalTag(tag);
            setSheetTag(tag);
          }}
          onShowPhoto={(cabinetId, hotspotId) => setLightbox({ cabinetId, hotspotId })}
          onShowSignal={(tag) => {
            setSheetTag(null);
            showSignal(tag);
          }}
          onUploadDatasheet={() => {
            setSheetTag(null);
            onTab("dokumente");
          }}
        />
      )}
      {lightbox && machine.cabinets.some((c) => c.id === lightbox.cabinetId) && (
        <CabinetLightbox
          cabinet={machine.cabinets.find((c) => c.id === lightbox.cabinetId)!}
          hotspotId={lightbox.hotspotId}
          referencedTags={highlightTags}
          onClose={() => setLightbox(null)}
          onChanged={onMachineChanged}
        />
      )}
    </section>
  );
}
