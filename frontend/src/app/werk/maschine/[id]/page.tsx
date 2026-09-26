"use client";

import { ScanSearch } from "lucide-react";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { AppShell } from "@/components/AppShell";
import { LayoutCanvas } from "@/components/layout/LayoutCanvas";
import { CabinetsTab } from "@/components/machine/CabinetsTab";
import { DocumentsTab } from "@/components/machine/DocumentsTab";
import { FaultDialog } from "@/components/machine/FaultDialog";
import { FaultTable } from "@/components/machine/FaultTable";
import { LayoutEmptyState } from "@/components/machine/LayoutEmptyState";
import { PartPanel } from "@/components/machine/PartPanel";
import { PageViewer, type PageTarget } from "@/components/PageViewer";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  api,
  layout as layoutApi,
  MACHINE_TYPE_LABELS,
  plant,
  type Fault,
  type FaultInput,
  type KnowledgeSource,
  type Layout,
  type LayoutPart,
  type MachineDetail,
} from "@/lib/api";

type TabId = "draufsicht" | "fehler" | "schaltschrank" | "dokumente";

const TRIGGER = "px-3 text-sm data-active:font-semibold data-active:text-primary after:!bg-primary";

export default function MachinePage() {
  const { id } = useParams<{ id: string }>();
  const [initialTag] = useState<string | null>(() =>
    typeof window === "undefined" ? null : new URLSearchParams(window.location.search).get("tag"),
  );
  const [machine, setMachine] = useState<MachineDetail | null>(null);
  const [layout, setLayout] = useState<Layout | null | undefined>(undefined);
  const [sources, setSources] = useState<KnowledgeSource[]>([]);
  const [tab, setTab] = useState<TabId>("draufsicht");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [faultFilter, setFaultFilter] = useState<string | null>(null);
  const [highlightTag, setHighlightTag] = useState<string | null>(initialTag);
  const [editing, setEditing] = useState<Fault | "new" | null>(null);
  const [pageTarget, setPageTarget] = useState<PageTarget | null>(null);
  const [imageBust, setImageBust] = useState(0);
  const [detecting, setDetecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadMachine = useCallback(() => plant.getMachine(id).then(setMachine).catch((err: Error) => setError(err.message)), [id]);
  const loadLayout = useCallback(
    () =>
      layoutApi
        .get(id)
        .then(setLayout)
        .catch((err: Error) => {
          setLayout(null);
          toast.error(`Draufsicht nicht geladen: ${err.message}`);
        }),
    [id],
  );

  useEffect(() => {
    loadMachine();
    loadLayout();
    api.listSources().then(setSources).catch(() => {});
  }, [loadMachine, loadLayout]);

  // ?tag=-M1 aus Suche oder Chat: passendes Teil in der Draufsicht waehlen, sonst Schaltschrank zeigen
  const [appliedTag, setAppliedTag] = useState(false);
  if (!appliedTag && layout !== undefined) {
    setAppliedTag(true);
    if (initialTag) {
      const hit = layout?.parts.find((p) => p.tag.toUpperCase() === initialTag.toUpperCase());
      if (hit) setSelectedId(hit.id);
      else setTab("schaltschrank");
    }
  }

  const selected: LayoutPart | null = layout?.parts.find((p) => p.id === selectedId) ?? null;

  const selectTag = useCallback(
    (tag: string) => {
      const hit = layout?.parts.find((p) => p.tag.toUpperCase() === tag.toUpperCase());
      setHighlightTag(tag);
      if (hit) {
        setSelectedId(hit.id);
        setTab("draufsicht");
      } else {
        setTab("schaltschrank");
      }
    },
    [layout],
  );

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

  if (!machine) {
    return (
      <AppShell breadcrumb={[{ label: "Werk", href: "/werk" }, { label: "…" }]}>
        <p className="p-8 text-muted-foreground">{error ?? "Lade Maschine …"}</p>
      </AppShell>
    );
  }

  const canDetect = Boolean(layout && (layout.has_image || (layout.document_id && layout.page)));

  return (
    <AppShell breadcrumb={[{ label: "Werk", href: "/werk" }, { label: machine.name }]}>
      <Tabs value={tab} onValueChange={(value) => setTab(value as TabId)} className="flex h-full flex-col gap-0">
        <div className="flex flex-wrap items-end gap-x-8 gap-y-2 border-b border-line px-6 pt-4">
          <div className="min-w-0 pb-2">
            <h1 className="truncate font-mono text-2xl font-semibold uppercase tracking-[0.02em]">{machine.name}</h1>
            <p className="font-mono text-xs text-muted-foreground">
              {MACHINE_TYPE_LABELS[machine.machine_type]} · {machine.source_name ?? "keine Doku verknüpft"} · {machine.document_count} Dokumente ·{" "}
              {layout ? `${layout.parts.length} Teile` : "keine Draufsicht"}
            </p>
          </div>
          <TabsList variant="line" className="ml-auto h-10 gap-2 pb-1">
            <TabsTrigger value="draufsicht" className={TRIGGER}>
              Draufsicht
            </TabsTrigger>
            <TabsTrigger value="fehler" className={TRIGGER}>
              Fehler {machine.fault_count}
            </TabsTrigger>
            <TabsTrigger value="schaltschrank" className={TRIGGER}>
              Schaltschrank
            </TabsTrigger>
            <TabsTrigger value="dokumente" className={TRIGGER}>
              Dokumente
            </TabsTrigger>
          </TabsList>
        </div>

        {error && <p className="mx-6 mt-3 border border-danger/40 bg-danger/5 px-3 py-2 text-sm text-danger">{error}</p>}

        <TabsContent value="draufsicht" className="min-h-0 flex-1 overflow-y-auto p-4 md:px-6">
          {layout === undefined ? (
            <p className="text-muted-foreground">Lade Draufsicht …</p>
          ) : layout === null ? (
            <div className="h-full border border-line">
              <LayoutEmptyState machine={machine} onCreated={loadLayout} />
            </div>
          ) : (
            <div className="grid h-full min-h-[520px] grid-cols-[minmax(0,1fr)] gap-4 lg:grid-cols-[minmax(0,1fr)_380px]">
              <div className="relative min-h-[420px] border border-line">
                <LayoutCanvas
                  layout={layout}
                  machineName={machine.name}
                  selectedId={selectedId}
                  onSelect={(part) => setSelectedId(part?.id ?? null)}
                  onChanged={loadLayout}
                />
                {canDetect && (
                  <Button size="sm" variant="outline" className="absolute right-3 top-14 z-10 bg-card" disabled={detecting} onClick={detect}>
                    <ScanSearch className="size-3.5" />
                    {detecting ? "Erkenne …" : "Vorschläge erkennen"}
                  </Button>
                )}
              </div>
              <PartPanel
                machine={machine}
                layout={layout}
                part={selected}
                onChanged={loadLayout}
                onOpenPage={setPageTarget}
                onShowFaults={(tag) => {
                  setFaultFilter(tag);
                  setTab("fehler");
                }}
              />
            </div>
          )}
        </TabsContent>

        <TabsContent value="fehler" className="min-h-0 flex-1 overflow-y-auto p-4 md:px-6">
          <FaultTable
            faults={machine.faults}
            tagFilter={faultFilter}
            onTagFilter={setFaultFilter}
            onTagClick={selectTag}
            onEdit={editFault}
            onDelete={deleteFault}
          />
        </TabsContent>

        <TabsContent value="schaltschrank" className="min-h-0 flex-1 overflow-y-auto p-4 md:px-6">
          <CabinetsTab machine={machine} highlightTag={highlightTag} onChanged={loadMachine} onOpenPage={setPageTarget} />
        </TabsContent>

        <TabsContent value="dokumente" className="min-h-0 flex-1 overflow-y-auto p-4 md:px-6">
          <DocumentsTab
            machine={machine}
            sources={sources}
            imageBust={imageBust}
            onUpdate={async (body) => {
              await plant.updateMachine(id, body).catch((err: Error) => toast.error(err.message));
              loadMachine();
            }}
            onUploadImage={async (file) => {
              if (!file) return;
              await plant.uploadMachineImage(id, file).catch((err: Error) => toast.error(err.message));
              setImageBust(Date.now());
              loadMachine();
            }}
            onOpenPage={setPageTarget}
          />
        </TabsContent>
      </Tabs>

      <FaultDialog fault={editing} onClose={() => setEditing(null)} onSave={saveFault} />
      {pageTarget && <PageViewer target={pageTarget} onClose={() => setPageTarget(null)} />}
    </AppShell>
  );
}
