"use client";

import { X } from "lucide-react";
import { useRef, useState } from "react";

import { ausDrop, ausInput, type Abgelegt } from "@/components/ablauf/ordner";
import { cn } from "@/lib/utils";

// Endungen wie ALLOWED_SUFFIXES im Backend (app/api/sources.py)
const ACCEPT = ".pdf,.awl,.scl,.sdf,.xlsx,.csv,.docx,.pptx,.md,.txt,.html,.png,.jpg,.jpeg,.tif,.tiff";

// webkitdirectory fehlt in den React-Typen; als Spread gesetzt.
const ORDNER = { webkitdirectory: "" } as Record<string, string>;

/** Dateien oder Ordner ablegen oder wählen; die Liste zeigt die Pfade und erlaubt das Entfernen einzelner Dateien. */
export function Dropzone({ files, onFiles, disabled = false }: { files: Abgelegt[]; onFiles: (files: Abgelegt[]) => void; disabled?: boolean }) {
  const input = useRef<HTMLInputElement>(null);
  const ordner = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);

  const add = (list: Abgelegt[]) => {
    if (disabled || list.length === 0) return;
    const known = new Set(files.map((a) => `${a.pfad}:${a.file.size}`));
    const fresh = list.filter((a) => !known.has(`${a.pfad}:${a.file.size}`));
    if (fresh.length > 0) onFiles([...files, ...fresh]);
  };

  return (
    <div>
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setOver(false);
          // ausDrop muss synchron im Handler starten, danach sind die Einträge der Ablage leer.
          ausDrop(e.dataTransfer.items).then(add, () => undefined);
        }}
        className={cn("rounded-md border border-dashed p-4 text-center", over ? "border-accent bg-accent-soft" : "border-line-strong")}
      >
        <input
          ref={input}
          type="file"
          multiple
          accept={ACCEPT}
          disabled={disabled}
          className="sr-only"
          aria-label="Dateien wählen"
          data-testid="ablauf-dateien"
          onChange={(e) => {
            if (e.target.files) add(ausInput(e.target.files));
            e.target.value = "";
          }}
        />
        <input
          ref={ordner}
          type="file"
          {...ORDNER}
          disabled={disabled}
          className="sr-only"
          aria-label="Ordner wählen"
          data-testid="ablauf-ordner"
          onChange={(e) => {
            if (e.target.files) add(ausInput(e.target.files));
            e.target.value = "";
          }}
        />
        <div className="flex flex-wrap justify-center gap-2">
          <button
            type="button"
            disabled={disabled}
            onClick={() => input.current?.click()}
            className="min-h-11 rounded-md border border-border bg-card px-4 text-subhead font-medium hover:bg-muted disabled:opacity-50"
          >
            Dateien wählen
          </button>
          <button
            type="button"
            disabled={disabled}
            onClick={() => ordner.current?.click()}
            className="min-h-11 rounded-md border border-border bg-card px-4 text-subhead font-medium hover:bg-muted disabled:opacity-50"
          >
            Ordner wählen
          </button>
        </div>
        <p className="mt-2 text-footnote text-muted-foreground">oder Dateien und Ordner hierher ziehen</p>
      </div>
      {files.length > 0 && (
        <ul className="mt-2 divide-y divide-border rounded-md border border-border" aria-label="Gewählte Dateien">
          {files.map((a) => (
            <li key={`${a.pfad}:${a.file.size}`} className="flex items-center gap-2 pl-3">
              <span className="min-w-0 flex-1 truncate font-mono text-footnote" title={a.pfad}>
                {a.pfad}
              </span>
              <button
                type="button"
                disabled={disabled}
                onClick={() => onFiles(files.filter((f) => f !== a))}
                aria-label={`${a.pfad} entfernen`}
                className="grid size-11 shrink-0 place-items-center text-muted-foreground hover:text-foreground disabled:opacity-50"
              >
                <X className="size-4" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
