"use client";

import { Camera, FileText, Route, Upload, X } from "lucide-react";
import { Dialog as DialogPrimitive } from "radix-ui";
import { useEffect, useRef, useState, type ReactNode } from "react";

import { CitationChip } from "@/components/chat/CitationChip";
import { PartChip } from "@/components/chat/PartChip";
import type { PageTarget } from "@/components/PageViewer";
import { Dialog, DialogDescription, DialogOverlay, DialogPortal, DialogTitle } from "@/components/ui/dialog";
import { factCard, plant, signalPath, type Cabinet, type FactCardData, type Hotspot, type MachineDetail, type MachineMap, type SignalPathData, type TagLookup } from "@/lib/api";
import { sameTag } from "@/lib/faults";
import { zoneOf, zoneTitle } from "@/lib/model";
import { relatedParts } from "@/lib/parts";
import { cn } from "@/lib/utils";

const DATASHEET_TYPES = new Set(["manual", "other", "datasheet"]);
const MAX_VALUES = 6;

function Section({ title, note, children }: { title: string; note?: string; children: ReactNode }) {
  return (
    <section className="space-y-1.5">
      <h3 className="font-mono text-[11px] font-semibold uppercase tracking-[0.06em] text-muted-foreground">
        {title}
        {note && <span className="ml-2 font-sans text-[11px] font-normal normal-case tracking-normal">{note}</span>}
      </h3>
      {children}
    </section>
  );
}

export interface PartActions {
  onOpenPage: (target: PageTarget) => void;
  onOpenPart: (tag: string) => void;
  onShowPhoto: (cabinetId: string, hotspotId: string) => void;
  onShowSignal: (tag: string) => void;
  onUploadDatasheet: () => void;
}

/** Datenblatt eines Bauteils aus Befundkarte (Kennzeichen-Index), Fundstellen und Signalweg; ohne Modellaufruf. */
export function usePartData(tag: string, machine: MachineDetail, map: MachineMap | null | undefined) {
  const [card, setCard] = useState<FactCardData | null>(null);
  const [lookup, setLookup] = useState<TagLookup | null>(null);
  const [path, setPath] = useState<SignalPathData | null>(null);
  const [loadedFor, setLoadedFor] = useState<string | null>(null);
  const loading = tag !== loadedFor;
  const sourceId = machine.source_id;

  useEffect(() => {
    if (!tag) return;
    let cancelled = false;
    const sources = sourceId ? [sourceId] : [];
    Promise.all([
      factCard(tag, sources).catch(() => null),
      sourceId ? plant.lookupTag(machine.id, tag).catch(() => null) : Promise.resolve(null),
      sourceId ? signalPath(tag, sourceId).catch(() => null) : Promise.resolve(null),
    ]).then(([c, l, p]) => {
      if (cancelled) return;
      setCard(c);
      setLookup(l);
      setPath(p);
      setLoadedFor(tag);
    });
    return () => {
      cancelled = true;
    };
  }, [tag, machine.id, sourceId]);

  const zone = zoneOf(map, tag);
  const mapParts = map?.zones.flatMap((z) => z.parts) ?? [];
  const part = mapParts.find((p) => sameTag(p.tag, tag)) ?? null;
  const title = card?.title || part?.label || lookup?.bom_line?.split("|").map((c) => c.trim()).filter(Boolean)[1] || "";
  const hits = lookup?.hits ?? [];
  const datasheet = hits.find((h) => DATASHEET_TYPES.has(h.doc_type) && h.page && h.filename.toLowerCase().endsWith(".pdf")) ?? null;
  const photos: { cabinet: Cabinet; hotspot: Hotspot }[] = machine.cabinets.flatMap((c) => c.hotspots.filter((h) => sameTag(h.tag, tag)).map((h) => ({ cabinet: c, hotspot: h })));
  // Verb aus der Art, die das Backend je nach Lesart der Kennbuchstaben bestimmt (Issue #99)
  const related = relatedParts(path, tag, (t) => mapParts.find((p) => sameTag(p.tag, t))?.verb ?? "hängt an");
  const rows = (card?.rows ?? []).filter((r) => r.values.length > 0);
  return { card, lookup, loading, zone, part, title, hits, datasheet, photos, related, rows };
}

type PartData = ReturnType<typeof usePartData>;

export function PartHeaderChips({ tag, data }: { tag: string; data: PartData }) {
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <PartChip tag={tag} referenced />
      {data.zone && <span className="rounded-md bg-secondary px-1.5 py-0.5 font-mono text-[11px] text-muted-foreground">{zoneTitle(data.zone)}</span>}
    </div>
  );
}

export function partDescription(data: PartData): string {
  return `${data.part?.kind ? `${data.part.kind} · ` : ""}${data.loading ? "Lade Datenblatt …" : `${data.hits.length} Fundstellen in der Doku`}`;
}

/** Inhalt des Datenblatts: Foto, Datenblatt, Befundkarte, verbundene Bauteile, Belege. */
export function PartBody({ tag, data, actions }: { tag: string; data: PartData; actions: PartActions }) {
  const { photos, datasheet, lookup, rows, related, hits, loading, card } = data;
  return (
    <div className="space-y-5 text-sm">
      {photos.length > 0 && (
        <Section title="Im Schaltschrank">
          <ul className="flex gap-3 overflow-x-auto" aria-label="Fotos mit diesem Bauteil">
            {photos.map(({ cabinet, hotspot }) => (
              <li key={hotspot.id} className="w-44 shrink-0">
                <button type="button" onClick={() => actions.onShowPhoto(cabinet.id, hotspot.id)} className="block w-full overflow-hidden rounded-xl border border-border text-left hover:border-primary" aria-label={`${cabinet.title}: ${tag} im Foto zeigen`}>
                  <span className="relative block aspect-[4/3] w-full overflow-hidden bg-secondary">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={plant.cabinetImageUrl(cabinet.id)} alt="" className="absolute inset-0 size-full object-cover" loading="lazy" />
                    <span aria-hidden className="absolute rounded-sm border-2 border-signal" style={{ left: `${hotspot.x * 100}%`, top: `${hotspot.y * 100}%`, width: `${hotspot.w * 100}%`, height: `${hotspot.h * 100}%` }} />
                  </span>
                  <span className="block truncate px-2 py-1 text-[11px] text-muted-foreground">{cabinet.title}{!hotspot.confirmed && " · unbestätigt"}</span>
                </button>
              </li>
            ))}
          </ul>
        </Section>
      )}

      <Section title="Datenblatt">
        {datasheet ? (
          <button
            type="button"
            onClick={() => actions.onOpenPage({ documentId: datasheet.document_id, filename: datasheet.filename, page: datasheet.page ?? undefined, label: `${datasheet.filename} S. ${datasheet.page}`, tag })}
            className="flex min-h-11 w-full items-center gap-2 rounded-xl border border-border p-2.5 text-left hover:border-primary"
            data-testid="datasheet-open"
          >
            <FileText className="size-4 shrink-0 text-primary" />
            <span className="min-w-0 flex-1">
              <span className="block truncate font-medium">{datasheet.filename}</span>
              <span className="block text-xs text-muted-foreground">Seite {datasheet.page}</span>
            </span>
            <span className="text-xs font-medium text-primary">Öffnen</span>
          </button>
        ) : (
          <div className="rounded-xl border border-dashed border-border p-2.5" data-testid="datasheet-missing">
            <p className="text-muted-foreground">Kein Datenblatt verknüpft{lookup?.bom_line ? "; Stücklistenzeile vorhanden" : ""}.</p>
            <button type="button" onClick={actions.onUploadDatasheet} className="mt-1.5 inline-flex min-h-11 items-center gap-1.5 text-xs font-medium text-primary hover:underline">
              <Upload className="size-3.5" /> Datenblatt hochladen
            </button>
          </div>
        )}
        {lookup?.bom_line && <p className="truncate font-mono text-[11px] text-muted-foreground" title={lookup.bom_line}>{lookup.bom_line}</p>}
      </Section>

      {rows.length > 0 && (
        <Section title="Befundkarte" note="aus dem Dokument-Index">
          <dl className="grid grid-cols-[max-content_1fr] gap-x-3 gap-y-1.5 text-[13px]" data-testid="part-fact-card">
            {rows.map((row) => (
              <div key={row.label} className="contents">
                <dt className="text-muted-foreground">{row.label}</dt>
                <dd className="flex flex-wrap gap-1">
                  {row.values.slice(0, MAX_VALUES).map((value) => {
                    const pdf = value.filename?.toLowerCase().endsWith(".pdf");
                    const open = value.document_id && pdf ? () => actions.onOpenPage({ documentId: value.document_id!, filename: value.filename!, page: value.page ?? undefined, reference: value.ref, label: `${row.label} ${value.text}`, tag }) : undefined;
                    return <CitationChip key={value.text} label={value.text} onClick={open} title={value.filename ?? undefined} />;
                  })}
                  {row.values.length > MAX_VALUES && <span className="text-[11px] text-muted-foreground">+{row.values.length - MAX_VALUES}</span>}
                </dd>
              </div>
            ))}
          </dl>
        </Section>
      )}

      {related.length > 0 && (
        <Section title="Verbundene Bauteile">
          <ul className="flex flex-wrap gap-1.5" aria-label="Verbundene Bauteile">
            {related.map((r) => (
              <li key={r.tag} className="flex items-center gap-1">
                <span className="text-[11px] text-muted-foreground">{r.verb}</span>
                <PartChip tag={r.tag} onClick={() => actions.onOpenPart(r.tag)} className="min-h-11" />
              </li>
            ))}
          </ul>
        </Section>
      )}

      {hits.length > 0 && (
        <Section title="Belege">
          <ul className="space-y-1">
            {hits.slice(0, 8).map((hit, i) => {
              const pdf = hit.filename.toLowerCase().endsWith(".pdf") && hit.page;
              return (
                <li key={`${hit.document_id}-${hit.page}-${i}`} className="flex items-baseline gap-2 text-[13px]">
                  {pdf ? (
                    <CitationChip label={`${hit.filename} S. ${hit.page}`} onClick={() => actions.onOpenPage({ documentId: hit.document_id, filename: hit.filename, page: hit.page!, tag })} />
                  ) : (
                    <span className="font-mono text-[11px] text-muted-foreground">{hit.filename}</span>
                  )}
                  <span className="min-w-0 truncate text-muted-foreground">{hit.context}</span>
                </li>
              );
            })}
          </ul>
        </Section>
      )}
      {!loading && hits.length === 0 && !card && <p className="text-muted-foreground">In der Doku dieser Maschine nichts zu {tag} gefunden. Unter „Dokumente“ lässt sich weitere Doku verknüpfen.</p>}
    </div>
  );
}

export function PartFooter({ tag, data, actions }: { tag: string; data: PartData; actions: PartActions }) {
  const first = data.photos[0];
  return (
    <>
      {first && (
        <button type="button" onClick={() => actions.onShowPhoto(first.cabinet.id, first.hotspot.id)} className="inline-flex min-h-11 items-center gap-1.5 rounded-lg bg-signal px-3 py-1.5 text-sm font-medium text-signal-foreground" data-testid="show-in-photo">
          <Camera className="size-4" /> Im Foto zeigen
        </button>
      )}
      <button type="button" onClick={() => actions.onShowSignal(tag)} className="inline-flex min-h-11 items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-sm hover:border-primary">
        <Route className="size-4" /> Signalweg
      </button>
    </>
  );
}

/**
 * Bauteil-Datenblatt (ux-spec §3.3): rechter Drawer ab 768 px, Bottom Sheet am Handy. Radix Dialog liefert
 * Fokus-Falle, Esc und Fokus-Rueckgabe; ein Wisch nach unten am Griff schliesst das Sheet. Im Bereich Stoerfaelle
 * steht derselbe Inhalt in der Detailspalte (PartBody, PartFooter).
 */
export function PartSheet({
  tag,
  machine,
  map,
  onClose,
  ...actions
}: {
  tag: string | null;
  machine: MachineDetail;
  map: MachineMap | null | undefined;
  onClose: () => void;
} & PartActions) {
  const swipeStart = useRef<number | null>(null);
  const data = usePartData(tag ?? "", machine, map);

  // Fokus kehrt zum ausloesenden Chip zurueck, auch wenn das Sheet beim Schliessen sofort abgebaut wird
  useEffect(() => {
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    return () => {
      opener?.focus();
    };
  }, []);

  if (!tag) return null;

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogPortal>
        <DialogOverlay className="bg-black/40" />
        <DialogPrimitive.Content
          data-testid="part-sheet"
          className={cn(
            "fixed z-50 flex flex-col bg-card text-card-foreground shadow-2xl outline-none",
            "inset-x-0 bottom-0 max-h-[85vh] rounded-t-2xl duration-250 data-open:animate-in data-open:slide-in-from-bottom data-closed:animate-out data-closed:slide-out-to-bottom",
            "md:inset-y-0 md:right-0 md:left-auto md:h-full md:max-h-none md:w-[440px] md:max-w-[92vw] md:rounded-none md:border-l md:border-border md:data-open:slide-in-from-right md:data-closed:slide-out-to-right",
          )}
          onPointerDown={(e) => {
            if ((e.target as HTMLElement).dataset.handle) swipeStart.current = e.clientY;
          }}
          onPointerUp={(e) => {
            if (swipeStart.current !== null && e.clientY - swipeStart.current > 80) onClose();
            swipeStart.current = null;
          }}
        >
          <div className="flex justify-center py-2 md:hidden" data-handle="true" aria-hidden>
            <span className="h-1.5 w-12 rounded-full bg-border" data-handle="true" />
          </div>
          <header className="flex items-start gap-2 border-b border-border px-4 py-3">
            <div className="min-w-0 flex-1">
              <PartHeaderChips tag={tag} data={data} />
              <DialogTitle className="mt-1.5 text-[16px] font-semibold leading-tight">{data.title || `Bauteil ${tag}`}</DialogTitle>
              <DialogDescription className="text-xs text-muted-foreground">{partDescription(data)}</DialogDescription>
            </div>
            <DialogPrimitive.Close className="grid size-11 place-items-center rounded-md text-muted-foreground hover:bg-secondary hover:text-foreground" aria-label="Datenblatt schließen">
              <X className="size-4" />
            </DialogPrimitive.Close>
          </header>

          <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
            <PartBody tag={tag} data={data} actions={actions} />
          </div>

          <footer className="flex flex-wrap gap-2 border-t border-border px-4 py-3">
            <PartFooter tag={tag} data={data} actions={actions} />
          </footer>
        </DialogPrimitive.Content>
      </DialogPortal>
    </Dialog>
  );
}
