"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import type { ChatMessage, SourceRef, ToolCall } from "@/lib/api";

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
  return detail ? `${TOOL_LABELS[call.name] ?? call.name}: ${detail}` : (TOOL_LABELS[call.name] ?? call.name);
}

function sourceLabel(source: SourceRef): string {
  if (source.page) return `${source.filename}, S. ${source.page}`;
  return source.section ? `${source.filename}, ${source.section}` : source.filename;
}

export function Message({
  message,
  streaming,
  onOpenSource,
}: {
  message: ChatMessage;
  streaming: boolean;
  onOpenSource: (source: SourceRef) => void;
}) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-md bg-primary/10 px-4 py-2.5">
          {message.content}
        </div>
      </div>
    );
  }

  const waiting = streaming && !message.content && message.tool_calls.every((c) => c.done);
  return (
    <div className="space-y-3">
      {message.tool_calls.length > 0 && (
        <ul className="space-y-1 text-sm text-muted-foreground">
          {message.tool_calls.map((call, index) => (
            <li key={index} className="flex items-center gap-2">
              <span
                className={`h-1.5 w-1.5 shrink-0 rounded-full ${
                  call.done || !streaming ? "bg-ok" : "animate-pulse bg-primary"
                }`}
              />
              <span className="truncate">{toolSummary(call)}</span>
            </li>
          ))}
        </ul>
      )}

      {waiting && <p className="animate-pulse text-sm text-muted-foreground">Denkt nach …</p>}

      {message.content && (
        <div className="markdown">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              table: (props) => (
                <div className="table-wrap">
                  <table {...props} />
                </div>
              ),
            }}
          >
            {message.content}
          </ReactMarkdown>
        </div>
      )}

      {message.error && (
        <p className="rounded-lg border border-danger/40 px-3 py-2 text-sm text-danger">
          {message.error}
        </p>
      )}

      {!streaming && message.sources.length > 0 && (
        <div className="flex flex-wrap gap-1.5 pt-1">
          {message.sources.slice(0, 12).map((source, index) => (
            <button
              key={index}
              onClick={() => onOpenSource(source)}
              disabled={!source.page}
              title={source.page ? "Seite anzeigen" : undefined}
              className="max-w-full truncate rounded-full border border-border bg-card px-2.5 py-1 text-xs text-muted-foreground enabled:hover:border-primary enabled:hover:text-foreground"
            >
              {sourceLabel(source)}
            </button>
          ))}
          {message.sources.length > 12 && (
            <span className="px-1 py-1 text-xs text-muted-foreground">+{message.sources.length - 12} weitere</span>
          )}
        </div>
      )}
    </div>
  );
}
