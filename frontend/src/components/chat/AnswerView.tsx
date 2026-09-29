"use client";

import { ChevronRight } from "lucide-react";
import { useMemo, type ReactNode } from "react";
import ReactMarkdown, { defaultUrlTransform, type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

import type { PageTarget } from "@/components/PageViewer";
import { citationCheckFor, citationLabel, citationsValidLabel, deviceTagOf, parseCitations, refOf, splitSections, type Citation } from "@/lib/answer";
import type { ChatMessage, SourceRef, ToolCall } from "@/lib/api";
import { costText } from "@/lib/format";

import { CitationChip } from "./CitationChip";
import { EvidenceRow } from "./EvidenceRow";
import { FactCard } from "./FactCard";
import { PartChip } from "./PartChip";

const TOOL_LABELS: Record<string, string> = {
  search_knowledge: "Suche in Wissensquellen",
  find_tag: "Kennzeichen verfolgen",
  keyword_search: "Textsuche",
  get_page: "Seite lesen",
  view_page: "Seite ansehen",
  get_plc_block: "SPS-Baustein laden",
  list_documents: "Dokumente auflisten",
};

function toolSummary(call: ToolCall): string {
  const { query, tag, text, page, block } = call.args as Record<string, string | number>;
  const detail = query ?? tag ?? text ?? block ?? (page ? `S. ${page}` : "");
  const label = TOOL_LABELS[call.name] ?? call.name;
  return detail ? `${label}: ${detail}` : label;
}

const stem = (filename: string) => filename.toLowerCase().replace(/\.[^.]+$/, "");
const MAX_FALLBACK_SOURCES = 8;

function SectionLabel({ children }: { children: ReactNode }) {
  return <h3 className="mb-1.5 font-mono text-[11px] font-semibold uppercase tracking-[0.06em] text-muted-foreground">{children}</h3>;
}

/** Details-Abschnitt: jede ###-Unterueberschrift wird eine eigene einklappbare Zeile. */
function splitDetails(markdown: string): { title: string; body: string }[] {
  const parts = markdown.split(/^###\s+/m);
  const intro = parts[0].trim();
  const blocks = parts.slice(1).map((part) => {
    const [first, ...rest] = part.split("\n");
    return { title: first.trim(), body: rest.join("\n").trim() };
  });
  return intro ? [{ title: "Details", body: intro }, ...blocks] : blocks;
}

export function AnswerView({
  message,
  question,
  streaming,
  sourceIds,
  activeReference,
  onOpen,
  onOpenPart,
  onShowInModel,
}: {
  message: ChatMessage;
  question: string;
  streaming: boolean;
  sourceIds: string[];
  activeReference: string | null;
  onOpen: (target: PageTarget) => void;
  onOpenPart?: (tag: string) => void;
  onShowInModel?: (tags: string[]) => void;
}) {
  const { markdown, citations } = useMemo(() => parseCitations(message.content), [message.content]);
  const sections = useMemo(() => splitSections(markdown), [markdown]);
  const tag = deviceTagOf(question);

  const resolve = (citation: Citation): SourceRef | undefined =>
    message.sources.find((s) => s.filename === citation.filename) ??
    message.sources.find((s) => stem(s.filename) === stem(citation.filename));

  const chip = (citation: Citation) => {
    const source = resolve(citation);
    const label = citationLabel(citation, source?.doc_type);
    const { ref, page } = refOf(citation.loc);
    const pdf = source?.filename.toLowerCase().endsWith(".pdf");
    const key = `${source?.document_id}${ref}`;
    const open =
      source && pdf && ref
        ? () => onOpen({ documentId: source.document_id, filename: source.filename, page, reference: ref, label, tag })
        : undefined;
    const check = citationCheckFor(message.meta?.citation_checks, citation);
    const invalid = check !== undefined && !check.valid;
    const title = check?.reason || (open ? `${source!.filename} öffnen` : citation.filename);
    return { label, open, active: activeReference === key, key, title, invalid };
  };

  const components: Components = {
    a: ({ href, children }) => {
      if (href?.startsWith("cite:")) {
        const citation = citations[Number(href.slice(5))];
        if (!citation) return <>{children}</>;
        const c = chip(citation);
        return <CitationChip label={c.label} onClick={c.open} active={c.active} title={c.title} invalid={c.invalid} />;
      }
      return (
        <a href={href} target="_blank" rel="noreferrer">
          {children}
        </a>
      );
    },
    table: (props) => (
      <div className="table-wrap">
        <table {...props} />
      </div>
    ),
  };
  const md = (text: string) => (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={components} urlTransform={(url) => (url.startsWith("cite:") ? url : defaultUrlTransform(url))}>
      {text}
    </ReactMarkdown>
  );

  const running = message.tool_calls.find((c) => !c.done);
  const waiting = streaming && !message.content;
  const grouped = citations.reduce<Map<string, { label: string; chips: ReturnType<typeof chip>[] }>>((acc, citation) => {
    const c = chip(citation);
    const group = c.label.slice(0, c.label.length - citation.loc.length).trim() || citation.filename;
    const entry = acc.get(group) ?? { label: group, chips: [] };
    if (!entry.chips.some((x) => x.label === c.label)) entry.chips.push({ ...c, label: citation.loc });
    acc.set(group, entry);
    return acc;
  }, new Map());

  return (
    <div className="space-y-4">
      {message.tool_calls.length > 0 &&
        (streaming && running ? (
          <p className="flex items-center gap-2 text-xs text-muted-foreground">
            <span className="size-1.5 animate-pulse rounded-full bg-primary" />
            {toolSummary(running)}
          </p>
        ) : (
          <details className="group text-xs text-muted-foreground">
            <summary className="flex cursor-pointer list-none items-center gap-1 hover:text-foreground">
              <ChevronRight className="size-3.5 transition-transform group-open:rotate-90" />
              {message.tool_calls.length} Schritte · {message.sources.length} Fundstellen durchsucht
            </summary>
            <ul className="mt-1.5 space-y-0.5 pl-5">
              {message.tool_calls.map((call, index) => (
                <li key={index} className="truncate">
                  {toolSummary(call)}
                </li>
              ))}
            </ul>
          </details>
        ))}

      {tag && !waiting && <FactCard tag={tag} sourceIds={sourceIds} onOpen={onOpen} />}

      {waiting && !running && <p className="animate-pulse text-sm text-muted-foreground">Denkt nach …</p>}

      {sections.frei && <div className="markdown">{md(sections.frei)}</div>}

      {sections.kurz && (
        <section>
          <SectionLabel>Kurzantwort</SectionLabel>
          <div className="markdown text-[15px] font-medium leading-relaxed">{md(sections.kurz)}</div>
        </section>
      )}

      {sections.pruefen && (
        <section>
          <SectionLabel>Prüfen</SectionLabel>
          <div className="markdown answer-steps">{md(sections.pruefen)}</div>
        </section>
      )}

      {sections.sicherheit && (
        <section className="border-l-[3px] border-nav bg-secondary px-3 py-2">
          <h3 className="font-mono text-[10px] font-semibold uppercase tracking-[0.06em]">Sicherheit</h3>
          <div className="markdown text-[13px]">{md(sections.sicherheit)}</div>
        </section>
      )}

      {sections.details && (
        <section className="border-t border-border">
          {splitDetails(sections.details).map((block) => (
            <details key={block.title} className="group border-b border-border">
              <summary className="flex cursor-pointer list-none items-center gap-1.5 py-2 text-[13px] font-medium">
                <ChevronRight className="size-3.5 transition-transform group-open:rotate-90" />
                {block.title}
              </summary>
              <div className="markdown pb-3 text-[13px]">{md(block.body)}</div>
            </details>
          ))}
        </section>
      )}

      {!streaming && citations.length === 0 && message.sources.some((s) => s.page) && (
        <section>
          <SectionLabel>Fundstellen</SectionLabel>
          <div className="flex flex-wrap gap-1">
            {message.sources
              .filter((s) => s.page)
              .slice(0, MAX_FALLBACK_SOURCES)
              .map((s) => (
                <CitationChip
                  key={`${s.document_id}-${s.page}`}
                  label={`${s.filename} S. ${s.page}`}
                  onClick={() => onOpen({ documentId: s.document_id, filename: s.filename, page: s.page! })}
                />
              ))}
          </div>
        </section>
      )}

      {message.error && <p className="border border-danger/40 px-3 py-2 text-sm text-danger">{message.error}</p>}

      {!streaming && grouped.size > 0 && (
        <section>
          <SectionLabel>Belege</SectionLabel>
          <dl className="grid grid-cols-[max-content_1fr] items-center gap-x-4 gap-y-1 text-xs">
            {[...grouped.values()].map((group) => (
              <div key={group.label} className="contents">
                <dt className="text-muted-foreground">{group.label}</dt>
                <dd className="flex flex-wrap gap-1">
                  {group.chips.map((c) => (
                    <CitationChip key={c.key + c.label} label={c.label} onClick={c.open} active={c.active} title={c.title} invalid={c.invalid} />
                  ))}
                </dd>
              </div>
            ))}
          </dl>
        </section>
      )}

      {!streaming && message.meta && message.meta.referenced_tags.length > 0 && (
        <section data-testid="referenced-parts">
          <SectionLabel>In der Antwort referenziert</SectionLabel>
          <div className="flex flex-wrap items-center gap-1.5">
            {message.meta.referenced_tags.map((tag) => (
              <PartChip key={tag} tag={tag} referenced onClick={onOpenPart ? () => onOpenPart(tag) : undefined} />
            ))}
            {onShowInModel && (
              <button
                type="button"
                onClick={() => onShowInModel(message.meta!.referenced_tags)}
                className="ml-1 rounded-lg border border-border px-2 py-1 text-xs font-medium hover:border-primary hover:text-primary"
              >
                Im Modell zeigen
              </button>
            )}
          </div>
        </section>
      )}

      {!streaming && message.meta && message.meta.evidence.length > 0 && (
        <section data-testid="evidence-row">
          <SectionLabel>Belegbilder</SectionLabel>
          <EvidenceRow evidence={message.meta.evidence} onOpen={onOpen} onOpenPart={onOpenPart} />
        </section>
      )}

      {!streaming && (message.cost_cents !== undefined || citationsValidLabel(message.meta?.citations_valid)) && (
        <div className="flex flex-wrap items-start gap-x-3 font-mono text-[11px] text-muted-foreground">
          {message.cost_cents !== undefined && (
            <span title="Aus dem Kostenbuch: alle Modellaufrufe dieser Antwort">Kosten dieser Antwort: {costText(message.cost_cents)}</span>
          )}
          {citationsValidLabel(message.meta?.citations_valid) &&
            (() => {
              const problems = (message.meta?.citation_checks ?? []).filter((c) => !c.valid || !c.checked || c.reason);
              const label = citationsValidLabel(message.meta?.citations_valid);
              if (problems.length === 0) {
                return (
                  <span data-testid="citations-valid" title="Alle Belege in den Fundstellen gefunden">
                    {label}
                  </span>
                );
              }
              return (
                <details data-testid="citations-valid" className="group">
                  <summary className="cursor-pointer list-none hover:text-foreground">
                    <ChevronRight className="mr-0.5 inline size-3 transition-transform group-open:rotate-90" />
                    {label}
                  </summary>
                  <ul className="mt-1 space-y-0.5 pl-4">
                    {problems.map((c) => (
                      <li key={c.text}>
                        <span className={c.valid ? "" : "line-through decoration-muted-foreground/70"}>{c.text}</span>: {c.reason}
                      </li>
                    ))}
                  </ul>
                </details>
              );
            })()}
        </div>
      )}
    </div>
  );
}
