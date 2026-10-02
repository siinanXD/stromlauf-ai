"use client";

import { ChevronLeft, ChevronRight, Factory, Maximize2, X, ZoomIn, ZoomOut } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { TransformComponent, TransformWrapper } from "react-zoom-pan-pinch";
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
          "mx-auto flex min-h-0 w-full max-w-7xl flex-1 flex-col overflow-hidden rounded-lg bg-card shadow-floating",
          docked && "lg:max-w-none lg:rounded-none lg:border-l-[0.5px] lg:border-border lg:shadow-none",
        )}
        onClick={(event) => event.stopPropagation()}
      >
        <header className="flex min-h-[52px] items-center gap-2 border-b-[0.5px] border-border bg-bg-bar px-4 py-1 backdrop-blur-bar">
          <span className="min-w-0 flex-1">
            <span className="block truncate text-headline">{title}</span>
            <span className="block truncate text-caption-1 text-muted-foreground">
              {target.filename} · {page === null ? "Blatt wird gesucht …" : `S. ${page}`}
              {target.pageCount ? ` / ${target.pageCount}` : ""}
            </span>
          </span>
          <button className="min-h-11 shrink-0 rounded-md px-2 text-body text-primary hover:bg-bg-fill" onClick={onClose} aria-label="Schließen">
            <X className="size-5 lg:hidden" aria-hidden />
            <span className="hidden lg:inline" aria-hidden>
              Schließen
            </span>
          </button>
        </header>
        <div className="min-h-0 flex-1 overflow-hidden bg-white">
          {page === null ? (
            <p className="p-8 text-center text-subhead text-muted-foreground">Lade {target.reference} …</p>
          ) : failed ? (
            <p className="p-8 text-center text-subhead text-muted-foreground">Seite {page} konnte nicht geladen werden.</p>
          ) : (
            <PageCanvas documentId={target.documentId} filename={target.filename} page={page} box={box} onError={() => setFailed(true)} />
          )}
        </div>
        <footer className="flex items-center gap-1 border-t-[0.5px] border-border bg-bg-bar px-2 py-1 text-subhead">
          <button className="flex min-h-11 items-center gap-1 rounded-md px-2 text-primary hover:bg-bg-fill disabled:text-muted-foreground disabled:opacity-50" onClick={() => page && go(page - 1)} disabled={!page || page <= 1}>
            <ChevronLeft className="size-5" />S. {(page ?? 1) - 1 || "–"}
          </button>
          <button className="flex min-h-11 items-center gap-1 rounded-md px-2 text-primary hover:bg-bg-fill disabled:text-muted-foreground disabled:opacity-50" onClick={() => page && go(page + 1)} disabled={!page || page >= lastPage}>
            S. {(page ?? 0) + 1}
            <ChevronRight className="size-5" />
          </button>
          {target.tag && machineId && (
            <button
              className="ml-auto flex min-h-11 items-center gap-1.5 rounded-md bg-primary px-3 font-semibold text-primary-foreground"
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

const zoomButton = "flex size-11 items-center justify-center text-primary hover:bg-bg-fill";

/**
 * Seitenbild mit Spaltenbox, zoom- und verschiebbar: Mausrad, Ziehen, zwei Finger, Doppelklick, dazu Knoepfe. Die
 * Box liegt im Zoom-Inhalt und bleibt so ueber ihrer Spalte. Der Behaelter bestimmt die Groesse; das Bild fuellt
 * seine Breite, eine hohe Seite verschiebt man.
 */
export function PageCanvas({
  documentId,
  filename,
  page,
  box,
  onError,
}: {
  documentId: string;
  filename: string;
  page: number;
  box: LocateResult["box"];
  onError?: () => void;
}) {
  return (
    <TransformWrapper key={`${documentId}:${page}`} minScale={1} maxScale={8} doubleClick={{ mode: "toggle", step: 1 }}>
      {({ zoomIn, zoomOut, resetTransform }) => (
        <div className="relative size-full">
          <TransformComponent wrapperStyle={{ width: "100%", height: "100%" }} contentStyle={{ width: "100%" }}>
            <div className="relative w-full cursor-grab active:cursor-grabbing">
              {/* Seitenbilder kommen dynamisch vom Backend; next/image bringt hier nichts. */}
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={api.pageImageUrl(documentId, page)}
                alt={`${filename}, Seite ${page}`}
                onError={onError}
                draggable={false}
                className="block h-auto w-full"
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
          </TransformComponent>
          <div className="absolute right-2 bottom-2 flex overflow-hidden rounded-md bg-card shadow-card">
            <button type="button" className={zoomButton} onClick={() => zoomIn()} aria-label="Vergrößern" title="Vergrößern">
              <ZoomIn className="size-4" />
            </button>
            <button type="button" className={zoomButton} onClick={() => zoomOut()} aria-label="Verkleinern" title="Verkleinern">
              <ZoomOut className="size-4" />
            </button>
            <button type="button" className={zoomButton} onClick={() => resetTransform()} aria-label="Einpassen" title="Einpassen">
              <Maximize2 className="size-4" />
            </button>
          </div>
        </div>
      )}
    </TransformWrapper>
  );
}
