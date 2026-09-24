"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";

export interface PageTarget {
  documentId: string;
  filename: string;
  page: number;
  pageCount?: number | null;
}

export function PageViewer({ target, onClose }: { target: PageTarget; onClose: () => void }) {
  const [page, setPage] = useState(target.page);
  const [zoomed, setZoomed] = useState(false);
  const [failed, setFailed] = useState(false);
  const lastPage = target.pageCount ?? Number.MAX_SAFE_INTEGER;

  const go = (next: number) => {
    setFailed(false);
    setPage(Math.min(Math.max(1, next), lastPage));
  };

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
      if (event.key === "ArrowLeft") go(page - 1);
      if (event.key === "ArrowRight") go(page + 1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  return (
    <div
      className="fixed inset-0 z-50 flex flex-col bg-black/70 p-3 sm:p-6"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label={`${target.filename}, Seite ${page}`}
    >
      <div
        className="mx-auto flex min-h-0 w-full max-w-7xl flex-1 flex-col overflow-hidden rounded-xl border border-border bg-surface"
        onClick={(event) => event.stopPropagation()}
      >
        <header className="flex items-center gap-2 border-b border-border px-4 py-2.5 text-sm">
          <span className="min-w-0 flex-1 truncate font-medium">{target.filename}</span>
          <button className="rounded-md px-2 py-1 hover:bg-surface-2 disabled:opacity-30" onClick={() => go(page - 1)} disabled={page <= 1} aria-label="Vorherige Seite">
            ←
          </button>
          <span className="tabular-nums text-muted">
            S. {page}
            {target.pageCount ? ` / ${target.pageCount}` : ""}
          </span>
          <button className="rounded-md px-2 py-1 hover:bg-surface-2 disabled:opacity-30" onClick={() => go(page + 1)} disabled={page >= lastPage} aria-label="Nächste Seite">
            →
          </button>
          <button className="rounded-md px-2 py-1 hover:bg-surface-2" onClick={() => setZoomed(!zoomed)}>
            {zoomed ? "Einpassen" : "Zoom"}
          </button>
          <button className="rounded-md px-2 py-1 hover:bg-surface-2" onClick={onClose} aria-label="Schließen">
            ✕
          </button>
        </header>
        <div className="min-h-0 flex-1 overflow-auto bg-white">
          {failed ? (
            <p className="p-8 text-center text-sm text-neutral-600">Seite {page} konnte nicht geladen werden.</p>
          ) : (
            // Seitenbilder kommen dynamisch vom Backend; next/image bringt hier nichts.
            // eslint-disable-next-line @next/next/no-img-element
            <img
              key={page}
              src={api.pageImageUrl(target.documentId, page)}
              alt={`${target.filename}, Seite ${page}`}
              onError={() => setFailed(true)}
              onClick={() => setZoomed(!zoomed)}
              className={zoomed ? "w-[200%] max-w-none cursor-zoom-out" : "mx-auto h-full w-full cursor-zoom-in object-contain"}
            />
          )}
        </div>
      </div>
    </div>
  );
}
