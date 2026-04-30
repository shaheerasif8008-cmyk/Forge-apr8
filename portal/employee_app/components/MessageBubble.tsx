"use client";

import { BriefCard } from "./BriefCard";
import type { Approval, ChatMessage } from "./types";

type Props = {
  message: ChatMessage;
  onDecision: (messageId: string, decision: "approve" | "decline" | "modify") => void;
};

export function MessageBubble({ message, onDecision }: Props) {
  if (message.message_type === "approval_request") {
    const approval = message as Approval;
    const isPending = approval.metadata?.status === "pending";
    return (
      <div className="w-full">
        <BriefCard
          brief={approval.metadata?.brief ?? {}}
          onDecision={isPending ? (decision) => onDecision(message.id, decision) : undefined}
        />
      </div>
    );
  }

  const align = message.role === "user" ? "ml-auto bg-ink text-white" : "mr-auto bg-white/85 text-ink";
  return (
    <div className={`max-w-3xl rounded-[26px] px-5 py-4 shadow-card ${align}`}>
      <div className="text-sm leading-6 whitespace-pre-wrap">{message.content}</div>
    </div>
  );
}
