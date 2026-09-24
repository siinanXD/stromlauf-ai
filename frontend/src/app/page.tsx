"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { Message } from "@/components/Message";
import { PageViewer, type PageTarget } from "@/components/PageViewer";
import { Sidebar } from "@/components/Sidebar";
import {
  api,
  streamChat,
  type ChatMessage,
  type Conversation,
  type Health,
  type KnowledgeSource,
  type SourceRef,
} from "@/lib/api";

const EXAMPLES = [
  "Wo ist Schütz -K12 verbaut und was schaltet es?",
  "Welcher SPS-Eingang hängt an Klemme -X1:5 und in welchem Netzwerk wird er verwendet?",
  "Erkläre mir FB 10 Netzwerk für Netzwerk.",
  "Motor -M1 läuft nicht an: welche Bedingungen müssen erfüllt sein?",
];

export default function Home() {
  const [health, setHealth] = useState<Health | null>(null);
  const [backendError, setBackendError] = useState<string | null>(null);
  const [sources, setSources] = useState<KnowledgeSource[]>([]);
  const [selectedSourceIds, setSelectedSourceIds] = useState<string[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [pageTarget, setPageTarget] = useState<PageTarget | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const loadSources = useCallback(() => api.listSources().then(setSources).catch(() => {}), []);
  const loadConversations = useCallback(
    () => api.listConversations().then(setConversations).catch(() => {}),
    [],
  );

  useEffect(() => {
    api
      .health()
      .then((result) => {
        setHealth(result);
        loadSources();
        loadConversations();
      })
      .catch(() => setBackendError("Backend nicht erreichbar. Läuft es auf Port 8010?"));
  }, [loadSources, loadConversations]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [messages]);

  function updateLast(change: (message: ChatMessage) => ChatMessage) {
    setMessages((current) => {
      const last = current[current.length - 1];
      // Nach Chat-Wechsel/Abbruch kann die Liste leer sein oder mit einer Nutzerfrage enden
      if (last?.role !== "assistant") return current;
      return [...current.slice(0, -1), change(last)];
    });
  }

  async function send(text: string) {
    const question = text.trim();
    if (!question || streaming) return;
    setInput("");
    setStreaming(true);
    setMessages((current) => [
      ...current,
      { role: "user", content: question, tool_calls: [], sources: [] },
      { role: "assistant", content: "", tool_calls: [], sources: [] },
    ]);

    const controller = new AbortController();
    abortRef.current = controller;
    try {
      const events = streamChat(
        { conversation_id: conversationId, message: question, source_ids: selectedSourceIds },
        controller.signal,
      );
      for await (const { event, data } of events) {
        if (event === "conversation") setConversationId(data.id);
        else if (event === "token") updateLast((m) => ({ ...m, content: m.content + data.text }));
        else if (event === "tool_start")
          updateLast((m) => ({ ...m, tool_calls: [...m.tool_calls, { ...data, done: false }] }));
        else if (event === "tool_end")
          updateLast((m) => {
            const index = m.tool_calls.findIndex((c) => c.name === data.name && !c.done);
            return {
              ...m,
              tool_calls: m.tool_calls.map((c, i) => (i === index ? { ...c, done: true } : c)),
            };
          });
        else if (event === "sources") updateLast((m) => ({ ...m, sources: data }));
        else if (event === "error") updateLast((m) => ({ ...m, error: data.message }));
      }
    } catch (err) {
      if (!controller.signal.aborted) updateLast((m) => ({ ...m, error: (err as Error).message }));
    } finally {
      updateLast((m) => ({ ...m, content: m.content.trim() }));
      setStreaming(false);
      abortRef.current = null;
      loadConversations();
    }
  }

  async function selectConversation(conversation: Conversation) {
    abortRef.current?.abort();
    setConversationId(conversation.id);
    setSelectedSourceIds(conversation.source_ids.filter((id) => sources.some((s) => s.id === id)));
    setSidebarOpen(false);
    setMessages(await api.getMessages(conversation.id).catch(() => []));
  }

  function newConversation() {
    abortRef.current?.abort();
    setConversationId(null);
    setMessages([]);
    setSidebarOpen(false);
  }

  async function deleteConversation(conversation: Conversation) {
    if (!confirm(`Chat „${conversation.title}“ löschen?`)) return;
    await api.deleteConversation(conversation.id).catch(() => {});
    if (conversation.id === conversationId) newConversation();
    loadConversations();
  }

  function openSource(source: SourceRef) {
    if (!source.page) return;
    setPageTarget({ documentId: source.document_id, filename: source.filename, page: source.page });
  }

  return (
    <div className="flex h-full">
      <aside
        className={`fixed inset-y-0 left-0 z-40 w-80 max-w-[88vw] border-r border-border bg-surface transition-transform md:static md:translate-x-0 ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <Sidebar
          sources={sources}
          selectedSourceIds={selectedSourceIds}
          onToggleSource={(id) =>
            setSelectedSourceIds((current) =>
              current.includes(id) ? current.filter((s) => s !== id) : [...current, id],
            )
          }
          onSourcesChanged={loadSources}
          conversations={conversations}
          activeConversationId={conversationId}
          onSelectConversation={selectConversation}
          onNewConversation={newConversation}
          onDeleteConversation={deleteConversation}
          onOpenPage={setPageTarget}
        />
      </aside>
      {sidebarOpen && (
        <div className="fixed inset-0 z-30 bg-black/40 md:hidden" onClick={() => setSidebarOpen(false)} />
      )}

      <main className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-3 border-b border-border px-4 py-2.5 md:hidden">
          <button onClick={() => setSidebarOpen(true)} aria-label="Menü öffnen" className="text-xl">
            ☰
          </button>
          <span className="font-semibold">Stromlauf AI</span>
        </header>

        {(backendError || (health && !health.api_key_configured)) && (
          <p className="border-b border-border bg-accent-soft px-4 py-2 text-sm">
            {backendError ??
              "ANTHROPIC_API_KEY fehlt: In .env eintragen und das Backend neu starten. Upload und Verwaltung funktionieren bereits."}
          </p>
        )}

        <div className="min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto max-w-3xl space-y-6 px-4 py-6">
            {messages.length === 0 ? (
              <div className="pt-[12vh]">
                <h1 className="text-2xl font-semibold tracking-tight">Was möchtest du über die Anlage wissen?</h1>
                <p className="mt-2 text-muted">
                  Ich verfolge Betriebsmittel, Klemmen und SPS-Adressen über Stromlaufplan, Stückliste,
                  Klemmenplan, AWL-Programm und Handbücher hinweg.
                </p>
                <div className="mt-6 grid gap-2 sm:grid-cols-2">
                  {EXAMPLES.map((example) => (
                    <button
                      key={example}
                      onClick={() => setInput(example)}
                      className="rounded-xl border border-border bg-surface p-3 text-left text-sm hover:border-accent"
                    >
                      {example}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((message, index) => (
                <Message
                  key={index}
                  message={message}
                  streaming={streaming && index === messages.length - 1}
                  onOpenSource={openSource}
                />
              ))
            )}
            <div ref={bottomRef} />
          </div>
        </div>

        <form
          className="border-t border-border bg-surface px-4 py-3"
          onSubmit={(event) => {
            event.preventDefault();
            send(input);
          }}
        >
          <div className="mx-auto flex max-w-3xl items-end gap-2">
            <textarea
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  send(input);
                }
              }}
              rows={Math.min(6, input.split("\n").length)}
              placeholder="Frage zur Anlage stellen … (Enter sendet, Shift+Enter neue Zeile)"
              className="min-w-0 flex-1 resize-none rounded-xl border border-border bg-bg px-3.5 py-2.5 outline-none focus:border-accent"
            />
            {streaming ? (
              <button
                type="button"
                onClick={() => abortRef.current?.abort()}
                className="rounded-xl border border-border px-4 py-2.5 font-medium hover:bg-surface-2"
              >
                Stopp
              </button>
            ) : (
              <button
                disabled={!input.trim()}
                className="rounded-xl bg-accent px-4 py-2.5 font-medium text-accent-fg disabled:opacity-40"
              >
                Senden
              </button>
            )}
          </div>
        </form>
      </main>

      {pageTarget && <PageViewer target={pageTarget} onClose={() => setPageTarget(null)} />}
    </div>
  );
}
