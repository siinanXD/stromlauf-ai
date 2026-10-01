"use client";

import { useCallback, useMemo } from "react";

import type { AnswerBlocksContext } from "@/components/chat/AnswerView";
import { ChatPanel, type ChatScope } from "@/components/chat/ChatPanel";
import { IncidentHeader } from "@/components/incident/IncidentHeader";
import type { Incident } from "@/components/incident/incidents";
import type { PageTarget } from "@/components/PageViewer";
import type { AnswerMeta, MachineDetail } from "@/lib/api";
import type { DetailRef } from "@/lib/detail";

/**
 * Chat eines Stoerfalls (frueher Tab „Chat“ der Maschine): Scope ist fest die Wissensquelle der Maschine (Backend
 * erzwingt das ueber machine_id), Antworten erscheinen als Bloecke. Ein neuer Stoerfall schickt seine Meldung
 * sofort ab (autoSend); die vom Server vergebene ID meldet onConversationId.
 */
export function MachineChatTab({
  machine,
  incident,
  conversationId,
  autoSend,
  activeReference,
  activePart = null,
  onConversationId,
  onSendStart,
  onSendSettled,
  onConversationsChanged,
  onOpenDetail,
  onOpenIncident,
  onShowInModel,
  onMeta,
  onBack,
  onResolve,
  onReopen,
  onDelete,
}: {
  machine: MachineDetail;
  incident: Incident;
  /** Echte Konversations-ID; null, solange der Server sie noch nicht vergeben hat. */
  conversationId: string | null;
  autoSend?: { key: string; text: string };
  activeReference: string | null;
  /** Bauteil, das gerade im Detail offen ist. */
  activePart?: string | null;
  onConversationId: (id: string, title: string) => void;
  onSendStart?: () => void;
  /** conversationId null: der Server hat keinen Chat angelegt, der neue Stoerfall gilt als "nicht angelegt". */
  onSendSettled?: (result: { conversationId: string | null; failed: boolean }) => void;
  onConversationsChanged: () => void;
  onOpenDetail: (detail: DetailRef) => void;
  onOpenIncident: (conversationId: string) => void;
  onShowInModel: (tags: string[]) => void;
  onMeta?: (meta: AnswerMeta) => void;
  onBack: () => void;
  onResolve: (finding: string) => Promise<boolean>;
  onReopen: () => Promise<boolean>;
  onDelete: () => Promise<boolean>;
}) {
  const sourceId = machine.source_id;
  const machineId = machine.id;
  const scope = useMemo<ChatScope>(() => ({ sourceIds: sourceId ? [sourceId] : [], machineId }), [sourceId, machineId]);
  const blocks = useMemo<AnswerBlocksContext>(
    () => ({ machineId, sourceId, onOpenDetail, onOpenIncident, activePart }),
    [machineId, sourceId, onOpenDetail, onOpenIncident, activePart],
  );
  const openPage = useCallback((target: PageTarget) => onOpenDetail({ kind: "plan", target }), [onOpenDetail]);

  return (
    <div className="flex h-full min-h-0 flex-col" data-testid="incident-chat">
      <IncidentHeader incident={incident} onBack={onBack} onResolve={onResolve} onReopen={onReopen} onDelete={onDelete} />
      <ChatPanel
        scope={scope}
        conversationId={conversationId}
        onConversationId={onConversationId}
        onSendStart={onSendStart}
        onSendSettled={onSendSettled}
        onConversationsChanged={onConversationsChanged}
        onOpenPage={openPage}
        activeReference={activeReference}
        placeholder="Nachfrage zu diesem Störfall …"
        onMeta={onMeta}
        onShowInModel={onShowInModel}
        blocks={blocks}
        autoSend={autoSend}
        emptyState={
          <p className="text-center text-subhead text-muted-foreground">
            {incident.pending
              ? "Die Meldung wird gesendet …"
              : incident.failed
                ? "Die Meldung wurde nicht angelegt. In der Liste lässt sie sich erneut senden."
                : "In diesem Störfall steht noch nichts. Stell unten eine Frage zur Meldung."}
          </p>
        }
      />
    </div>
  );
}
