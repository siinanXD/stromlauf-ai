"use client";

import { X } from "lucide-react";
import { useRef, useState } from "react";

import { cn } from "@/lib/utils";

// Endungen wie ALLOWED_SUFFIXES im Backend (app/api/sources.py)
const ACCEPT = ".pdf,.awl,.scl,.sdf,.xlsx,.csv,.docx,.pptx,.md,.txt,.html,.png,.jpg,.jpeg,.tif,.tiff";

/** Dateien ablegen oder wählen; die Liste darunter erlaubt das Entfernen einzelner Dateien. */
export function Dropzone({ files, onFiles, disabled = false }: { files: File[]; onFiles: (files: File[]) => void; disabled?: boolean }) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);

  const add = (list: FileList | null) => {
    if (!list || disabled) return;
    const known = new Set(files.map((f) => `${f.name}:${f.size}`));
    const fresh = Array.from(list).filter((f) => !known.has(`${f.name}:${f.size}`));
    onFiles([...files, ...fresh]);
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
          add(e.dataTransfer.files);
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
            add(e.target.files);
            e.target.value = "";
          }}
        />
        <button
          type="button"
          disabled={disabled}
          onClick={() => input.current?.click()}
          className="min-h-11 rounded-md border border-border bg-card px-4 text-subhead font-medium hover:bg-muted disabled:opacity-50"
        >
          Dateien wählen
        </button>
        <p className="mt-2 text-footnote text-muted-foreground">oder hierher ziehen</p>
      </div>
      {files.length > 0 && (
        <ul className="mt-2 divide-y divide-border rounded-md border border-border" aria-label="Gewählte Dateien">
          {files.map((file) => (
            <li key={`${file.name}:${file.size}`} className="flex items-center gap-2 pl-3">
              <span className="min-w-0 flex-1 truncate font-mono text-footnote" title={file.name}>
                {file.name}
              </span>
              <button
                type="button"
                disabled={disabled}
                onClick={() => onFiles(files.filter((f) => f !== file))}
                aria-label={`${file.name} entfernen`}
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
