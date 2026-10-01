"use client";

import { ChevronLeft, Pencil } from "lucide-react";
import dynamic from "next/dynamic";
import { useState, type ReactNode } from "react";

import { BlockSkeleton } from "@/components/answer/blocks/Block";
import { knownFault } from "@/components/answer/faultHitsStore";
import { PartChip } from "@/components/chat/PartChip";
import { PageViewer } from "@/components/PageViewer";
import { CabinetLightbox } from "@/components/part/CabinetLightbox";
import { PartBody, PartFooter, PartHeaderChips, partDescription, usePartData, type PartActions } from "@/components/part/PartSheet";
import { plant, type Cabinet, type Fault, type MachineDetail, type MachineMap } from "@/lib/api";
import type { DetailRef } from "@/lib/detail";
import { matchesAny } from "@/lib/faults";
import { cn } from "@/lib/utils";

import type { AufbauTab } from "./view";

// Die Signalweg-Ansicht bringt ihre Grafik-Bibliothek mit; erst laden, wenn das Detail offen ist.
const SignalView = dynamic(() => import("@/components/signal/SignalView").then((m) => m.SignalView), {
  ssr: false,
  loading: () => (
    <div className="p-4">
      <BlockSkeleton rows={5} label="Signalweg wird geladen" />
    </div>
  ),
});

/** Breite der Detailspalte ab 1024 px; dieselbe wie die angedockte Seitenansicht. */
export const DETAIL_WIDTH = "lg:w-[min(560px,45%)]";

const TITLES: Record<Exclude<DetailRef["kind"], "plan">, string> = {
  signal: "Signalweg",
  part: "Bauteil",
  cabinet: "Schaltschrank",
  fault: "Fehlereintrag",
};

function Empty({ children, action }: { children: ReactNode; action?: { label: string; onClick: () => void } }) {
  return (
    <div className="space-y-3 p-4 text-subhead" data-testid="detail-empty">
      <p className="text-muted-foreground">{children}</p>
      {action && (
        <button type="button" onClick={action.onClick} className="min-h-11 rounded-md bg-bg-fill px-4 font-semibold text-primary hover:bg-muted">
          {action.label}
        </button>
      )}
    </div>
  );
}

/**
 * Detail zu einem angetippten Block: Signalweg, Planseite, Bauteil mit Befundkarte, Schrankfoto oder
 * Fehlereintrag. Ab 1024 px die rechte Spalte, darunter eine eigene Ebene mit "Zurück".
 */
export function DetailPane({
  detail,
  machine,
  map,
  referencedTags,
  onOpenDetail,
  onClose,
  onGoToAufbau,
  onMachineChanged,
}: {
  detail: DetailRef;
  machine: MachineDetail;
  map: MachineMap | null | undefined;
  referencedTags: string[];
  onOpenDetail: (detail: DetailRef) => void;
  onClose: () => void;
  onGoToAufbau: (tab: AufbauTab) => void;
  onMachineChanged: () => void;
}) {
  if (detail.kind === "plan") {
    // Die Seitenansicht bringt Kopf, Schliessen und Esc selbst mit; angedockt ab 1024 px, sonst Vollbild.
    return <PageViewer target={detail.target} onClose={onClose} docked />;
  }

  let title: string = TITLES[detail.kind];
  let body: ReactNode;
  if (detail.kind === "signal") {
    title = `Signalweg ${detail.tag}`;
    // Signalweg im Vollbild (Figma): die Ansicht bringt ihren Kopf mit "‹ Störfall" selbst mit
    if (machine.source_id) {
      return (
        <PaneFrame title={title} onClose={onClose} kind="signal" bare wide>
          <SignalView sourceId={machine.source_id} tag={detail.tag} variant="auto" onOpenDetail={onOpenDetail} onClose={onClose} />
        </PaneFrame>
      );
    }
    body = (
      <Empty action={{ label: "Dokumente verknüpfen", onClick: () => onGoToAufbau("dokumente") }}>Keine Dokumentation verknüpft, deshalb gibt es keinen Signalweg.</Empty>
    );
  } else if (detail.kind === "part") {
    return (
      <PartPane key={detail.tag} tag={detail.tag} machine={machine} map={map} onOpenDetail={onOpenDetail} onClose={onClose} onGoToAufbau={onGoToAufbau} />
    );
  } else if (detail.kind === "cabinet") {
    const cabinet = machine.cabinets.find((c) => c.id === detail.cabinetId);
    if (cabinet) title = cabinet.title;
    body = cabinet ? (
      <CabinetDetail key={cabinet.id} cabinet={cabinet} hotspotId={detail.hotspotId ?? null} referencedTags={referencedTags} onOpenDetail={onOpenDetail} onChanged={onMachineChanged} />
    ) : (
      <Empty>Quelle wurde entfernt: dieses Schaltschrankfoto gibt es nicht mehr.</Empty>
    );
  } else {
    const own = machine.faults.find((f) => f.id === detail.faultId);
    const other = own ? undefined : knownFault(detail.faultId);
    const fault = own ?? other?.fault;
    if (fault?.code) title = `Fehlereintrag ${fault.code}`;
    body = fault ? (
      <FaultDetail fault={fault} otherMachine={other?.machineName ?? null} onOpenDetail={onOpenDetail} onShowList={() => onGoToAufbau("fehler")} />
    ) : (
      <Empty action={{ label: "Fehlerliste öffnen", onClick: () => onGoToAufbau("fehler") }}>Quelle wurde entfernt: diesen Fehlereintrag gibt es nicht mehr.</Empty>
    );
  }

  return (
    <PaneFrame title={title} onClose={onClose} kind={detail.kind}>
      {body}
    </PaneFrame>
  );
}

/**
 * Rahmen des Details: am Handy eine Nav-Leiste mit "‹ Zurück", am PC die rechte Spalte mit "Schließen" (Figma).
 * bare: die Ansicht bringt ihren Kopf selbst mit; wide: nimmt am PC den Platz des Chats ein (Signalweg im Vollbild).
 */
function PaneFrame({
  title,
  onClose,
  kind,
  children,
  footer,
  bare = false,
  wide = false,
}: {
  title: ReactNode;
  onClose: () => void;
  kind: string;
  children: ReactNode;
  footer?: ReactNode;
  bare?: boolean;
  wide?: boolean;
}) {
  return (
    <aside
      className={cn("flex min-h-0 w-full flex-1 flex-col bg-card lg:border-l-[0.5px] lg:border-border", wide ? "bg-background" : cn("lg:flex-none", DETAIL_WIDTH))}
      aria-label="Detail"
      data-testid="detail-pane"
      data-detail={kind}
    >
      {!bare && (
        <header className="flex min-h-[52px] items-center gap-1 border-b-[0.5px] border-border bg-bg-bar px-1 py-1 backdrop-blur-bar lg:px-3">
          <button type="button" onClick={onClose} className="flex min-h-11 shrink-0 items-center rounded-md pr-1.5 text-body text-primary hover:bg-bg-fill lg:hidden" aria-label="Zurück">
            <ChevronLeft className="size-6" aria-hidden />
            <span aria-hidden>Zurück</span>
          </button>
          <h2 className="min-w-0 flex-1 truncate px-1 text-center text-headline lg:text-left">{title}</h2>
          <button type="button" onClick={onClose} className="hidden min-h-11 shrink-0 rounded-md px-2 text-body text-primary hover:bg-bg-fill lg:block" aria-label="Detail schließen">
            <span aria-hidden>Schließen</span>
          </button>
        </header>
      )}
      <div className="relative flex min-h-0 flex-1 flex-col overflow-y-auto">{children}</div>
      {footer && <footer className="flex flex-wrap gap-2 border-t-[0.5px] border-border bg-bg-bar px-4 py-3 backdrop-blur-bar">{footer}</footer>}
    </aside>
  );
}

/** Inhalt des Bauteil-Sheets mit Befundkarte, in der Detailspalte statt als Dialog. */
function PartPane({
  tag,
  machine,
  map,
  onOpenDetail,
  onClose,
  onGoToAufbau,
}: {
  tag: string;
  machine: MachineDetail;
  map: MachineMap | null | undefined;
  onOpenDetail: (detail: DetailRef) => void;
  onClose: () => void;
  onGoToAufbau: (tab: AufbauTab) => void;
}) {
  const data = usePartData(tag, machine, map);
  const actions: PartActions = {
    onOpenPage: (target) => onOpenDetail({ kind: "plan", target }),
    onOpenPart: (next) => onOpenDetail({ kind: "part", tag: next }),
    onShowPhoto: (cabinetId, hotspotId) => onOpenDetail({ kind: "cabinet", cabinetId, hotspotId }),
    onShowSignal: (next) => onOpenDetail({ kind: "signal", tag: next }),
    onUploadDatasheet: () => onGoToAufbau("dokumente"),
  };
  return (
    <PaneFrame title={`Bauteil ${tag}`} onClose={onClose} kind="part" footer={<PartFooter tag={tag} data={data} actions={actions} />}>
      <div className="space-y-5 px-5 py-5" data-testid="part-detail">
        <div>
          <PartHeaderChips tag={tag} data={data} />
          <p className="mt-4 text-title-3">{data.title || `Bauteil ${tag}`}</p>
          <p className="mt-0.5 text-footnote text-muted-foreground">{partDescription(data)}</p>
        </div>
        <PartBody tag={tag} data={data} actions={actions} />
      </div>
    </PaneFrame>
  );
}

/** Schrankfoto mit Rahmen; die Bauteile darunter sind die Bedienelemente (Rahmen sind fuer Finger zu klein). */
function CabinetDetail({
  cabinet,
  hotspotId,
  referencedTags,
  onOpenDetail,
  onChanged,
}: {
  cabinet: Cabinet;
  hotspotId: string | null;
  referencedTags: string[];
  onOpenDetail: (detail: DetailRef) => void;
  onChanged: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const active = cabinet.hotspots.find((h) => h.id === hotspotId) ?? null;
  const ratio = cabinet.width > 0 && cabinet.height > 0 ? `${cabinet.width} / ${cabinet.height}` : "4 / 3";
  return (
    <div className="space-y-3 p-3" data-testid="cabinet-detail">
      <div className="relative w-full overflow-hidden rounded-md bg-bg-fill" style={{ aspectRatio: ratio }}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={plant.cabinetImageUrl(cabinet.id)} alt={`${cabinet.title}${active ? `: ${active.tag} markiert` : ""}`} className="absolute inset-0 size-full object-contain" />
        {cabinet.hotspots.map((h) => {
          const isActive = h.id === active?.id;
          const referenced = matchesAny(h.tag, referencedTags);
          return (
            <span
              key={h.id}
              aria-hidden
              className={cn(
                "absolute rounded-sm",
                isActive ? "border-[3px] border-signal bg-signal/20 shadow-[0_0_0_1px_var(--signal-foreground)]" : referenced ? "border-2 border-signal" : "border border-white/80 shadow-[0_0_0_1px_rgba(0,0,0,0.4)]",
              )}
              style={{ left: `${h.x * 100}%`, top: `${h.y * 100}%`, width: `${h.w * 100}%`, height: `${h.h * 100}%` }}
            />
          );
        })}
      </div>
      {active && !active.confirmed && <p className="text-footnote text-muted-foreground">Markierung unbestätigt: vorgeschlagen, noch nicht geprüft.</p>}
      <ul className="flex flex-wrap gap-1.5" aria-label="Markierte Bauteile">
        {cabinet.hotspots.map((h) => (
          <li key={h.id}>
            <PartChip tag={h.tag} label={h.label} referenced={matchesAny(h.tag, referencedTags)} active={h.id === active?.id} onClick={() => onOpenDetail({ kind: "part", tag: h.tag })} className="min-h-11" />
          </li>
        ))}
      </ul>
      <button type="button" onClick={() => setEditing(true)} className="inline-flex min-h-11 items-center gap-1.5 rounded-md bg-bg-fill px-4 text-subhead font-semibold text-primary hover:bg-muted">
        <Pencil className="size-4" aria-hidden /> Groß ansehen und Markierung korrigieren
      </button>
      {editing && <CabinetLightbox cabinet={cabinet} hotspotId={active?.id ?? null} referencedTags={referencedTags} onClose={() => setEditing(false)} onChanged={onChanged} />}
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="space-y-0.5">
      <dt className="text-footnote font-semibold text-muted-foreground uppercase">{label}</dt>
      <dd className="text-body whitespace-pre-wrap">{children}</dd>
    </div>
  );
}

/** Fehlereintrag mit Ursache und Behebung; ein Treffer von einer anderen Maschine ist als Erfahrung benannt. */
function FaultDetail({ fault, otherMachine, onOpenDetail, onShowList }: { fault: Fault; otherMachine: string | null; onOpenDetail: (detail: DetailRef) => void; onShowList: () => void }) {
  return (
    <div className="space-y-4 p-4" data-testid="fault-detail">
      {otherMachine && (
        <p className="rounded-md bg-bg-grouped px-3 py-2 text-footnote text-muted-foreground">
          Erfahrung von {otherMachine}: kein Beleg für diese Maschine.
        </p>
      )}
      <dl className="space-y-3">
        <Field label="Symptom">{fault.symptom || "–"}</Field>
        <Field label="Ursache">{fault.cause || "Nicht eingetragen."}</Field>
        <Field label="Behebung">{fault.fix || "Nicht eingetragen."}</Field>
        {fault.doc_ref && <Field label="Fundstelle">{fault.doc_ref}</Field>}
      </dl>
      {fault.tags.length > 0 && (
        <ul className="flex flex-wrap gap-1.5" aria-label="Bauteile des Fehlereintrags">
          {fault.tags.map((tag) => (
            <li key={tag}>
              <PartChip tag={tag} onClick={otherMachine ? undefined : () => onOpenDetail({ kind: "part", tag })} className="min-h-11" />
            </li>
          ))}
        </ul>
      )}
      {!otherMachine && (
        <button type="button" onClick={onShowList} className="min-h-11 rounded-md bg-bg-fill px-4 text-subhead font-semibold text-primary hover:bg-muted">
          In der Fehlerliste zeigen
        </button>
      )}
    </div>
  );
}

