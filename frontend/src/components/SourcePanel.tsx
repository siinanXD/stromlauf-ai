"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { api, DOC_TYPE_LABELS, type DocType, type DocTypeDetection, type SourceDocument } from "@/lib/api";
import type { PageTarget } from "@/components/PageViewer";

/** Datei mit erkanntem Typ, wartet auf Bestätigung im Panel. */
interface PendingFile {
  file: File;
  docType: DocType;
  detection: DocTypeDetection | null;
}

const STATUS_LABELS: Record<SourceDocument["status"], string> = {
  pending: "Wartet",
  processing: "Verarbeitung",
  ready: "Bereit",
  failed: "Fehler",
};

export function SourcePanel({
  sourceId,
  onChanged,
  onOpenPage,
}: {
  sourceId: string;
  onChanged: () => void;
  onOpenPage: (target: PageTarget) => void;
}) {
  const [documents, setDocuments] = useState<SourceDocument[]>([]);
  const [docType, setDocType] = useState<DocType>("auto");
  const [vision, setVision] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [pending, setPending] = useState<PendingFile[]>([]);
  const [detecting, setDetecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  const reload = useCallback(async () => {
    try {
      setDocuments(await api.listDocuments(sourceId));
    } catch (err) {
      setError((err as Error).message);
    }
  }, [sourceId]);

  useEffect(() => {
    let cancelled = false;
    api
      .listDocuments(sourceId)
      .then((result) => !cancelled && setDocuments(result))
      .catch((err) => !cancelled && setError(err.message));
    return () => {
      cancelled = true;
    };
  }, [sourceId]);

  // Solange etwas verarbeitet wird, Status nachladen
  const busy = documents.some((d) => d.status === "pending" || d.status === "processing");
  useEffect(() => {
    if (!busy) return;
    const timer = setInterval(reload, 2000);
    return () => clearInterval(timer);
  }, [busy, reload]);

  async function upload(items: { file: File; docType: DocType }[]) {
    if (!items.length) return;
    setUploading(true);
    setError(null);
    try {
      for (const { file, docType: type } of items) {
        await api.uploadDocument(sourceId, file, type, vision);
      }
      setPending([]);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setUploading(false);
      if (fileInput.current) fileInput.current.value = "";
      await reload();
      onChanged();
    }
  }

  /** Bei „Automatisch erkennen“ erst den Vorschlag je Datei zeigen; bei festem Typ direkt hochladen. */
  async function choose(files: FileList | null) {
    if (!files?.length) return;
    const list = Array.from(files);
    if (docType !== "auto") {
      await upload(list.map((file) => ({ file, docType })));
      return;
    }
    setDetecting(true);
    setError(null);
    const detected = await Promise.all(
      list.map(async (file): Promise<PendingFile> => {
        try {
          const detection = await api.detectDocType(file);
          return { file, docType: detection.doc_type, detection };
        } catch {
          return { file, docType: "other", detection: null };
        }
      }),
    );
    setPending(detected);
    setDetecting(false);
    if (fileInput.current) fileInput.current.value = "";
  }

  async function remove(document: SourceDocument) {
    if (!confirm(`„${document.filename}“ aus der Wissensquelle löschen?`)) return;
    await api.deleteDocument(document.id).catch((err) => setError(err.message));
    await reload();
    onChanged();
  }

  return (
    <div className="space-y-2 border-t border-border bg-background/60 px-3 py-3 text-sm">
      {documents.length === 0 && <p className="text-muted-foreground">Noch keine Dokumente.</p>}
      {documents.some((d) => d.status === "ready") && (
        <Link href={`/quelle/${sourceId}`} className="inline-block text-xs font-medium text-primary hover:underline">
          Steckbrief: Abdeckung und Lücken →
        </Link>
      )}
      <ul className="space-y-1.5">
        {documents.map((document) => (
          <li key={document.id} className="rounded-lg border border-border bg-card px-2.5 py-2">
            <div className="flex items-start gap-2">
              <button
                className="min-w-0 flex-1 truncate text-left font-medium enabled:hover:text-primary"
                disabled={!document.page_count}
                title={document.page_count ? "Seiten ansehen" : document.filename}
                onClick={() =>
                  onOpenPage({
                    documentId: document.id,
                    filename: document.filename,
                    page: 1,
                    pageCount: document.page_count,
                  })
                }
              >
                {document.filename}
              </button>
              <button
                onClick={() => remove(document)}
                className="shrink-0 text-muted-foreground hover:text-danger"
                aria-label={`${document.filename} löschen`}
              >
                ✕
              </button>
            </div>
            <div className="mt-0.5 flex flex-wrap items-center gap-x-2 text-xs text-muted-foreground">
              <span>{DOC_TYPE_LABELS[document.doc_type] ?? document.doc_type}</span>
              <span
                className={
                  document.status === "ready"
                    ? "text-ok"
                    : document.status === "failed"
                      ? "text-danger"
                      : "animate-pulse text-primary"
                }
              >
                {STATUS_LABELS[document.status]}
              </span>
              {document.progress && <span className="truncate">{document.progress}</span>}
            </div>
            {document.error && (
              <div className="mt-1 flex items-start gap-2 text-xs text-danger">
                <span className="min-w-0 flex-1 break-words">{document.error}</span>
                <button
                  className="shrink-0 underline"
                  onClick={() => api.reingestDocument(document.id).then(reload)}
                >
                  Erneut
                </button>
              </div>
            )}
          </li>
        ))}
      </ul>

      <div className="space-y-2 rounded-lg border border-dashed border-border p-2.5">
        <select
          value={docType}
          onChange={(event) => setDocType(event.target.value as DocType)}
          className="w-full rounded-md border border-border bg-card px-2 py-1.5"
          aria-label="Dokumenttyp"
        >
          {Object.entries(DOC_TYPE_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
        <label className="flex items-start gap-2 text-xs text-muted-foreground">
          <input
            type="checkbox"
            checked={vision}
            onChange={(event) => setVision(event.target.checked)}
            className="mt-0.5 accent-[var(--primary)]"
          />
          <span>
            Vision-Analyse für Schaltplanseiten (PDF). Erkennt Verbindungen im Bild, kostet
            API-Tokens pro Seite.
          </span>
        </label>
        <input
          ref={fileInput}
          type="file"
          multiple
          hidden
          accept=".pdf,.awl,.sdf,.xlsx,.csv,.docx,.pptx,.md,.txt,.html,.png,.jpg,.jpeg,.tif,.tiff"
          onChange={(event) => choose(event.target.files)}
        />
        {pending.length > 0 && (
          <ul className="space-y-1.5" aria-label="Erkannte Dokumenttypen">
            {pending.map((item, index) => (
              <li key={`${item.file.name}-${index}`} className="rounded-md border border-border bg-card px-2 py-1.5">
                <div className="truncate font-medium" title={item.file.name}>
                  {item.file.name}
                </div>
                <select
                  value={item.docType}
                  onChange={(event) =>
                    setPending((current) =>
                      current.map((entry, i) => (i === index ? { ...entry, docType: event.target.value as DocType } : entry)),
                    )
                  }
                  aria-label={`Dokumenttyp für ${item.file.name}`}
                  className="mt-1 w-full rounded-md border border-border bg-background px-2 py-1"
                >
                  {Object.entries(DOC_TYPE_LABELS)
                    .filter(([value]) => value !== "auto")
                    .map(([value, label]) => (
                      <option key={value} value={value}>
                        {label}
                      </option>
                    ))}
                </select>
                <p className="mt-1 text-xs text-muted-foreground">
                  {item.detection
                    ? item.detection.source === "none"
                      ? "Nicht erkannt: bitte Typ wählen."
                      : `Erkannt: ${item.detection.reason}`
                    : "Erkennung fehlgeschlagen: bitte Typ wählen."}
                </p>
              </li>
            ))}
            <li className="flex gap-1.5">
              <button
                onClick={() => upload(pending)}
                disabled={uploading}
                className="flex-1 rounded-md bg-primary px-3 py-1.5 font-medium text-primary-foreground disabled:opacity-50"
              >
                {uploading ? "Lädt hoch …" : `${pending.length} ${pending.length === 1 ? "Datei" : "Dateien"} hochladen`}
              </button>
              <button
                onClick={() => setPending([])}
                disabled={uploading}
                className="rounded-md border border-border px-3 py-1.5 text-muted-foreground hover:text-foreground"
              >
                Abbrechen
              </button>
            </li>
          </ul>
        )}
        {pending.length === 0 && (
          <button
            onClick={() => fileInput.current?.click()}
            disabled={uploading || detecting}
            className="w-full rounded-md bg-primary px-3 py-1.5 font-medium text-primary-foreground disabled:opacity-50"
          >
            {uploading ? "Lädt hoch …" : detecting ? "Erkenne Typ …" : "Dateien wählen"}
          </button>
        )}
      </div>
      {error && <p className="text-xs text-danger">{error}</p>}
    </div>
  );
}
