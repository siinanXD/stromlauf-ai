"use client";

import { Plus } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { ChatPanel, ExampleQuestions } from "@/components/chat/ChatPanel";
import type { PageTarget } from "@/components/PageViewer";
import { api, type AnswerMeta, type Conversation, type MachineDetail } from "@/lib/api";

/**
 * Chat je Maschine (chat-first, MB-4): Scope ist fest ihre Wissensquelle (Backend erzwingt das ueber
 * machine_id). Der Verlauf sitzt als Auswahl in der Kopfzeile; der Composer bleibt unten.
 */
export function MachineChatTab({
  machine,
  onOpenPage,
  activeReference,
  onMeta,
  onOpenPart,
  onShowInModel,
  onGoToDocuments,
}: {
  machine: MachineDetail;
  onOpenPage: (target: PageTarget) => void;
  activeReference: string | null;
  onMeta?: (meta: AnswerMeta) => void;
  onOpenPart?: (tag: string) => void;
  onShowInModel?: (tags: string[]) => void;
  onGoToDocuments?: () => void;
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
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center" data-testid="chat-no-source">
        <p className="text-sm text-muted-foreground">Keine Dokumentation verknüpft. Ohne Doku gibt es keine belegten Antworten.</p>
        {onGoToDocuments && (
          <button type="button" onClick={onGoToDocuments} className="rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground">
            Dokumente verknüpfen
          </button>
        )}
      </div>
    );
  }

  async function remove() {
    const conversation = conversations.find((c) => c.id === conversationId);
    if (!conversation || !confirm(`Chat „${conversation.title}“ löschen?`)) return;
    await api.deleteConversation(conversation.id).catch(() => {});
    setConversationId(null);
    loadConversations();
  }

  const examples = [
    `Welche Bedingungen müssen erfüllt sein, damit ${machine.name} anläuft?`,
    "Was steht in der Fehlerliste zu „steht“ oder „Störung“?",
    "Welche Not-Halt-Kette hat diese Maschine?",
    "Welche SPS-Eingänge gehören zu den Sensoren am Einlauf?",
  ];

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex items-center gap-2 border-b border-border bg-card px-3 py-1.5 text-xs">
        <label className="flex min-w-0 items-center gap-2">
          <span className="shrink-0 text-muted-foreground">Verlauf</span>
          <select
            value={conversationId ?? ""}
            onChange={(e) => setConversationId(e.target.value || null)}
            aria-label="Chatverlauf wählen"
            className="h-7 min-w-0 max-w-[16rem] rounded-md border border-border bg-background px-1.5"
          >
            <option value="">Neuer Chat</option>
            {conversations.map((c) => (
              <option key={c.id} value={c.id}>
                {c.title}
              </option>
            ))}
          </select>
        </label>
        <button type="button" onClick={() => setConversationId(null)} className="rounded-md border border-border p-1 hover:border-primary" aria-label="Neuer Chat" title="Neuer Chat">
          <Plus className="size-3.5" />
        </button>
        {conversationId && (
          <button type="button" onClick={remove} className="text-muted-foreground hover:text-danger">
            Löschen
          </button>
        )}
        <span className="ml-auto hidden truncate text-muted-foreground sm:inline">Antworten nur aus {machine.source_name ?? "dieser Wissensquelle"}</span>
      </div>
      <ChatPanel
        scope={{ sourceIds: [sourceId], machineId: machine.id }}
        conversationId={conversationId}
        onConversationId={setConversationId}
        onConversationsChanged={loadConversations}
        onOpenPage={onOpenPage}
        activeReference={activeReference}
        initialInput={initialInput}
        placeholder={`Frag etwas zu ${machine.name} …`}
        onMeta={onMeta}
        onOpenPart={onOpenPart}
        onShowInModel={onShowInModel}
        emptyState={
          <>
            <h2 className="text-xl font-semibold tracking-tight">Was willst du über {machine.name} wissen?</h2>
            <p className="mt-2 text-sm text-muted-foreground">Jede Antwort zeigt die Bauteile im Modell oben und belegt sie mit Seiten aus der Doku.</p>
            <ExampleQuestions examples={examples} onPick={setInitialInput} />
          </>
        }
      />
    </div>
  );
}
