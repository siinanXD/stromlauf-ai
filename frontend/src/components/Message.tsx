"use client";

import { AnswerView } from "@/components/chat/AnswerView";
import type { PageTarget } from "@/components/PageViewer";
import type { ChatMessage } from "@/lib/api";

export function Message({
  message,
  question,
  streaming,
  sourceIds,
  activeReference,
  onOpen,
}: {
  message: ChatMessage;
  /** Nutzerfrage zu dieser Antwort (fuer die Befundkarte). */
  question: string;
  streaming: boolean;
  sourceIds: string[];
  activeReference: string | null;
  onOpen: (target: PageTarget) => void;
}) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] whitespace-pre-wrap bg-primary/10 px-4 py-2.5 text-[14px]">{message.content}</div>
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
    />
  );
}
