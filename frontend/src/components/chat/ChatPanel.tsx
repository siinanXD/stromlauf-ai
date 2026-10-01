"use client";

import { ArrowDown, ArrowUp, Plus, Square } from "lucide-react";
import { useEffect, useEffectEvent, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { useStickToBottom } from "use-stick-to-bottom";

import { prefetchFaultHits } from "@/components/answer/faultHitsStore";
import type { AnswerBlocksContext } from "@/components/chat/AnswerView";
import { Message } from "@/components/Message";
import type { PageTarget } from "@/components/PageViewer";
import { api, streamChat, type AnswerMeta, type ChatMessage } from "@/lib/api";
import { lastAnswerMeta } from "@/lib/chatMemory";

import { olderBefore, olderPage, PAGE_SIZE } from "./history";

const EMPTY_META: AnswerMeta = { referenced_tags: [], citations: [], evidence: [] };

export interface ChatScope {
  /** Wissensquellen, die der Agent durchsuchen darf; leer = alle. */
  sourceIds: string[];
  /** Maschinen-Chat: Backend legt den Scope auf die Quelle der Maschine fest und gibt dem Agenten den Kontext. */
  machineId?: string;
}

/** Nachricht im Verlauf mit stabilem Schluessel, auch wenn aeltere Seiten vorne dazukommen. */
type Entry = ChatMessage & { key: string };

/** Platzhalter: keine Konversation gehoert gerade dem eigenen Stream. */
const NOT_OWNED = "#nicht-eigen";

let liveCounter = 0;
const liveKey = () => `l${(liveCounter += 1)}`;
const withKeys = (messages: ChatMessage[]): Entry[] => messages.map((m, i) => ({ ...m, key: typeof m.index === "number" ? `m${m.index}` : `h${i}` }));

/**
 * Nachrichtenliste plus Eingabe; der Verlauf haengt an conversationId. Wechselt die ID von aussen,
 * laedt das Panel die letzten 30 Nachrichten, aeltere beim Hochscrollen; null = neuer Chat. Die vom Stream
 * vergebene ID meldet es per onConversationId. autoSend schickt eine Meldung sofort ab (neuer Stoerfall).
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
  blocks,
  autoSend,
  onSendStart,
  onSendSettled,
}: {
  scope: ChatScope;
  conversationId: string | null;
  onConversationId: (id: string, title: string) => void;
  onConversationsChanged: () => void;
  onOpenPage: (target: PageTarget) => void;
  activeReference: string | null;
  emptyState: ReactNode;
  initialInput?: string;
  banner?: ReactNode;
  placeholder?: string;
  /** Antwort-Vertrag am Ende des Streams: Maschinenseite markiert die Bauteile im Modell. */
  onMeta?: (meta: AnswerMeta) => void;
  /** Klick auf einen Bauteil-Chip unter der Antwort (werksweiter Chat). */
  onOpenPart?: (tag: string) => void;
  /** "Im Modell zeigen" unter der Antwort. */
  onShowInModel?: (tags: string[]) => void;
  /** Maschinen-Chat: Antworten als Bloecke, Fehlerliste startet beim Senden parallel. */
  blocks?: AnswerBlocksContext;
  /** Meldung, die beim Erscheinen sofort gesendet wird; key verhindert doppeltes Senden. */
  autoSend?: { key: string; text: string };
  /** Ein Senden beginnt (auch "Erneut versuchen"). */
  onSendStart?: () => void;
  /** Senden beendet: conversationId null heisst, der Server hat keinen Chat angelegt (Fehler vor "conversation"). */
  onSendSettled?: (result: { conversationId: string | null; failed: boolean }) => void;
}) {
  const [messages, setMessages] = useState<Entry[]>([]);
  const [input, setInput] = useState(initialInput);
  const [streaming, setStreaming] = useState(false);
  const [announcement, setAnnouncement] = useState("");
  const [older, setOlder] = useState<"idle" | "loading" | "error">("idle");
  const abortRef = useRef<AbortController | null>(null);
  const ownedIdRef = useRef<string | null>(null);
  const sentKeyRef = useRef<string | null>(null);
  const anchorRef = useRef<{ height: number; top: number } | null>(null);
  const { scrollRef, contentRef, isAtBottom, scrollToBottom } = useStickToBottom({ initial: "instant", resize: "smooth" });

  // Neue Vorbelegung von aussen (z. B. Klick auf eine Fehlerzeile) uebernehmen: Zustand beim Rendern angleichen
  const [lastInitial, setLastInitial] = useState(initialInput);
  if (initialInput !== lastInitial) {
    setLastInitial(initialInput);
    setInput(initialInput);
  }

  const machineId = scope.machineId;

  // Verlauf anzeigen; als Ereignis, damit wechselnde Callbacks des Aufrufers kein neues Laden ausloesen
  const showHistory = useEffectEvent((result: ChatMessage[]) => {
    setMessages(withKeys(result));
    setOlder("idle");
    onMeta?.(lastAnswerMeta(result) ?? EMPTY_META);
    void scrollToBottom("instant");
  });

  useEffect(() => {
    // Vom eigenen Stream vergeben (oder neuer Chat beim Start): der Verlauf ist schon da
    if (conversationId === ownedIdRef.current) return;
    abortRef.current?.abort();
    // Ab jetzt gehoert keine ID mehr dem Stream; so laedt auch ein zweiter Effektlauf (StrictMode) den Verlauf
    ownedIdRef.current = NOT_OWNED;
    let cancelled = false;
    // null = neuer Chat: leerer Verlauf (asynchron wie das Laden, damit kein setState direkt im Effekt steht).
    // Der Verlauf traegt das meta je Antwort (Issue #47): die Maschinenseite markiert die letzte Antwort im Modell
    // oder hebt eine alte Markierung auf. Ein Server ohne Seiten liefert alles; das Nachladen entfaellt dann.
    const load = conversationId ? api.getMessagesPage(conversationId, PAGE_SIZE, undefined, machineId) : Promise.resolve<ChatMessage[]>([]);
    load
      .then((result) => {
        if (!cancelled) showHistory(result);
      })
      .catch(() => {
        if (!cancelled) showHistory([]);
      });
    return () => {
      cancelled = true;
    };
  }, [conversationId, machineId]);

  // Aeltere Seite vorne angefuegt: Scrollposition halten, damit der Leser an derselben Stelle bleibt
  useLayoutEffect(() => {
    const anchor = anchorRef.current;
    const element = scrollRef.current;
    if (!anchor || !element) return;
    anchorRef.current = null;
    element.scrollTop = anchor.top + (element.scrollHeight - anchor.height);
  }, [messages, scrollRef]);

  const before = olderBefore(messages);

  async function loadOlder() {
    if (!conversationId || before === null || older === "loading") return;
    const element = scrollRef.current;
    setOlder("loading");
    try {
      const page = await api.getMessagesPage(conversationId, PAGE_SIZE, before, machineId);
      if (element) anchorRef.current = { height: element.scrollHeight, top: element.scrollTop };
      setMessages((current) => [...withKeys(olderPage(current, page)), ...current]);
      setOlder("idle");
    } catch {
      setOlder("error");
    }
  }

  function updateLast(change: (message: Entry) => Entry) {
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
    onSendStart?.();
    let received: string | null = null;
    let failed = false;
    // Fehlerliste parallel zum Chat, ohne Modell: der erste Block steht, bevor der Text kommt
    if (blocks && machineId) void prefetchFaultHits(machineId, question);
    setMessages((current) => [
      ...current,
      { role: "user", content: question, tool_calls: [], sources: [], key: liveKey() },
      { role: "assistant", content: "", tool_calls: [], sources: [], key: liveKey() },
    ]);
    void scrollToBottom("smooth");
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      const events = streamChat({ conversation_id: conversationId, message: question, source_ids: scope.sourceIds, machine_id: machineId }, controller.signal);
      for await (const { event, data } of events) {
        if (event === "conversation") {
          ownedIdRef.current = data.id;
          received = data.id;
          onConversationId(data.id, data.title);
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
          const n = Array.isArray(data.referenced_tags) ? data.referenced_tags.length : 0;
          setAnnouncement(n > 0 ? `Antwort fertig, ${n} ${n === 1 ? "Bauteil" : "Bauteile"} in der Antwort.` : "Antwort fertig.");
        } else if (event === "error") {
          // Rohtext merken; die Antwort zeigt einen Satz fuer Menschen und den Text nur unter "Details"
          failed = true;
          updateLast((m) => ({ ...m, error: data.message || "Fehler ohne Text" }));
        }
      }
    } catch (err) {
      failed = true;
      if (!controller.signal.aborted) {
        const message = (err as Error).message;
        updateLast((m) => ({ ...m, error: message || "Fehler ohne Text" }));
        // 402 vom Backend: Banner in der AppShell aktualisieren
        if (message.includes("Monatslimit")) window.dispatchEvent(new CustomEvent("stromlauf:budget"));
      }
    } finally {
      updateLast((m) => ({ ...m, content: m.content.trim() }));
      setStreaming(false);
      abortRef.current = null;
      onConversationsChanged();
      onSendSettled?.({ conversationId: received ?? conversationId, failed });
    }
  }

  /** Letzte Frage nach einem Fehler noch einmal senden: fehlgeschlagenes Paar entfernen, neu abschicken. */
  function retry() {
    const last = messages[messages.length - 1];
    const question = messages[messages.length - 2];
    if (!last?.error || question?.role !== "user") return;
    setMessages((current) => current.slice(0, -2));
    void send(question.content);
  }

  // Meldung von aussen (neuer Stoerfall oder "Erneut versuchen" in der Liste): ein fehlgeschlagenes Paar ersetzen
  const sendFromOutside = useEffectEvent((text: string) => {
    const last = messages[messages.length - 1];
    if (last?.error && messages[messages.length - 2]?.role === "user") setMessages((current) => current.slice(0, -2));
    void send(text);
  });
  useEffect(() => {
    if (!autoSend || autoSend.key === sentKeyRef.current) return;
    sentKeyRef.current = autoSend.key;
    sendFromOutside(autoSend.text);
  }, [autoSend]);

  const lastMessage = messages[messages.length - 1];
  const canRetry = !streaming && Boolean(lastMessage?.error) && messages[messages.length - 2]?.role === "user";

  return (
    <div className="relative flex h-full min-h-0 flex-1 flex-col">
      {banner && <div className="border-b-[0.5px] border-border bg-primary-soft px-4 py-2 text-footnote">{banner}</div>}
      <div
        ref={scrollRef}
        className="min-h-0 flex-1 overflow-y-auto"
        onScroll={(event) => {
          if (event.currentTarget.scrollTop < 120 && before !== null && older === "idle") void loadOlder();
        }}
      >
        <div ref={contentRef} className="mx-auto max-w-3xl space-y-3 px-4 pt-4 pb-6 lg:px-6">
          {before !== null && (
            <div className="flex justify-center">
              <button
                type="button"
                onClick={() => void loadOlder()}
                disabled={older === "loading"}
                className="min-h-11 rounded-full bg-bg-fill px-4 text-footnote font-semibold text-primary hover:bg-muted disabled:opacity-60"
              >
                {older === "loading" ? "Lade ältere Nachrichten …" : older === "error" ? "Ältere Nachrichten: erneut versuchen" : "Ältere Nachrichten laden"}
              </button>
            </div>
          )}
          {messages.length === 0 ? (
            <div className="pt-[8vh]">{emptyState}</div>
          ) : (
            messages.map((message, index) => (
              <Message
                key={message.key}
                message={message}
                question={messages[index - 1]?.role === "user" ? messages[index - 1].content : ""}
                streaming={streaming && index === messages.length - 1}
                sourceIds={scope.sourceIds}
                activeReference={activeReference}
                onOpen={onOpenPage}
                onOpenPart={onOpenPart}
                onShowInModel={onShowInModel}
                blocks={blocks}
              />
            ))
          )}
          {canRetry && (
            <div className="flex justify-start">
              <button type="button" onClick={retry} className="min-h-11 rounded-md bg-bg-fill px-4 text-subhead font-semibold text-primary hover:bg-muted">
                Erneut versuchen
              </button>
            </div>
          )}
        </div>
      </div>
      {!isAtBottom && messages.length > 0 && (
        <button
          type="button"
          onClick={() => void scrollToBottom("smooth")}
          className="absolute bottom-24 left-1/2 flex min-h-11 -translate-x-1/2 items-center gap-1.5 rounded-full bg-popover px-4 text-footnote font-semibold text-primary shadow-floating"
        >
          <ArrowDown className="size-3.5" aria-hidden />
          Zum Ende
        </button>
      )}
      <p className="sr-only-live" aria-live="polite" role="status">
        {announcement}
      </p>
      {/* Eingabe (Figma "Eingabe"): Milchglas-Leiste, darin das gefuellte Feld wie die Meldung-Eingabe */}
      <form
        className="border-t-[0.5px] border-border bg-bg-bar px-4 pt-3 pb-4 backdrop-blur-bar lg:px-6"
        onSubmit={(event) => {
          event.preventDefault();
          void send(input);
        }}
      >
        <div className="mx-auto flex max-w-3xl items-end gap-2">
          <label className="flex min-h-11 min-w-0 flex-1 cursor-text items-start gap-2 rounded-md bg-bg-fill px-3 focus-within:ring-3 focus-within:ring-ring/50">
            <span className="mt-[11px] grid size-[22px] shrink-0 place-items-center rounded-full bg-accent text-white" aria-hidden>
              <Plus className="size-3.5" strokeWidth={3} />
            </span>
            <textarea
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  void send(input);
                }
              }}
              rows={Math.min(6, input.split("\n").length)}
              placeholder={placeholder}
              aria-label={placeholder}
              className="min-h-11 min-w-0 flex-1 resize-none bg-transparent py-[11px] text-body outline-none"
            />
          </label>
          {streaming ? (
            <button
              type="button"
              onClick={() => abortRef.current?.abort()}
              className="grid size-11 shrink-0 place-items-center rounded-full bg-bg-fill text-foreground hover:bg-muted"
              aria-label="Stopp"
              title="Stopp"
            >
              <Square className="size-4 fill-current" aria-hidden />
            </button>
          ) : (
            <button
              disabled={!input.trim()}
              className="grid size-11 shrink-0 place-items-center rounded-full bg-primary text-primary-foreground disabled:bg-bg-fill disabled:text-muted-foreground"
              aria-label="Senden"
              title="Senden (Enter)"
            >
              <ArrowUp className="size-5" strokeWidth={2.5} aria-hidden />
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
        <button key={example} onClick={() => onPick(example)} className="min-h-11 rounded-lg bg-card p-3 text-left text-subhead shadow-card hover:bg-bg-fill">
          {example}
        </button>
      ))}
    </div>
  );
}
