"use client";

import { FileText, ImageUp, PenLine } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, layout as layoutApi, type MachineDetail, type SourceDocument } from "@/lib/api";

/** Noch keine Draufsicht: Skizze hochladen, Dokumentseite waehlen oder leer mit Massen beginnen. */
export function LayoutEmptyState({ machine, onCreated }: { machine: MachineDetail; onCreated: () => void }) {
  const [width, setWidth] = useState("");
  const [depth, setDepth] = useState("");
  const [documents, setDocuments] = useState<SourceDocument[]>([]);
  const [documentId, setDocumentId] = useState("");
  const [page, setPage] = useState("1");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!machine.source_id) return;
    api
      .listDocuments(machine.source_id)
      .then((docs) => setDocuments(docs.filter((d) => d.filename.toLowerCase().endsWith(".pdf"))))
      .catch(() => setDocuments([]));
  }, [machine.source_id]);

  const sizes = () => ({ width_mm: Number(width) || 0, depth_mm: Number(depth) || 0, scale_note: "" });

  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    try {
      await action();
      onCreated();
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid h-full place-items-center bg-card p-6">
      <div className="w-full max-w-2xl">
        <h2 className="font-mono text-lg font-semibold uppercase tracking-[0.04em]">Draufsicht anlegen</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Die Draufsicht zeigt Baugruppen und Feldgeräte in mm. Quelle ist eine Skizze aus den Unterlagen (Aufstellungsplan, Scan, Foto)
          oder deine eigene Zeichnung.
        </p>

        <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
          <label>
            <span className="text-muted-foreground">Breite der Grundfläche (mm, optional)</span>
            <Input type="number" min={0} value={width} onChange={(e) => setWidth(e.target.value)} placeholder="7400" className="font-mono" />
          </label>
          <label>
            <span className="text-muted-foreground">Tiefe (mm, optional)</span>
            <Input type="number" min={0} value={depth} onChange={(e) => setDepth(e.target.value)} placeholder="2600" className="font-mono" />
          </label>
        </div>

        <div className="mt-4 grid gap-3 md:grid-cols-3">
          <label className="flex cursor-pointer flex-col gap-2 border border-line bg-background p-4 hover:border-primary">
            <ImageUp className="size-5 text-primary" />
            <span className="font-medium">Skizze hochladen</span>
            <span className="text-xs text-muted-foreground">PNG, JPG oder WebP</span>
            <input
              type="file"
              accept="image/png,image/jpeg,image/webp"
              className="hidden"
              disabled={busy}
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) run(async () => {
                  await layoutApi.put(machine.id, { ...sizes(), document_id: null, page: null });
                  await layoutApi.uploadImage(machine.id, file);
                });
              }}
            />
          </label>

          <div className="flex flex-col gap-2 border border-line bg-background p-4">
            <FileText className="size-5 text-primary" />
            <span className="font-medium">Seite aus der Doku</span>
            {documents.length === 0 ? (
              <span className="text-xs text-muted-foreground">
                {machine.source_id ? "Keine PDF-Dokumente in der Wissensquelle." : "Erst eine Wissensquelle verknüpfen."}
              </span>
            ) : (
              <>
                <select value={documentId} onChange={(e) => setDocumentId(e.target.value)} className="h-8 border border-border bg-card px-2 text-xs">
                  <option value="">Dokument wählen …</option>
                  {documents.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.filename}
                    </option>
                  ))}
                </select>
                <div className="flex gap-2">
                  <Input type="number" min={1} value={page} onChange={(e) => setPage(e.target.value)} className="h-8 w-20 font-mono" aria-label="Seite" />
                  <Button
                    size="sm"
                    disabled={!documentId || busy}
                    onClick={() => run(() => layoutApi.put(machine.id, { ...sizes(), document_id: documentId, page: Number(page) || 1 }))}
                  >
                    Übernehmen
                  </Button>
                </div>
              </>
            )}
          </div>

          <button
            disabled={busy}
            onClick={() => run(() => layoutApi.put(machine.id, { ...sizes(), document_id: null, page: null }))}
            className="flex flex-col items-start gap-2 border border-line bg-background p-4 text-left hover:border-primary"
          >
            <PenLine className="size-5 text-primary" />
            <span className="font-medium">Leer beginnen</span>
            <span className="text-xs text-muted-foreground">Teile selbst mit Rechteck und Kreis zeichnen</span>
          </button>
        </div>
      </div>
    </div>
  );
}
