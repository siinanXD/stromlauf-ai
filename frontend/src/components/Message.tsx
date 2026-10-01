"use client";

import { memo } from "react";

import { AnswerView, type AnswerBlocksContext } from "@/components/chat/AnswerView";
import type { PageTarget } from "@/components/PageViewer";
import type { ChatMessage } from "@/lib/api";

/**
 * Eine Nachricht im Verlauf. memo: beim Streamen aendert sich nur die letzte Antwort; die anderen behalten ihr
 * Nachrichtenobjekt und werden nicht neu gerendert, solange der Aufrufer stabile Callbacks uebergibt.
 */
export const Message = memo(function Message({
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
  /** Nutzerfrage zu dieser Antwort (Befundkarte, Fehlerliste). */
  question: string;
  streaming: boolean;
  sourceIds: string[];
  activeReference: string | null;
  onOpen: (target: PageTarget) => void;
  onOpenPart?: (tag: string) => void;
  onShowInModel?: (tags: string[]) => void;
  blocks?: AnswerBlocksContext;
}) {
  if (message.role === "user") {
    return (
      // Frage-Blase (Figma): blau, rechtsbuendig, hoechstens 280 px breit; ab der zweiten Frage mit Abstand zur Antwort davor
      <div className="flex justify-end [&:not(:first-child)]:pt-5">
        <div className="max-w-[min(280px,85%)] rounded-xl bg-primary px-4 py-3 text-body break-words whitespace-pre-wrap text-primary-foreground">{message.content}</div>
      </div>
    );
  }
  return (
    <AnswerView
      message={message}
      question={question}
      streaming={streaming}
      sourceIds={sourceIds}
      activeReference={activeReference}
      onOpen={onOpen}
      onOpenPart={onOpenPart}
      onShowInModel={onShowInModel}
      blocks={blocks}
    />
  );
});
