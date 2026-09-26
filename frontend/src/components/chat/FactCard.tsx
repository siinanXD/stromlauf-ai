"use client";

import { Route } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import type { PageTarget } from "@/components/PageViewer";
import { factCard, searchTags, type FactCardData } from "@/lib/api";

import { CitationChip } from "./CitationChip";

const MAX_VALUES = 4;

/** Befundkarte zum Betriebsmittel der Frage; Daten aus dem Kennzeichen-Index, nicht vom Modell. */
export function FactCard({ tag, sourceIds, onOpen }: { tag: string; sourceIds: string[]; onOpen: (target: PageTarget) => void }) {
  const router = useRouter();
  const [card, setCard] = useState<FactCardData | null>(null);
  const key = `${tag}|${sourceIds.join(",")}`;

  useEffect(() => {
    let cancelled = false;
    factCard(tag, sourceIds)
      .then((result) => !cancelled && setCard(result))
      .catch(() => !cancelled && setCard(null));
    return () => {
      cancelled = true;
    };
    // key buendelt tag und Quellen, damit ein neues Array nicht jedes Mal neu laedt
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  if (!card) return null;
  return (
    <section className="border border-line bg-card">
      <div className="flex items-center justify-between bg-nav px-3 py-1.5">
        <span className="font-mono text-[11px] font-semibold tracking-[0.06em] text-white">BEFUNDKARTE</span>
        <span className="flex items-center gap-3 text-[11px] text-nav-foreground">
          aus dem Dokument-Index
          <button
            type="button"
            className="flex items-center gap-1 text-white hover:underline"
            onClick={async () => {
              const hit = (await searchTags(card.tag).catch(() => [])).find((h) => h.tag === card.tag);
              const machine = hit?.machines[0];
              if (machine) router.push(`/werk/maschine/${machine.id}?tag=${encodeURIComponent(card.tag)}&tab=signalweg`);
            }}
          >
            <Route className="size-3" />
            Signalweg
          </button>
        </span>
      </div>
      <div className="flex flex-wrap items-baseline gap-x-3 px-3 pt-2.5">
        <span className="font-mono text-[22px] font-semibold text-primary">{card.tag}</span>
        {card.title && <span className="text-[13px]">{card.title}</span>}
      </div>
      <div className="grid gap-x-4 gap-y-2 px-3 pb-3 pt-2 sm:grid-cols-3">
        {card.rows.map((row) => (
          <div key={row.label} className="min-w-0">
            <div className="text-[11px] text-muted-foreground">{row.label}</div>
            <div className="mt-0.5 flex flex-wrap gap-1">
              {row.values.slice(0, MAX_VALUES).map((value) => {
                const pdf = value.filename?.toLowerCase().endsWith(".pdf");
                const open =
                  value.document_id && pdf
                    ? () =>
                        onOpen({
                          documentId: value.document_id!,
                          filename: value.filename!,
                          page: value.page ?? undefined,
                          reference: value.ref,
                          label: `${row.label} ${value.text}`,
                          tag: card.tag,
                        })
                    : undefined;
                return <CitationChip key={value.text} label={value.text} onClick={open} title={value.filename ?? undefined} />;
              })}
              {row.values.length > MAX_VALUES && <span className="text-[11px] text-muted-foreground">+{row.values.length - MAX_VALUES}</span>}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
