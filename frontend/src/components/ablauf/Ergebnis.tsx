"use client";

import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { CitationChip } from "@/components/chat/CitationChip";
import { SteckbriefKarte } from "@/components/SteckbriefKarte";
import type { Run } from "@/lib/api";

/** Ergebnis des Laufs, sobald der Steckbrief da ist: Steckbrief, Modellgröße, Antworten mit Belegen, Weg zur Maschine. */
export function Ergebnis({ run }: { run: Run }) {
  const { profile, map_counts, answers, machine_id } = run.result;
  if (!profile) return null;
  return (
    <section aria-label="Ergebnis" className="space-y-6 p-4 md:px-6">
      <SteckbriefKarte profile={profile} />
      {map_counts && (
        <p className="text-subhead" data-testid="ablauf-modell">
          Modell: {map_counts.zones} Zonen, {map_counts.parts} Bauteile
        </p>
      )}
      {answers?.map((answer, index) => (
        <article key={index} className="rounded-md border border-border bg-card p-4">
          <h3 className="text-headline font-semibold">{answer.question}</h3>
          <div className="markdown mt-2 text-body">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{answer.answer_md}</ReactMarkdown>
          </div>
          {answer.sources.length > 0 && (
            <div className="mt-2 flex flex-wrap">
              {answer.sources.map((s, i) => (
                <CitationChip key={`${s.document_id}-${s.page}-${i}`} label={`${s.filename}${s.page ? ` S. ${s.page}` : ""}`} title={s.section || undefined} />
              ))}
            </div>
          )}
        </article>
      ))}
      {machine_id && (
        <Link
          href={`/werk/maschine/${machine_id}`}
          className="inline-flex min-h-11 items-center rounded-md bg-primary px-4 text-subhead font-medium text-primary-foreground"
        >
          Maschine öffnen
        </Link>
      )}
    </section>
  );
}
