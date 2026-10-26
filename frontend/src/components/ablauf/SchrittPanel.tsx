"use client";

import { X } from "lucide-react";
import { useEffect, type ReactNode } from "react";

import type { RunStep } from "@/lib/api";

import { dauerText } from "./knoten";

function Zeile({ titel, children }: { titel: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-caption-1 font-semibold uppercase text-muted-foreground">{titel}</dt>
      <dd className="mt-0.5 text-subhead break-words whitespace-pre-wrap">{children}</dd>
    </div>
  );
}

/** Einzelheiten eines Schritts: rechts ab md (360 px), darunter als Sheet am unteren Rand. */
export function SchrittPanel({ step, onClose }: { step: RunStep; onClose: () => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <aside
      aria-label={`Schritt ${step.label}`}
      data-testid="schritt-panel"
      className="fixed inset-x-0 bottom-0 z-30 max-h-[60vh] overflow-y-auto border-t border-border bg-card p-4 md:static md:max-h-none md:w-[360px] md:shrink-0 md:border-t-0 md:border-l-[0.5px]"
    >
      <div className="flex items-center gap-2">
        <h2 className="min-w-0 flex-1 truncate text-headline font-semibold">{step.label}</h2>
        <button type="button" onClick={onClose} aria-label="Schließen" className="grid size-11 shrink-0 place-items-center rounded-full hover:bg-muted">
          <X className="size-5" />
        </button>
      </div>
      <dl className="mt-3 space-y-3">
        <Zeile titel="Eingabe">{step.input || "–"}</Zeile>
        <Zeile titel="Ausgabe">{step.output || "–"}</Zeile>
        <Zeile titel="Dauer">{dauerText(step) || "–"}</Zeile>
        {step.error && (
          <div>
            <dt className="text-caption-1 font-semibold uppercase text-danger">Fehler</dt>
            <dd className="mt-0.5 text-subhead break-words whitespace-pre-wrap text-danger">{step.error}</dd>
          </div>
        )}
      </dl>
      <div className="mt-4">
        {step.trace_url ? (
          <a
            href={step.trace_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex min-h-11 items-center text-subhead font-medium text-primary hover:underline"
          >
            In Langfuse öffnen
          </a>
        ) : (
          <span className="text-footnote text-muted-foreground">Tracing aus</span>
        )}
      </div>
    </aside>
  );
}
