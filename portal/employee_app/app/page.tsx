"use client";

import { useEffect, useMemo, useState } from "react";

import { ChatInput } from "@/components/ChatInput";
import { MessageBubble } from "@/components/MessageBubble";
import { SidebarPanels } from "@/components/SidebarPanels";
import { StreamingIndicator } from "@/components/StreamingIndicator";
import type { Approval, ChatMessage } from "@/components/types";

const API_BASE = process.env.NEXT_PUBLIC_EMPLOYEE_API_URL ?? "http://localhost:8001";
const WS_BASE = (process.env.NEXT_PUBLIC_EMPLOYEE_WS_URL ?? "ws://localhost:8001").replace(/\/$/, "");

export default function HomePage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [activity, setActivity] = useState<Record<string, unknown>[]>([]);
  const [settings, setSettings] = useState<Record<string, unknown>>({});
  const [metrics, setMetrics] = useState<Record<string, unknown>>({});
  const [streaming, setStreaming] = useState(false);

  const conversationId = "default";

  async function loadSidebar() {
    const [approvalRes, activityRes, settingsRes, metricsRes] = await Promise.all([
      fetch(`${API_BASE}/api/v1/approvals`),
      fetch(`${API_BASE}/api/v1/activity`),
      fetch(`${API_BASE}/api/v1/settings`),
      fetch(`${API_BASE}/api/v1/metrics`),
    ]);
    setApprovals(await approvalRes.json());
    setActivity(await activityRes.json());
    setSettings(await settingsRes.json());
    setMetrics(await metricsRes.json());
  }

  useEffect(() => {
    const load = async () => {
      const response = await fetch(`${API_BASE}/api/v1/chat/history?conversation_id=${conversationId}`);
      const data = await response.json();
      setMessages(data.messages);
      await loadSidebar();
    };
    void load();
  }, []);

  async function decideApproval(messageId: string, decision: "approve" | "decline" | "modify") {
    await fetch(`${API_BASE}/api/v1/approvals/${messageId}/decide`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ decision, note: "" }),
    });
    await loadSidebar();
  }

  async function sendMessage(content: string) {
    setStreaming(true);
    setMessages((current) => [
      ...current,
      { id: `local-${Date.now()}`, role: "user", content, message_type: "text" },
    ]);

    const socket = new WebSocket(`${WS_BASE}/api/v1/ws`);
    let streamedText = "";
    socket.onopen = () => {
      socket.send(JSON.stringify({ type: "chat_message", content, conversation_id: conversationId }));
    };
    socket.onmessage = (event) => {
      const payload = JSON.parse(event.data) as Record<string, unknown>;
      if (payload.type === "status") {
        setActivity((current) => [...current, payload]);
      }
      if (payload.type === "token") {
        streamedText += String(payload.content ?? "");
        setMessages((current) => {
          const withoutDraft = current.filter((message) => message.id !== "draft-stream");
          return [
            ...withoutDraft,
            {
              id: "draft-stream",
              role: "assistant",
              content: streamedText,
              message_type: "status_update",
            },
          ];
        });
      }
      if (payload.type === "complete") {
        setMessages((current) => {
          const withoutDraft = current.filter((message) => message.id !== "draft-stream");
          return [
            ...withoutDraft,
            {
              id: `approval-${Date.now()}`,
              role: "assistant",
              content: streamedText,
              message_type: "approval_request",
              metadata: { brief: payload.data },
            },
          ];
        });
        setStreaming(false);
        socket.close();
        void loadSidebar();
      }
    };
    socket.onerror = () => setStreaming(false);
    socket.onclose = () => setStreaming(false);
  }

  const pendingApprovals = useMemo(
    () => approvals.filter((approval) => approval.metadata?.status === "pending"),
    [approvals],
  );

  return (
    <main className="min-h-screen px-4 py-6 md:px-8">
      <div className="mx-auto grid max-w-7xl gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        <section className="rounded-[34px] border border-ink/10 bg-white/55 p-5 shadow-card backdrop-blur">
          <div className="mb-5 flex items-center justify-between gap-4 border-b border-ink/10 pb-4">
            <div>
              <div className="text-xs font-semibold uppercase tracking-[0.28em] text-ink/45">Arthur</div>
              <h1 className="font-display text-4xl">Legal Intake Associate</h1>
            </div>
            <div className="rounded-full bg-gold/20 px-4 py-2 text-sm font-semibold text-ink">
              Hosted web demo
            </div>
          </div>

          <div className="flex min-h-[60vh] flex-col gap-4 overflow-y-auto pb-4">
            {messages.map((message) => (
              <MessageBubble key={message.id} message={message} onDecision={decideApproval} />
            ))}
            {streaming ? <StreamingIndicator /> : null}
          </div>

          <ChatInput onSend={sendMessage} />
        </section>

        <aside className="min-h-[70vh]">
          <SidebarPanels
            approvals={pendingApprovals}
            activity={activity}
            settings={settings}
            metrics={metrics}
          />
        </aside>
      </div>
    </main>
  );
}
