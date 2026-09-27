"use client";

import { useCallback, useEffect, useState } from "react";

import { ChatPanel, ExampleQuestions } from "@/components/chat/ChatPanel";
import type { PageTarget } from "@/components/PageViewer";
import { api, type Conversation, type MachineDetail } from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * Chat je Maschine: Scope ist fest ihre Wissensquelle (Backend erzwingt das ueber machine_id), Fehlerlisten
 * bleiben werksweit (search_faults). Links die Chats dieser Maschine, rechts der Verlauf.
 */
export function MachineChatTab({
  machine,
  onOpenPage,
  activeReference,
}: {
  machine: MachineDetail;
  onOpenPage: (target: PageTarget) => void;
  activeReference: string | null;
}) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [initialInput, setInitialInput] = useState("");
  const sourceId = machine.source_id;

  const loadConversations = useCallback(() => {
    if (!sourceId) return;
    api.listConversations(sourceId).then(setConversations).catch(() => {});
  }, [sourceId]);

  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  if (!sourceId) {
    return <p className="text-sm text-muted-foreground">Keine Dokumentation verknüpft. Im Tab „Dokumente“ eine Wissensquelle wählen, dann gibt es hier den Chat zu dieser Maschine.</p>;
  }

  async function remove(conversation: Conversation) {
    if (!confirm(`Chat „${conversation.title}“ löschen?`)) return;
    await api.deleteConversation(conversation.id).catch(() => {});
    if (conversation.id === conversationId) setConversationId(null);
    loadConversations();
  }

  const examples = [
    `Welche Bedingungen müssen erfüllt sein, damit ${machine.name} anläuft?`,
    "Was steht in der Fehlerliste zu „steht“ oder „Störung“?",
    "Welche Not-Halt-Kette hat diese Maschine?",
    "Welche SPS-Eingänge gehören zu den Sensoren am Einlauf?",
  ];

  return (
    <div className="grid h-full min-h-[560px] grid-cols-1 gap-0 border border-line bg-card md:grid-cols-[240px_minmax(0,1fr)]">
      <aside className="flex min-h-0 flex-col border-b border-border md:border-b-0 md:border-r">
        <div className="flex items-center justify-between px-3 py-2">
          <span className="font-mono text-[11px] font-semibold uppercase tracking-[0.06em] text-muted-foreground">Chats zu {machine.name}</span>
          <button onClick={() => setConversationId(null)} className="px-1.5 text-lg leading-none text-muted-foreground hover:text-foreground" aria-label="Neuer Chat">
            +
          </button>
        </div>
        <ul className="min-h-0 flex-1 overflow-y-auto">
          {conversations.length === 0 && <li className="px-3 pb-2 text-xs text-muted-foreground">Noch kein Chat. Frage unten stellen.</li>}
          {conversations.map((c) => (
            <li key={c.id} className={cn("group flex items-center gap-2 px-3 py-1.5 text-sm hover:bg-secondary", c.id === conversationId && "bg-secondary font-medium")}>
              <button className="min-w-0 flex-1 truncate text-left" onClick={() => setConversationId(c.id)}>
                {c.title}
              </button>
              <button onClick={() => remove(c)} className="text-muted-foreground opacity-0 hover:text-danger focus:opacity-100 group-hover:opacity-100" aria-label={`Chat „${c.title}“ löschen`}>
                ✕
              </button>
            </li>
          ))}
        </ul>
        <p className="border-t border-border px-3 py-2 text-xs text-muted-foreground">
          Scope: nur {machine.source_name ?? "diese Wissensquelle"}. Fehlerlisten aller Maschinen bleiben durchsuchbar.
        </p>
      </aside>
      <ChatPanel
        scope={{ sourceIds: [sourceId], machineId: machine.id }}
        conversationId={conversationId}
        onConversationId={setConversationId}
        onConversationsChanged={loadConversations}
        onOpenPage={onOpenPage}
        activeReference={activeReference}
        initialInput={initialInput}
        placeholder={`Frage zu ${machine.name} … (Enter sendet)`}
        emptyState={
          <>
            <h2 className="text-xl font-semibold tracking-tight">Was willst du über {machine.name} wissen?</h2>
            <p className="mt-2 text-sm text-muted-foreground">Antworten kommen nur aus der Dokumentation dieser Maschine. Erfahrungen aus den Fehlerlisten anderer Maschinen werden als solche gekennzeichnet.</p>
            <ExampleQuestions examples={examples} onPick={setInitialInput} />
          </>
        }
      />
    </div>
  );
}
