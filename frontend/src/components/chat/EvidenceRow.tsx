"use client";

import type { PageTarget } from "@/components/PageViewer";
import { api, plant, type Evidence } from "@/lib/api";

/** Belegbilder unter der Antwort: Seitenausschnitte der Zitate und Schaltschrankfotos mit Rahmen um das Bauteil. */
export function EvidenceRow({ evidence, onOpen }: { evidence: Evidence[]; onOpen: (target: PageTarget) => void }) {
  return (
    <ul className="scroll-contain flex w-0 min-w-full snap-x gap-3 overflow-x-auto pb-1 [scrollbar-width:thin]" aria-label="Belegbilder">
      {evidence.map((item) =>
        item.kind === "page" ? (
          <li key={`${item.document_id}-${item.page}`} className="w-40 shrink-0 snap-start">
            <button
              type="button"
              onClick={() => onOpen({ documentId: item.document_id, filename: item.filename, page: item.page, label: item.label })}
              className="block w-full overflow-hidden rounded-xl border border-border bg-card text-left hover:border-primary"
              aria-label={`${item.label} öffnen`}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={api.pageImageUrl(item.document_id, item.page)} alt={`Seite ${item.page} aus ${item.filename}`} className="aspect-[4/3] w-full object-cover object-top" loading="lazy" />
              <span className="block truncate px-2 py-1 text-[11px] text-muted-foreground">{item.label}</span>
            </button>
          </li>
        ) : (
          <li key={item.hotspot_id} className="w-40 shrink-0 snap-start" data-testid="evidence-cabinet">
            <figure className="overflow-hidden rounded-xl border border-border bg-card">
              <div className="relative aspect-[4/3] w-full overflow-hidden bg-secondary">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={plant.cabinetImageUrl(item.cabinet_id)} alt={`${item.cabinet_title}: ${item.tag} markiert`} className="absolute inset-0 size-full object-cover" loading="lazy" />
                <span
                  aria-hidden
                  className="absolute rounded-sm border-2 border-signal shadow-[0_0_0_1px_var(--signal-foreground)]"
                  style={{ left: `${item.box.x * 100}%`, top: `${item.box.y * 100}%`, width: `${item.box.w * 100}%`, height: `${item.box.h * 100}%` }}
                />
              </div>
              <figcaption className="truncate px-2 py-1 font-mono text-[11px] text-muted-foreground">
                {item.tag} · {item.cabinet_title}
                {!item.confirmed && " · unbestätigt"}
              </figcaption>
            </figure>
          </li>
        ),
      )}
    </ul>
  );
}
