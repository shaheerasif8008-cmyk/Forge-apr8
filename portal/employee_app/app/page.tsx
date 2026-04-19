"use client";

import { useEffect, useState } from "react";

import { employeeAppConfig, resolveApiBaseUrl, resolveWsBaseUrl } from "@/app/config";
import { ChatInput } from "@/components/ChatInput";
import { MessageBubble } from "@/components/MessageBubble";
import { SidebarPanels } from "@/components/SidebarPanels";
import { StreamingIndicator } from "@/components/StreamingIndicator";
import type { Approval } from "@/components/types";
import type { ChatMessage, EmployeeMeta } from "@/components/types";

export default function HomePage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [meta, setMeta] = useState<EmployeeMeta | null>(null);
  const [dropActive, setDropActive] = useState(false);

  const conversationId = "default";
  const apiBase = resolveApiBaseUrl();
  const wsBase = resolveWsBaseUrl();

  useEffect(() => {
    const load = async () => {
      const [response, metaResponse] = await Promise.all([
        fetch(`${apiBase}/api/v1/chat/history?conversation_id=${conversationId}`),
        fetch(`${apiBase}/api/v1/meta`),
      ]);
      const data = await response.json();
      setMessages(data.messages);
      if (metaResponse.ok) {
        setMeta(await metaResponse.json());
      }
    };
    void load();
  }, [apiBase]);

  useEffect(() => {
    const removeDropHandler = window.forge?.onFileDropped?.((path) => {
      void uploadDroppedDocument(path);
    });

    let dragDepth = 0;
    const handleDragEnter = (event: DragEvent) => {
      event.preventDefault();
      dragDepth += 1;
      setDropActive(true);
    };
    const handleDragOver = (event: DragEvent) => {
      event.preventDefault();
    };
    const handleDragLeave = (event: DragEvent) => {
      event.preventDefault();
      dragDepth = Math.max(0, dragDepth - 1);
      if (dragDepth === 0) {
        setDropActive(false);
      }
    };
    const handleDrop = (event: DragEvent) => {
      event.preventDefault();
      dragDepth = 0;
      setDropActive(false);
      const file = event.dataTransfer?.files?.[0];
      if (file) {
        void uploadDroppedDocument(file);
      }
    };

    window.addEventListener("dragenter", handleDragEnter);
    window.addEventListener("dragover", handleDragOver);
    window.addEventListener("dragleave", handleDragLeave);
    window.addEventListener("drop", handleDrop);

    return () => {
      if (typeof removeDropHandler === "function") {
        removeDropHandler();
      }
      window.removeEventListener("dragenter", handleDragEnter);
      window.removeEventListener("dragover", handleDragOver);
      window.removeEventListener("dragleave", handleDragLeave);
      window.removeEventListener("drop", handleDrop);
    };
  }, [apiBase]);

  async function sendMessage(content: string) {
    setStreaming(true);
    setMessages((current) => [
      ...current,
      { id: `local-${Date.now()}`, role: "user", content, message_type: "text" },
    ]);

    const socket = new WebSocket(`${wsBase}/api/v1/ws`);
    let streamedText = "";
    socket.onopen = () => {
      socket.send(JSON.stringify({ type: "chat_message", content, conversation_id: conversationId }));
    };
    socket.onmessage = (event) => {
      const payload = JSON.parse(event.data) as Record<string, unknown>;
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
      }
    };
    socket.onerror = () => setStreaming(false);
    socket.onclose = () => setStreaming(false);
  }

  async function uploadDroppedDocument(file: File | string) {
    const form = new FormData();
    if (typeof file === "string") {
      form.append("file_path", file);
      form.append("metadata", JSON.stringify({ source: "electron-drop" }));
    } else {
      form.append("file", file);
      form.append("metadata", JSON.stringify({ source: "browser-drop" }));
    }
    await fetch(`${apiBase}/api/v1/documents/upload`, {
      method: "POST",
      body: form,
    });
    void window.forge?.notify?.("Document uploaded", "The document is available in Memory.", "/memory");
  }

  function handleApprovalsCountChange(count: number) {
    void window.forge?.setBadgeCount?.(count);
  }

  function handleUrgentApproval(approval: Approval) {
    const summary = approval.metadata?.brief?.executive_summary ?? approval.content;
    void window.forge?.notify?.("Urgent approval pending", summary.slice(0, 140), "/");
  }

  return (
    <main className="min-h-screen px-4 py-6 md:px-8">
      {dropActive ? (
        <div className="pointer-events-none fixed inset-0 z-50 grid place-items-center bg-ink/15 backdrop-blur-sm">
          <div className="rounded-[32px] border border-white/50 bg-white/90 px-8 py-10 text-center shadow-card">
            <div className="text-xs font-semibold uppercase tracking-[0.26em] text-ink/45">Document Upload</div>
            <div className="mt-3 font-display text-3xl text-ink">Drop files anywhere to add them to memory.</div>
          </div>
        </div>
      ) : null}
      <div className="mx-auto grid max-w-7xl gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        <section className="rounded-[34px] border border-ink/10 bg-white/55 p-5 shadow-card backdrop-blur">
          <div className="mb-5 flex items-center justify-between gap-4 border-b border-ink/10 pb-4">
            <div>
              <div className="text-xs font-semibold uppercase tracking-[0.28em] text-ink/45">
                {meta?.employee_name ?? employeeAppConfig.employeeName}
              </div>
              <h1 className="font-display text-4xl">{meta?.role_title ?? employeeAppConfig.employeeRole}</h1>
            </div>
            <div className="rounded-full bg-gold/20 px-4 py-2 text-sm font-semibold text-ink">
              {meta?.badge ?? employeeAppConfig.deploymentFormat}
            </div>
          </div>

          <div className="flex min-h-[60vh] flex-col gap-4 overflow-y-auto pb-4">
            {messages.map((message) => (
              <MessageBubble key={message.id} message={message} onDecision={async () => undefined} />
            ))}
            {streaming ? <StreamingIndicator /> : null}
          </div>

          <ChatInput
            onSend={sendMessage}
            placeholder={
              meta?.workflow === "legal_intake"
                ? "Paste an intake email or ask your employee to process a matter..."
                : "Ask your employee to triage, schedule, draft, or coordinate work..."
            }
            footerLabel={meta?.deployment_format ?? employeeAppConfig.deploymentFormat}
          />
        </section>

        <aside className="min-h-[70vh]">
          <SidebarPanels
            apiBase={apiBase}
            onApprovalsCountChange={handleApprovalsCountChange}
            onUrgentApproval={handleUrgentApproval}
          />
        </aside>
      </div>
    </main>
  );
}
