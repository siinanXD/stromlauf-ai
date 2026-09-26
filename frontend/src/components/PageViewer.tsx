"use client";

import { ChevronLeft, ChevronRight, Factory, X, ZoomIn, ZoomOut } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { api, locate, searchTags, type LocateResult } from "@/lib/api";
import { cn } from "@/lib/utils";

export interface PageTarget {
  documentId: string;
  filename: string;
  /** Fehlt bei Blatt-Verweisen: die Seite bestimmt dann das Backend. */
  page?: number;
  pageCount?: number | null;
  /** Beleg wie "/3.8": Seite wird ueber das Blatt bestimmt, die Spalte markiert. */
  reference?: string;
  /** Kopfzeile, z. B. "Stromlaufplan /3.8". */
  label?: string;
  /** Betriebsmittel fuer "im Werk zeigen". */
  tag?: string | null;
}

/**
 * Seitenansicht eines Dokuments. docked: auf breiten Bildschirmen als rechte Spalte neben dem
 * Inhalt, sonst Vollbild-Overlay.
 */
export function PageViewer({ target, onClose, docked = false }: { target: PageTarget; onClose: () => void; docked?: boolean }) {
  const router = useRouter();
  const [page, setPage] = useState<number | null>(target.page ?? null);
  const [zoomed, setZoomed] = useState(false);
  const [failed, setFailed] = useState(false);
  const [located, setLocated] = useState<LocateResult | null>(null);
  const [machineId, setMachineId] = useState<string | null>(null);
  const userPaged = useRef(false);
  const lastPage = target.pageCount ?? Number.MAX_SAFE_INTEGER;

  // Jeder Klick auf einen Beleg ist ein neues target-Objekt: Zustand zuruecksetzen und neu anspringen
  const [seen, setSeen] = useState(target);
  if (seen !== target) {
    setSeen(target);
    setPage(target.page ?? null);
    setLocated(null);
    setFailed(false);
  }
  useEffect(() => {
    userPaged.current = false;
    if (!target.reference) return;
    let cancelled = false;
    locate(target.documentId, target.reference)
      .then((result) => {
        if (cancelled) return;
        setLocated(result);
        if (!userPaged.current) setPage(result.page);
      })
      .catch((err: Error) => {
        if (cancelled) return;
        toast.warning(`${target.reference} nicht gefunden (${err.message}), zeige Seite ${target.page ?? 1}.`);
        setPage((current) => current ?? 1);
      });
    return () => {
      cancelled = true;
    };
  }, [target]);

  useEffect(() => {
    if (!target.tag) return;
    let cancelled = false;
    searchTags(target.tag)
      .then((hits) => !cancelled && setMachineId(hits.find((h) => h.tag === target.tag)?.machines[0]?.id ?? null))
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [target.tag]);

  const go = (next: number) => {
    userPaged.current = true;
    setFailed(false);
    setPage(Math.min(Math.max(1, next), lastPage));
  };

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      // Angedockt bleibt der Chat bedienbar: Tasten in Eingabefeldern gehoeren nicht der Seitenansicht
      const el = event.target as HTMLElement | null;
      if (el && (el.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName))) return;
      if (page === null) return;
      if (event.key === "Escape") onClose();
      if (event.key === "ArrowLeft") go(page - 1);
      if (event.key === "ArrowRight") go(page + 1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const box = located?.box && located.page === page ? located.box : null;
  const title = [target.label ?? target.filename, located?.column && located.page === page ? `Spalte ${located.column}` : null]
    .filter(Boolean)
    .join(" · ");

  return (
    <div
      className={cn(
        "fixed inset-0 z-50 flex flex-col bg-black/70 p-3 sm:p-6",
        docked && "lg:static lg:z-auto lg:w-[min(560px,45%)] lg:shrink-0 lg:bg-transparent lg:p-0",
      )}
      onClick={onClose}
      role="dialog"
      aria-label={`${target.filename}, Seite ${page}`}
    >
      <div
        className={cn(
          "mx-auto flex min-h-0 w-full max-w-7xl flex-1 flex-col overflow-hidden border border-line bg-card",
          docked && "lg:max-w-none lg:border-y-0 lg:border-r-0",
        )}
        onClick={(event) => event.stopPropagation()}
      >
        <header className="flex items-center gap-2 bg-nav px-4 py-2.5 text-white">
          <span className="min-w-0 flex-1 truncate font-mono text-xs font-semibold uppercase tracking-[0.06em]">{title}</span>
          <button className="p-1 hover:text-white/70" onClick={() => setZoomed(!zoomed)} aria-label={zoomed ? "Einpassen" : "Zoom"}>
            {zoomed ? <ZoomOut className="size-4" /> : <ZoomIn className="size-4" />}
          </button>
          <button className="p-1 hover:text-white/70" onClick={onClose} aria-label="Schließen">
            <X className="size-4" />
          </button>
        </header>
        <div className="px-4 py-1.5 font-mono text-[11px] text-muted-foreground">
          {target.filename} · {page === null ? "Blatt wird gesucht …" : `S. ${page}`}
          {target.pageCount ? ` / ${target.pageCount}` : ""}
        </div>
        <div className="min-h-0 flex-1 overflow-auto bg-white">
          {page === null ? (
            <p className="p-8 text-center text-sm text-muted-foreground">Lade {target.reference} …</p>
          ) : failed ? (
            <p className="p-8 text-center text-sm text-muted-foreground">Seite {page} konnte nicht geladen werden.</p>
          ) : (
            <div className={cn("relative", zoomed ? "w-[200%]" : "w-full")}>
              {/* Seitenbilder kommen dynamisch vom Backend; next/image bringt hier nichts. */}
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                key={page}
                src={api.pageImageUrl(target.documentId, page)}
                alt={`${target.filename}, Seite ${page}`}
                onError={() => setFailed(true)}
                onClick={() => setZoomed(!zoomed)}
                className={cn("block h-auto w-full", zoomed ? "cursor-zoom-out" : "cursor-zoom-in")}
              />
              {box && (
                <div
                  className="pointer-events-none absolute border-2 border-primary bg-primary/10"
                  style={{
                    left: `${box.x0 * 100}%`,
                    top: `${box.y0 * 100}%`,
                    width: `${(box.x1 - box.x0) * 100}%`,
                    height: `${(box.y1 - box.y0) * 100}%`,
                  }}
                />
              )}
            </div>
          )}
        </div>
        <footer className="flex items-center gap-3 border-t border-line px-4 py-2.5 text-sm">
          <button className="flex items-center gap-1 text-muted-foreground hover:text-foreground disabled:opacity-30" onClick={() => page && go(page - 1)} disabled={!page || page <= 1}>
            <ChevronLeft className="size-4" />S. {(page ?? 1) - 1 || "–"}
          </button>
          <button className="flex items-center gap-1 text-muted-foreground hover:text-foreground disabled:opacity-30" onClick={() => page && go(page + 1)} disabled={!page || page >= lastPage}>
            S. {(page ?? 0) + 1}
            <ChevronRight className="size-4" />
          </button>
          {target.tag && machineId && (
            <button
              className="ml-auto flex items-center gap-1.5 bg-primary px-3 py-1.5 font-medium text-primary-foreground"
              onClick={() => router.push(`/werk/maschine/${machineId}?tag=${encodeURIComponent(target.tag!)}`)}
            >
              <Factory className="size-4" />
              {target.tag} im Werk zeigen
            </button>
          )}
        </footer>
      </div>
    </div>
  );
}
