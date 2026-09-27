"use client";

import { ClipboardList, MessageSquare } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import type { PageTarget } from "@/components/PageViewer";
import { Button } from "@/components/ui/button";
import { api, DOC_TYPE_LABELS, plant, type KnowledgeSource, type MachineDetail, type SourceDocument } from "@/lib/api";

type MachineUpdate = Parameters<typeof plant.updateMachine>[1];

/** Stammdaten, Foto und verknuepfte Wissensquelle der Maschine mit ihren Dokumenten. */
export function DocumentsTab({
  machine,
  sources,
  imageBust,
  onUpdate,
  onUploadImage,
  onOpenPage,
}: {
  machine: MachineDetail;
  sources: KnowledgeSource[];
  imageBust: number;
  onUpdate: (body: MachineUpdate) => void;
  onUploadImage: (file: File | undefined) => void;
  onOpenPage: (target: PageTarget) => void;
}) {
  const [documents, setDocuments] = useState<SourceDocument[]>([]);

  useEffect(() => {
    if (!machine.source_id) return;
    api.listDocuments(machine.source_id).then(setDocuments).catch(() => setDocuments([]));
  }, [machine.source_id]);

  const chatHref = `/werk/maschine/${machine.id}?tab=chat`;

  return (
    <div className="grid gap-6 lg:grid-cols-[320px_minmax(0,1fr)]">
      <div className="space-y-3">
        <label className="group relative block aspect-[4/3] cursor-pointer overflow-hidden border border-line bg-secondary">
          {machine.has_image ? (
            // eslint-disable-next-line @next/next/no-img-element -- Bild kommt vom Backend
            <img src={plant.machineImageUrl(machine.id, imageBust)} alt={machine.name} className="size-full object-cover" />
          ) : (
            <span className="grid size-full place-items-center text-sm text-muted-foreground">Foto der Maschine hochladen</span>
          )}
          <span className="absolute inset-x-0 bottom-0 bg-nav/80 py-1 text-center text-xs text-white opacity-0 group-hover:opacity-100">
            Bild ändern
          </span>
          <input type="file" accept="image/*" className="hidden" onChange={(e) => onUploadImage(e.target.files?.[0])} />
        </label>
        <label className="block text-sm">
          <span className="text-muted-foreground">Name</span>
          <input
            key={machine.name}
            defaultValue={machine.name}
            onBlur={(e) => e.target.value.trim() && e.target.value !== machine.name && onUpdate({ name: e.target.value.trim() })}
            className="h-8 w-full border border-border bg-background px-2"
          />
        </label>
        <label className="block text-sm">
          <span className="text-muted-foreground">Beschreibung</span>
          <textarea
            key={machine.description}
            defaultValue={machine.description}
            placeholder="Aufgabe, Baujahr, Besonderheiten …"
            rows={4}
            onBlur={(e) => e.target.value !== machine.description && onUpdate({ description: e.target.value })}
            className="w-full resize-none border border-border bg-background px-2 py-1.5"
          />
        </label>
      </div>

      <section className="border border-line bg-card">
        <div className="flex flex-wrap items-center gap-3 border-b border-line px-4 py-3 text-sm">
          <span className="font-mono text-sm font-semibold uppercase tracking-[0.06em]">Wissensquelle</span>
          <select
            value={machine.source_id ?? ""}
            onChange={(e) => (e.target.value ? onUpdate({ source_id: e.target.value }) : onUpdate({ clear_source: true }))}
            className="h-8 border border-border bg-background px-2"
          >
            <option value="">keine Wissensquelle</option>
            {sources.map((source) => (
              <option key={source.id} value={source.id}>
                {source.name} ({source.document_count})
              </option>
            ))}
          </select>
          {machine.source_id && (
            <Button size="sm" variant="outline" className="ml-auto" asChild>
              <Link href={`/quelle/${machine.source_id}`}>
                <ClipboardList className="size-3.5" />
                Steckbrief
              </Link>
            </Button>
          )}
          <Button size="sm" className={machine.source_id ? "" : "ml-auto"} asChild>
            <Link href={chatHref}>
              <MessageSquare className="size-3.5" />
              Chat zu dieser Maschine
            </Link>
          </Button>
        </div>
        {!machine.source_id ? (
          <p className="px-4 py-6 text-sm text-muted-foreground">
            Wissensquelle wählen, damit Draufsicht, Schaltschrank und Chat auf Stromlaufplan, Stückliste und SPS-Programm zugreifen.
          </p>
        ) : (
          <ul>
            {documents.map((doc) => (
              <li key={doc.id} className="flex items-center gap-3 border-b border-border px-4 py-2 text-sm last:border-b-0">
                <span className="w-32 shrink-0 text-xs text-muted-foreground">{DOC_TYPE_LABELS[doc.doc_type]}</span>
                <span className="min-w-0 flex-1 truncate font-mono text-[13px]">{doc.filename}</span>
                {doc.page_count ? (
                  <button
                    className="text-xs text-primary hover:underline"
                    onClick={() => onOpenPage({ documentId: doc.id, filename: doc.filename, page: 1, pageCount: doc.page_count })}
                  >
                    {doc.page_count} Seiten ansehen
                  </button>
                ) : (
                  <span className="text-xs text-muted-foreground">{doc.status}</span>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
