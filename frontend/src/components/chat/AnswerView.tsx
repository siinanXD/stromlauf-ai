"use client";

import { ChevronRight } from "lucide-react";
import { useMemo, type ReactNode } from "react";
import { defaultUrlTransform, type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

import { metaBlockData } from "@/components/answer/blockData";
import { CabinetBlock } from "@/components/answer/blocks/CabinetBlock";
import { CitationsBlock, type ChipData, type CitationGroup } from "@/components/answer/blocks/CitationsBlock";
import { FaultHitsBlock } from "@/components/answer/blocks/FaultHitsBlock";
import { PartsBlock } from "@/components/answer/blocks/PartsBlock";
import { PlanBlock } from "@/components/answer/blocks/PlanBlock";
import { SignalBlock } from "@/components/answer/blocks/SignalBlock";
import type { PageTarget } from "@/components/PageViewer";
import { citationCheckFor, citationLabel, citationsValidLabel, deviceTagOf, parseCitations, refOf, splitSections, type Citation } from "@/lib/answer";
import type { ChatMessage, SourceRef, ToolCall } from "@/lib/api";
import type { DetailRef } from "@/lib/detail";
import { costText } from "@/lib/format";

import { AnswerError } from "./chatError";
import { CitationChip } from "./CitationChip";
import { EvidenceRow } from "./EvidenceRow";
import { FactCard } from "./FactCard";
import { Markdown, type MarkdownRender } from "./Markdown";
import { remarkPartTags, tagFromHref } from "./markdownText";
import { PartChip } from "./PartChip";

const TOOL_LABELS: Record<string, string> = {
  search_knowledge: "Suche in Wissensquellen",
  find_tag: "Kennzeichen verfolgen",
  keyword_search: "Textsuche",
  get_page: "Seite lesen",
  view_page: "Seite ansehen",
  get_plc_block: "SPS-Baustein laden",
  list_documents: "Dokumente auflisten",
  search_faults: "Fehlerlisten durchsuchen",
};

function toolSummary(call: ToolCall): string {
  const { query, tag, text, page, block } = call.args as Record<string, string | number>;
  const detail = query ?? tag ?? text ?? block ?? (page ? `S. ${page}` : "");
  const label = TOOL_LABELS[call.name] ?? call.name;
  return detail ? `${label}: ${detail}` : label;
}

const urlTransform = (url: string) => (url.startsWith("cite:") || url.startsWith("part:") ? url : defaultUrlTransform(url));

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

/** Maschinen-Chat: Antwort als Bloecke mit Detail-Spalte. Ohne bleibt die bisherige Darstellung (werksweiter Chat). */
export interface AnswerBlocksContext {
  machineId: string;
  sourceId: string | null;
  onOpenDetail: (detail: DetailRef) => void;
  /** Treffer "erledigter Stoerfall" im Block Fehlerliste oeffnet diesen Stoerfall. */
  onOpenIncident?: (conversationId: string) => void;
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
  blocks,
}: {
  message: ChatMessage;
  question: string;
  streaming: boolean;
  sourceIds: string[];
  activeReference: string | null;
  onOpen: (target: PageTarget) => void;
  onOpenPart?: (tag: string) => void;
  onShowInModel?: (tags: string[]) => void;
  blocks?: AnswerBlocksContext;
}) {
  const { markdown, citations } = useMemo(() => parseCitations(message.content), [message.content]);
  const sections = useMemo(() => splitSections(markdown), [markdown]);
  const meta = message.meta;
  const tag = deviceTagOf(question);
  // Kennzeichen der Antwort werden im Text zu Knoepfen (nur im Maschinen-Chat, dort gibt es das Bauteil-Detail)
  const tagsKey = blocks && Array.isArray(meta?.referenced_tags) ? meta.referenced_tags.join(",") : "";

  const resolve = (citation: Citation): SourceRef | undefined =>
    message.sources.find((s) => s.filename === citation.filename) ??
    message.sources.find((s) => stem(s.filename) === stem(citation.filename));

  const chip = (citation: Citation): ChipData => {
    const source = resolve(citation);
    const label = citationLabel(citation, source?.doc_type);
    const { ref, page } = refOf(citation.loc);
    const pdf = source?.filename.toLowerCase().endsWith(".pdf");
    const key = `${source?.document_id}${ref}`;
    const open =
      source && pdf && ref
        ? () => onOpen({ documentId: source.document_id, filename: source.filename, page, reference: ref, label, tag })
        : undefined;
    const check = citationCheckFor(meta?.citation_checks, citation);
    const invalid = check !== undefined && !check.valid;
    const title = check?.reason || (open ? `${source!.filename} öffnen` : citation.filename);
    return { label, open, active: activeReference === key, key, title, invalid };
  };

  // Die Absaetze sind zwischengespeichert (Markdown.tsx) und rendern nur neu, wenn sich ihr Text oder die Version
  // aendert; dann bekommen sie diese frische Umgebung mit den aktuellen Belegen.
  const onOpenDetail = blocks?.onOpenDetail;
  const components: Components = {
    a: ({ href, children }) => {
      if (href?.startsWith("cite:")) {
        const citation = citations[Number(href.slice(5))];
        if (!citation) return <>{children}</>;
        const c = chip(citation);
        return <CitationChip label={c.label} onClick={c.open} active={c.active} title={c.title} invalid={c.invalid} />;
      }
      const part = tagFromHref(href);
      if (part) {
        return (
          <button
            type="button"
            data-part-link={part}
            title={`Bauteil ${part} öffnen`}
            onClick={() => onOpenDetail?.({ kind: "part", tag: part })}
            className="rounded-sm px-0.5 font-mono text-[0.95em] font-semibold text-primary underline decoration-primary/40 underline-offset-2 hover:decoration-primary focus-visible:ring-2 focus-visible:ring-ring"
          >
            {children}
          </button>
        );
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
  const remarkPlugins = useMemo<MarkdownRender["remarkPlugins"]>(() => [remarkGfm, [remarkPartTags, { tags: tagsKey ? tagsKey.split(",") : [] }]], [tagsKey]);
  const render: MarkdownRender = { components, remarkPlugins, urlTransform };

  // Was die Darstellung eines fertigen Absatzes aendern kann, ausser seinem Text
  const version = [activeReference ?? "", message.sources.length, meta ? "m" : "", meta?.citation_checks?.length ?? 0, tagsKey].join("|");
  const md = (text: string) => <Markdown text={text} render={render} version={version} />;

  const running = message.tool_calls.find((c) => !c.done);
  const waiting = streaming && !message.content;
  const grouped = citations.reduce<Map<string, CitationGroup>>((acc, citation) => {
    const c = chip(citation);
    const group = c.label.slice(0, c.label.length - citation.loc.length).trim() || citation.filename;
    const entry = acc.get(group) ?? { label: group, chips: [] };
    if (!entry.chips.some((x) => x.label === citation.loc)) entry.chips.push({ ...c, label: citation.loc });
    acc.set(group, entry);
    return acc;
  }, new Map());
  const groups = [...grouped.values()];
  const fallback = citations.length === 0 ? message.sources.filter((s) => s.page).slice(0, MAX_FALLBACK_SOURCES) : [];
  const validLabel = citationsValidLabel(meta?.citations_valid);
  const problems = (meta?.citation_checks ?? []).filter((c) => !c.valid || !c.checked || c.reason);
  const openSource = (s: SourceRef) => onOpen({ documentId: s.document_id, filename: s.filename, page: s.page! });

  const toolLine =
    message.tool_calls.length > 0 &&
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
    ));

  const text = (
    <>
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
              <summary className="flex min-h-11 cursor-pointer list-none items-center gap-1.5 py-2 text-[13px] font-medium">
                <ChevronRight className="size-3.5 transition-transform group-open:rotate-90" />
                {block.title}
              </summary>
              <div className="markdown pb-3 text-[13px]">{md(block.body)}</div>
            </details>
          ))}
        </section>
      )}

      {message.error && <AnswerError raw={message.error} faultList={Boolean(blocks && question.trim())} />}
    </>
  );

  const cost = !streaming && message.cost_cents !== undefined && (
    <p className="font-mono text-[11px] text-muted-foreground" title="Aus dem Kostenbuch: alle Modellaufrufe dieser Antwort">
      Kosten dieser Antwort: {costText(message.cost_cents)}
    </p>
  );

  if (blocks) {
    // Feste Reihenfolge der Spec: Fehlerliste sofort, Text waehrend des Streams, danach die Bloecke aus meta.
    const data = metaBlockData(meta, blocks.sourceId);
    return (
      <div className="space-y-3" data-answer="blocks">
        {question.trim() && <FaultHitsBlock machineId={blocks.machineId} query={question} onOpenDetail={blocks.onOpenDetail} onOpenIncident={blocks.onOpenIncident} />}
        <div className="space-y-4" data-block="text">
          {toolLine}
          {text}
        </div>
        {!streaming && (
          <>
            {data.parts && <PartsBlock tags={data.parts.tags} kinds={data.parts.kinds} onOpenDetail={blocks.onOpenDetail} onShowInModel={onShowInModel} />}
            {data.signal && blocks.sourceId && <SignalBlock sourceId={blocks.sourceId} start={data.signal} onOpenDetail={blocks.onOpenDetail} />}
            {data.plan && <PlanBlock spots={data.plan} onOpenDetail={blocks.onOpenDetail} />}
            {data.cabinet && <CabinetBlock evidence={data.cabinet} onOpenDetail={blocks.onOpenDetail} />}
            <CitationsBlock groups={groups} validLabel={validLabel} problems={problems} fallback={fallback} onOpenSource={openSource} />
            {cost}
          </>
        )}
      </div>
    );
  }

  // Werksweiter Chat: Befundkarte zur Frage, Belege, referenzierte Bauteile und Belegbilder wie bisher
  return (
    <div className="space-y-4">
      {toolLine}

      {tag && !waiting && <FactCard tag={tag} sourceIds={sourceIds} onOpen={onOpen} />}

      {text}

      {!streaming && fallback.length > 0 && (
        <section>
          <SectionLabel>Fundstellen</SectionLabel>
          <div className="flex flex-wrap gap-1">
            {fallback.map((s) => (
              <CitationChip key={`${s.document_id}-${s.page}`} label={`${s.filename} S. ${s.page}`} onClick={() => openSource(s)} />
            ))}
          </div>
        </section>
      )}

      {!streaming && groups.length > 0 && (
        <section>
          <SectionLabel>Belege</SectionLabel>
          <dl className="grid grid-cols-[max-content_1fr] items-center gap-x-4 gap-y-1 text-xs">
            {groups.map((group) => (
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

      {!streaming && meta && meta.referenced_tags.length > 0 && (
        <section data-testid="referenced-parts">
          <SectionLabel>In der Antwort referenziert</SectionLabel>
          <div className="flex flex-wrap items-center gap-1.5">
            {meta.referenced_tags.map((t) => (
              <PartChip key={t} tag={t} referenced onClick={onOpenPart ? () => onOpenPart(t) : undefined} />
            ))}
            {onShowInModel && (
              <button
                type="button"
                onClick={() => onShowInModel(meta.referenced_tags)}
                className="ml-1 rounded-lg border border-border px-2 py-1 text-xs font-medium hover:border-primary hover:text-primary"
              >
                Im Modell zeigen
              </button>
            )}
          </div>
        </section>
      )}

      {!streaming && meta && meta.evidence.length > 0 && (
        <section data-testid="evidence-row">
          <SectionLabel>Belegbilder</SectionLabel>
          <EvidenceRow evidence={meta.evidence} onOpen={onOpen} onOpenPart={onOpenPart} />
        </section>
      )}

      {!streaming && (message.cost_cents !== undefined || validLabel) && (
        <div className="flex flex-wrap items-start gap-x-3 font-mono text-[11px] text-muted-foreground">
          {message.cost_cents !== undefined && (
            <span title="Aus dem Kostenbuch: alle Modellaufrufe dieser Antwort">Kosten dieser Antwort: {costText(message.cost_cents)}</span>
          )}
          {validLabel &&
            (problems.length === 0 ? (
              <span data-testid="citations-valid" title="Alle Belege in den Fundstellen gefunden">
                {validLabel}
              </span>
            ) : (
              <details data-testid="citations-valid" className="group">
                <summary className="cursor-pointer list-none hover:text-foreground">
                  <ChevronRight className="mr-0.5 inline size-3 transition-transform group-open:rotate-90" />
                  {validLabel}
                </summary>
                <ul className="mt-1 space-y-0.5 pl-4">
                  {problems.map((c) => (
                    <li key={c.text}>
                      <span className={c.valid ? "" : "line-through decoration-muted-foreground/70"}>{c.text}</span>: {c.reason}
                    </li>
                  ))}
                </ul>
              </details>
            ))}
        </div>
      )}
    </div>
  );
}
