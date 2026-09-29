"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

import { Message } from "@/components/Message";
import type { PageTarget } from "@/components/PageViewer";
import { api, streamChat, type AnswerMeta, type ChatMessage } from "@/lib/api";
import { lastAnswerMeta } from "@/lib/chatMemory";

const EMPTY_META: AnswerMeta = { referenced_tags: [], citations: [], evidence: [] };

export interface ChatScope {
  /** Wissensquellen, die der Agent durchsuchen darf; leer = alle. */
  sourceIds: string[];
  /** Maschinen-Chat: Backend legt den Scope auf die Quelle der Maschine fest und gibt dem Agenten den Kontext. */
  machineId?: string;
}

/**
 * Nachrichtenliste plus Eingabe; der Verlauf haengt an conversationId. Wechselt die ID von aussen,
 * laedt das Panel den Verlauf; null = neuer Chat. Die vom Stream vergebene ID meldet es per onConversationId.
 */
export function ChatPanel({
  scope,
  conversationId,
  onConversationId,
  onConversationsChanged,
  onOpenPage,
  activeReference,
  emptyState,
  initialInput = "",
  banner,
  placeholder = "Frage zur Anlage stellen … (Enter sendet, Shift+Enter neue Zeile)",
  onMeta,
  onOpenPart,
  onShowInModel,
}: {
  scope: ChatScope;
  conversationId: string | null;
  onConversationId: (id: string) => void;
  onConversationsChanged: () => void;
  onOpenPage: (target: PageTarget) => void;
  activeReference: string | null;
  emptyState: ReactNode;
  initialInput?: string;
  banner?: ReactNode;
  placeholder?: string;
  /** Antwort-Vertrag am Ende des Streams: Maschinenseite markiert die Bauteile im Modell. */
  onMeta?: (meta: AnswerMeta) => void;
  /** Klick auf einen Bauteil-Chip unter der Antwort. */
  onOpenPart?: (tag: string) => void;
  /** "Im Modell zeigen" unter der Antwort. */
  onShowInModel?: (tags: string[]) => void;
}) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState(initialInput);
  const [streaming, setStreaming] = useState(false);
  const [announcement, setAnnouncement] = useState("");
  const abortRef = useRef<AbortController | null>(null);
  const ownedIdRef = useRef<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Neue Vorbelegung von aussen (z. B. Klick auf eine Fehlerzeile) uebernehmen: Zustand beim Rendern angleichen
  const [lastInitial, setLastInitial] = useState(initialInput);
  if (initialInput !== lastInitial) {
    setLastInitial(initialInput);
    setInput(initialInput);
  }

  const machineId = scope.machineId;
  useEffect(() => {
    if (conversationId === ownedIdRef.current) return; // vom eigenen Stream vergeben: Verlauf ist schon da
    abortRef.current?.abort();
    ownedIdRef.current = conversationId;
    let cancelled = false;
    // null = neuer Chat: leerer Verlauf (asynchron wie das Laden, damit kein setState direkt im Effekt steht).
    // Der Verlauf traegt das meta je Antwort (Issue #47): die Maschinenseite markiert die letzte Antwort im Modell
    // oder hebt eine alte Markierung auf.
    const load = conversationId ? api.getMessages(conversationId, machineId) : Promise.resolve<ChatMessage[]>([]);
    load
      .then((result) => {
        if (cancelled) return;
        setMessages(result);
        onMeta?.(lastAnswerMeta(result) ?? EMPTY_META);
      })
      .catch(() => {
        if (cancelled) return;
        setMessages([]);
        onMeta?.(EMPTY_META);
      });
    return () => {
      cancelled = true;
    };
  }, [conversationId, machineId, onMeta]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [messages]);

  function updateLast(change: (message: ChatMessage) => ChatMessage) {
    setMessages((current) => {
      const last = current[current.length - 1];
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
        { conversation_id: conversationId, message: question, source_ids: scope.sourceIds, machine_id: scope.machineId },
        controller.signal,
      );
      for await (const { event, data } of events) {
        if (event === "conversation") {
          ownedIdRef.current = data.id;
          onConversationId(data.id);
        } else if (event === "token") updateLast((m) => ({ ...m, content: m.content + data.text }));
        else if (event === "tool_start") updateLast((m) => ({ ...m, tool_calls: [...m.tool_calls, { ...data, done: false }] }));
        else if (event === "tool_end")
          updateLast((m) => {
            const index = m.tool_calls.findIndex((c) => c.name === data.name && !c.done);
            return { ...m, tool_calls: m.tool_calls.map((c, i) => (i === index ? { ...c, done: true } : c)) };
          });
        else if (event === "sources") updateLast((m) => ({ ...m, sources: data }));
        else if (event === "usage") updateLast((m) => ({ ...m, cost_cents: (m.cost_cents ?? 0) + data.cost_cents }));
        else if (event === "meta") {
          updateLast((m) => ({ ...m, meta: data }));
          onMeta?.(data);
          const n = data.referenced_tags.length;
          setAnnouncement(n > 0 ? `Antwort fertig, ${n} ${n === 1 ? "Bauteil" : "Bauteile"} im Modell markiert.` : "Antwort fertig.");
        }
        else if (event === "error") updateLast((m) => ({ ...m, error: data.message }));
      }
    } catch (err) {
      if (!controller.signal.aborted) {
        const message = (err as Error).message;
        updateLast((m) => ({ ...m, error: message }));
        // 402 vom Backend: Banner in der AppShell aktualisieren
        if (message.includes("Monatslimit")) window.dispatchEvent(new CustomEvent("stromlauf:budget"));
      }
    } finally {
      updateLast((m) => ({ ...m, content: m.content.trim() }));
      setStreaming(false);
      abortRef.current = null;
      onConversationsChanged();
    }
  }

  return (
    <div className="flex h-full min-h-0 flex-1 flex-col">
      {banner && <p className="border-b border-border bg-primary/10 px-4 py-2 text-sm">{banner}</p>}
      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto max-w-3xl space-y-6 px-4 py-6">
          {messages.length === 0 ? (
            <div className="pt-[8vh]">{typeof emptyState === "function" ? null : emptyState}</div>
          ) : (
            messages.map((message, index) => (
              <Message
                key={index}
                message={message}
                question={messages[index - 1]?.role === "user" ? messages[index - 1].content : ""}
                streaming={streaming && index === messages.length - 1}
                sourceIds={scope.sourceIds}
                activeReference={activeReference}
                onOpen={onOpenPage}
                onOpenPart={onOpenPart}
                onShowInModel={onShowInModel}
              />
            ))
          )}
          <div ref={bottomRef} />
        </div>
      </div>
      <p className="sr-only-live" aria-live="polite" role="status">
        {announcement}
      </p>
      <form
        className="border-t border-border bg-card px-4 py-3"
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
            placeholder={placeholder}
            className="min-w-0 flex-1 resize-none rounded-xl border border-border bg-background px-3.5 py-2.5 outline-none focus:border-primary"
          />
          {streaming ? (
            <button type="button" onClick={() => abortRef.current?.abort()} className="rounded-xl border border-border px-4 py-2.5 font-medium hover:bg-secondary">
              Stopp
            </button>
          ) : (
            <button disabled={!input.trim()} className="rounded-xl bg-primary px-4 py-2.5 font-medium text-primary-foreground disabled:opacity-40">
              Senden
            </button>
          )}
        </div>
      </form>
    </div>
  );
}

/** Beispielfragen als Kacheln; Klick uebernimmt die Frage in die Eingabe (ueber initialInput des Aufrufers). */
export function ExampleQuestions({ examples, onPick }: { examples: string[]; onPick: (q: string) => void }) {
  return (
    <div className="mt-6 grid gap-2 sm:grid-cols-2">
      {examples.map((example) => (
        <button key={example} onClick={() => onPick(example)} className="rounded-xl border border-border bg-card p-3 text-left text-sm hover:border-primary">
          {example}
        </button>
      ))}
    </div>
  );
}
