"use client";

import { useState } from "react";

import { api, type Conversation, type KnowledgeSource } from "@/lib/api";
import { AppNav } from "@/components/AppNav";
import type { PageTarget } from "@/components/PageViewer";
import { SourcePanel } from "@/components/SourcePanel";

export function Sidebar({
  sources,
  selectedSourceIds,
  onToggleSource,
  onSourcesChanged,
  conversations,
  activeConversationId,
  onSelectConversation,
  onNewConversation,
  onDeleteConversation,
  onOpenPage,
}: {
  sources: KnowledgeSource[];
  selectedSourceIds: string[];
  onToggleSource: (id: string) => void;
  onSourcesChanged: () => void;
  conversations: Conversation[];
  activeConversationId: string | null;
  onSelectConversation: (conversation: Conversation) => void;
  onNewConversation: () => void;
  onDeleteConversation: (conversation: Conversation) => void;
  onOpenPage: (target: PageTarget) => void;
}) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function createSource(event: React.FormEvent) {
    event.preventDefault();
    if (!name.trim()) return;
    try {
      const source = await api.createSource(name, "");
      setName("");
      setCreating(false);
      setError(null);
      setExpanded(source.id);
      onSourcesChanged();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function deleteSource(source: KnowledgeSource) {
    if (!confirm(`Wissensquelle „${source.name}“ mit ${source.document_count} Dokument(en) löschen?`)) return;
    await api.deleteSource(source.id).catch((err) => setError(err.message));
    onSourcesChanged();
  }

  return (
    <div className="flex h-full flex-col">
      <AppNav />

      <div className="min-h-0 flex-1 overflow-y-auto">
        <section>
          <div className="flex items-center justify-between px-4 pb-1.5 pt-2">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-muted">Wissensquellen</h2>
            <button
              onClick={() => setCreating(!creating)}
              className="rounded-md px-1.5 text-lg leading-none text-muted hover:bg-surface-2 hover:text-text"
              aria-label="Wissensquelle anlegen"
            >
              +
            </button>
          </div>

          {creating && (
            <form onSubmit={createSource} className="flex gap-1.5 px-3 pb-2">
              <input
                autoFocus
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="z.B. Anlage 4711 oder Siemens-Handbücher"
                className="min-w-0 flex-1 rounded-md border border-border bg-surface px-2 py-1.5 text-sm"
              />
              <button className="rounded-md bg-accent px-2.5 text-sm font-medium text-accent-fg">OK</button>
            </form>
          )}
          {error && <p className="px-4 pb-2 text-xs text-danger">{error}</p>}

          {sources.length === 0 && !creating && (
            <p className="px-4 pb-2 text-sm text-muted">
              Lege mit + eine Wissensquelle an und lade Pläne, Stücklisten, AWL-Quellen oder Handbücher hoch.
            </p>
          )}

          <ul>
            {sources.map((source) => (
              <li key={source.id}>
                <div className="group flex items-center gap-2 px-4 py-1.5 hover:bg-surface-2">
                  <input
                    type="checkbox"
                    checked={selectedSourceIds.includes(source.id)}
                    onChange={() => onToggleSource(source.id)}
                    className="accent-[var(--accent)]"
                    aria-label={`${source.name} im Chat verwenden`}
                  />
                  <button
                    className="min-w-0 flex-1 truncate text-left text-sm"
                    onClick={() => setExpanded(expanded === source.id ? null : source.id)}
                    aria-expanded={expanded === source.id}
                  >
                    {source.name}
                    <span className="ml-1.5 text-xs text-muted">{source.document_count}</span>
                  </button>
                  <button
                    onClick={() => deleteSource(source)}
                    className="text-muted opacity-0 hover:text-danger focus:opacity-100 group-hover:opacity-100"
                    aria-label={`${source.name} löschen`}
                  >
                    ✕
                  </button>
                </div>
                {expanded === source.id && (
                  <SourcePanel sourceId={source.id} onChanged={onSourcesChanged} onOpenPage={onOpenPage} />
                )}
              </li>
            ))}
          </ul>
          {sources.length > 0 && (
            <p className="px-4 pt-1 text-xs text-muted">
              {selectedSourceIds.length === 0
                ? "Keine Auswahl: der Chat durchsucht alle Quellen."
                : `Chat durchsucht ${selectedSourceIds.length} von ${sources.length} Quellen.`}
            </p>
          )}
        </section>

        <section className="mt-5">
          <div className="flex items-center justify-between px-4 pb-1.5">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-muted">Chats</h2>
            <button
              onClick={onNewConversation}
              className="rounded-md px-1.5 text-lg leading-none text-muted hover:bg-surface-2 hover:text-text"
              aria-label="Neuer Chat"
            >
              +
            </button>
          </div>
          <ul>
            {conversations.map((conversation) => (
              <li
                key={conversation.id}
                className={`group flex items-center gap-2 px-4 py-1.5 text-sm hover:bg-surface-2 ${
                  conversation.id === activeConversationId ? "bg-surface-2 font-medium" : ""
                }`}
              >
                <button
                  className="min-w-0 flex-1 truncate text-left"
                  onClick={() => onSelectConversation(conversation)}
                >
                  {conversation.title}
                </button>
                <button
                  onClick={() => onDeleteConversation(conversation)}
                  className="text-muted opacity-0 hover:text-danger focus:opacity-100 group-hover:opacity-100"
                  aria-label={`Chat „${conversation.title}“ löschen`}
                >
                  ✕
                </button>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  );
}
