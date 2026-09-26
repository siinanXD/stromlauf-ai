"use client";

import { FileText, MessageSquare } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import type { PageTarget } from "@/components/PageViewer";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  DOC_TYPE_LABELS,
  LAYOUT_KINDS,
  layout as layoutApi,
  plant,
  type DocType,
  type Layout,
  type LayoutPart,
  type LayoutPartInput,
  type MachineDetail,
  type TagHit,
  type TagLookup,
} from "@/lib/api";

const FIELD = "h-8 w-full border border-border bg-background px-2 text-[13px]";

function SectionTitle({ children }: { children: React.ReactNode }) {
  return <h3 className="mb-1.5 mt-4 font-mono text-[11px] font-semibold uppercase tracking-[0.06em] text-muted-foreground">{children}</h3>;
}

/** Rechte Spalte der Draufsicht: gewaehltes Teil bearbeiten und alles zeigen, was die Doku dazu weiss. */
export function PartPanel({
  machine,
  layout,
  part,
  onChanged,
  onOpenPage,
  onShowFaults,
}: {
  machine: MachineDetail;
  layout: Layout;
  part: LayoutPart | null;
  onChanged: () => void;
  onOpenPage: (target: PageTarget) => void;
  onShowFaults: (tag: string) => void;
}) {
  const [lookup, setLookup] = useState<TagLookup | null>(null);

  useEffect(() => {
    if (!part?.tag || !machine.source_id) return;
    let cancelled = false;
    plant
      .lookupTag(machine.id, part.tag)
      .then((result) => !cancelled && setLookup(result))
      .catch(() => !cancelled && setLookup(null));
    return () => {
      cancelled = true;
    };
  }, [part?.tag, machine.id, machine.source_id]);

  async function save(body: Partial<LayoutPartInput>) {
    if (!part) return;
    try {
      await layoutApi.updatePart(part.id, body);
    } catch (err) {
      toast.error(`Speichern fehlgeschlagen: ${(err as Error).message}`);
    }
    onChanged();
  }

  async function saveLayout(body: Partial<Pick<Layout, "width_mm" | "depth_mm" | "scale_note">>) {
    try {
      await layoutApi.put(machine.id, {
        width_mm: layout.width_mm,
        depth_mm: layout.depth_mm,
        scale_note: layout.scale_note,
        document_id: layout.document_id,
        page: layout.page,
        ...body,
      });
    } catch (err) {
      toast.error((err as Error).message);
    }
    onChanged();
  }

  const hits = part?.tag && lookup?.tag === part.tag ? lookup.hits : [];
  const faults = part?.tag ? machine.faults.filter((f) => f.tags.some((t) => t.toUpperCase() === part.tag.toUpperCase())) : [];
  const schematicHit = hits.find((h) => h.doc_type === "schematic" && h.page);
  const byType = hits.reduce<Record<string, TagHit[]>>((acc, hit) => {
    (acc[hit.doc_type] ??= []).push(hit);
    return acc;
  }, {});
  const chatHref = `/?${new URLSearchParams({
    ...(machine.source_id ? { source: machine.source_id } : {}),
    ...(part?.tag ? { q: `Was ist ${part.tag} an ${machine.name} und wo finde ich es im Plan?` } : {}),
  })}`;

  return (
    <aside className="flex h-full flex-col border border-line bg-card">
      <div className="bg-nav px-4 py-2.5 font-mono text-xs font-semibold tracking-[0.06em] text-white">
        {part ? "AUSGEWÄHLT" : "DRAUFSICHT"}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-4 pb-4">
        {!part && (
          <>
            <p className="mt-3 text-sm text-muted-foreground">
              Teil in der Draufsicht anklicken, um Stückliste, Klemmen, SPS-Adressen und Fehler dazu zu sehen.
            </p>
            <SectionTitle>Grundfläche</SectionTitle>
            <div className="grid grid-cols-2 gap-2 text-[13px]">
              <label>
                <span className="text-muted-foreground">Breite (mm)</span>
                <Input
                  key={`w${layout.width_mm}`}
                  type="number"
                  min={0}
                  defaultValue={layout.width_mm || ""}
                  onBlur={(e) => Number(e.target.value) !== layout.width_mm && saveLayout({ width_mm: Number(e.target.value) || 0 })}
                  className="font-mono"
                />
              </label>
              <label>
                <span className="text-muted-foreground">Tiefe (mm)</span>
                <Input
                  key={`d${layout.depth_mm}`}
                  type="number"
                  min={0}
                  defaultValue={layout.depth_mm || ""}
                  onBlur={(e) => Number(e.target.value) !== layout.depth_mm && saveLayout({ depth_mm: Number(e.target.value) || 0 })}
                  className="font-mono"
                />
              </label>
              <label className="col-span-2">
                <span className="text-muted-foreground">Maßstab / Hinweis</span>
                <Input
                  key={`s${layout.scale_note}`}
                  defaultValue={layout.scale_note}
                  placeholder="z. B. M 1:50"
                  onBlur={(e) => e.target.value !== layout.scale_note && saveLayout({ scale_note: e.target.value })}
                />
              </label>
            </div>
            <p className="mt-3 text-xs text-muted-foreground">{layout.parts.length} Teile · davon {layout.parts.filter((p) => !p.confirmed).length} Vorschläge</p>
          </>
        )}

        {part && (
          <>
            <div className="mt-3 flex items-start justify-between gap-2">
              <div className="min-w-0">
                <div className="truncate font-mono text-[26px] font-semibold leading-tight text-primary">{part.tag || "ohne BMK"}</div>
                <div className="truncate text-[15px] font-medium">{part.label || part.kind}</div>
              </div>
              {part.confirmed ? (
                <Badge variant="outline" className="gap-1.5 rounded-none">
                  <span className="size-1.5 rounded-full bg-ok" />
                  bestätigt
                </Badge>
              ) : (
                <Button size="sm" variant="outline" className="border-primary text-primary" onClick={() => save({ confirmed: true })}>
                  Vorschlag bestätigen
                </Button>
              )}
            </div>

            <div key={part.id} className="mt-3 grid grid-cols-[96px_1fr] items-center gap-x-3 gap-y-1.5 text-[13px]">
              <span className="text-muted-foreground">BMK</span>
              <input
                defaultValue={part.tag}
                placeholder="-M1"
                onBlur={(e) => e.target.value.trim() !== part.tag && save({ tag: e.target.value.trim() })}
                className={`${FIELD} font-mono`}
              />
              <span className="text-muted-foreground">Bezeichnung</span>
              <input defaultValue={part.label} onBlur={(e) => e.target.value !== part.label && save({ label: e.target.value })} className={FIELD} />
              <span className="text-muted-foreground">Art</span>
              <select value={part.kind} onChange={(e) => save({ kind: e.target.value as LayoutPart["kind"] })} className={FIELD}>
                {LAYOUT_KINDS.map((kind) => (
                  <option key={kind}>{kind}</option>
                ))}
              </select>
              <span className="text-muted-foreground">Form</span>
              <select value={part.shape} onChange={(e) => save({ shape: e.target.value as LayoutPart["shape"] })} className={FIELD}>
                <option value="rect">Rechteck</option>
                <option value="circle">Kreis</option>
              </select>
              <span className="text-muted-foreground">Drehung (°)</span>
              <input
                type="number"
                step={15}
                defaultValue={part.rotation_deg}
                onBlur={(e) => Number(e.target.value) !== part.rotation_deg && save({ rotation_deg: Number(e.target.value) || 0 })}
                className={`${FIELD} font-mono`}
              />
              <span className="text-muted-foreground">Lage (mm)</span>
              <span className="font-mono text-muted-foreground">
                x {Math.round(part.x_mm)} · y {Math.round(part.y_mm)} · {Math.round(part.w_mm)} × {Math.round(part.h_mm)}
              </span>
            </div>

            <SectionTitle>In der Dokumentation</SectionTitle>
            {!machine.source_id ? (
              <p className="text-sm text-muted-foreground">Keine Dokumentation verknüpft. Im Tab „Dokumente“ eine Wissensquelle wählen.</p>
            ) : !part.tag ? (
              <p className="text-sm text-muted-foreground">BMK eintragen, dann erscheinen hier die Fundstellen.</p>
            ) : hits.length === 0 ? (
              <p className="text-sm text-muted-foreground">Keine Fundstellen für {part.tag}.</p>
            ) : (
              <div className="space-y-2 text-[13px]">
                {lookup?.bom_line && <p className="border-l-2 border-primary bg-secondary px-2 py-1">{lookup.bom_line}</p>}
                {Object.entries(byType).map(([docType, list]) => (
                  <div key={docType}>
                    <div className="text-xs font-medium text-muted-foreground">
                      {DOC_TYPE_LABELS[docType as DocType] ?? docType} ({list.length})
                    </div>
                    <ul>
                      {list.slice(0, 3).map((hit, index) => (
                        <li key={`${hit.document_id}-${hit.page}-${index}`} className="flex gap-2 border-b border-border py-1">
                          <span className="min-w-0 flex-1 truncate" title={hit.context}>
                            {hit.context}
                          </span>
                          {hit.page && (
                            <button
                              className="shrink-0 font-mono text-primary hover:underline"
                              onClick={() => onOpenPage({ documentId: hit.document_id, filename: hit.filename, page: hit.page! })}
                            >
                              S. {hit.page}
                            </button>
                          )}
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            )}

            <SectionTitle>Fehler mit {part.tag || "diesem Teil"}</SectionTitle>
            {faults.length === 0 ? (
              <p className="text-sm text-muted-foreground">Keine Einträge in der Fehlerliste.</p>
            ) : (
              <ul className="space-y-1.5">
                {faults.map((fault) => (
                  <li key={fault.id}>
                    <button
                      onClick={() => onShowFaults(part.tag)}
                      className="flex w-full items-center gap-2 border border-border bg-background px-2.5 py-1.5 text-left text-[13px] hover:border-primary"
                    >
                      <span className="size-2 shrink-0 rounded-full bg-danger" />
                      <span className="font-mono">{fault.code}</span>
                      <span className="min-w-0 flex-1 truncate">{fault.symptom}</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </div>

      {part && (
        <div className="flex gap-2 border-t border-border p-3">
          <Button
            className="flex-1"
            disabled={!schematicHit}
            onClick={() => schematicHit && onOpenPage({ documentId: schematicHit.document_id, filename: schematicHit.filename, page: schematicHit.page! })}
          >
            <FileText className="size-4" />
            Im Stromlaufplan öffnen
          </Button>
          <Button variant="outline" className="flex-1 border-line" asChild>
            <Link href={chatHref}>
              <MessageSquare className="size-4" />
              Im Chat fragen
            </Link>
          </Button>
        </div>
      )}
    </aside>
  );
}
