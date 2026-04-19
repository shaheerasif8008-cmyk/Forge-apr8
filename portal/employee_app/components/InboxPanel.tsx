"use client";

import { useEffect, useRef, useState } from "react";

import { fetchAlerts, fetchApprovals, fetchBriefings, fetchReasoningRecords, resolveApproval } from "@/lib/api";

import { ApprovalCard } from "./ApprovalCard";
import { BriefingCard } from "./BriefingCard";
import { ReasoningModal } from "./ReasoningModal";
import type { AlertItem, Approval, Briefing } from "./types";

type Props = {
  apiBase: string;
  onApprovalsCountChange?: (count: number) => void;
  onUrgentApproval?: (approval: Approval) => void;
};

type TabId = "approvals" | "briefings" | "alerts";

export function InboxPanel({ apiBase, onApprovalsCountChange, onUrgentApproval }: Props) {
  const [activeTab, setActiveTab] = useState<TabId>("approvals");
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [briefings, setBriefings] = useState<Briefing[]>([]);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [selectedReasoningId, setSelectedReasoningId] = useState("");
  const notifiedUrgentIds = useRef<Set<string>>(new Set());

  async function loadInbox() {
    const [nextApprovals, nextBriefings, nextAlerts] = await Promise.all([
      fetchApprovals(apiBase),
      fetchBriefings(apiBase),
      fetchAlerts(apiBase),
    ]);
    const pendingApprovals = nextApprovals.filter((approval) => approval.metadata?.status === "pending");
    setApprovals(pendingApprovals);
    setBriefings(nextBriefings);
    setAlerts(nextAlerts);
    onApprovalsCountChange?.(pendingApprovals.length);
    for (const approval of pendingApprovals) {
      const urgency = String(approval.metadata?.urgency ?? "").toLowerCase();
      if (!["urgent", "high", "critical"].includes(urgency) || notifiedUrgentIds.current.has(approval.id)) {
        continue;
      }
      notifiedUrgentIds.current.add(approval.id);
      onUrgentApproval?.(approval);
    }
  }

  useEffect(() => {
    void loadInbox();
  }, [apiBase]);

  async function handleResolve(id: string, decision: "approve" | "decline" | "modify") {
    await resolveApproval(apiBase, id, decision);
    await loadInbox();
  }

  async function openReasoningForApproval(approval: Approval) {
    if (!approval.metadata?.task_id) {
      return;
    }
    const records = await fetchReasoningRecords(apiBase, approval.metadata.task_id);
    if (records.length) {
      setSelectedReasoningId(records[0].record_id);
    }
  }

  const tabs: Array<{ id: TabId; label: string; count: number }> = [
    { id: "approvals", label: "Approvals", count: approvals.length },
    { id: "briefings", label: "Briefings", count: briefings.length },
    { id: "alerts", label: "Alerts", count: alerts.length },
  ];

  return (
    <>
      <div className="rounded-[28px] border border-ink/10 bg-white/80 p-4 shadow-card">
        <div className="text-xs font-semibold uppercase tracking-[0.24em] text-ink/45">Inbox</div>

        <div className="mt-3 inline-flex rounded-full bg-paper p-1">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              className={`rounded-full px-4 py-2 text-sm font-semibold transition ${
                activeTab === tab.id ? "bg-white text-ink shadow-sm" : "text-ink/60"
              }`}
              onClick={() => setActiveTab(tab.id)}
              type="button"
            >
              {tab.label} <span className="text-ink/45">{tab.count}</span>
            </button>
          ))}
        </div>

        <div className="mt-4 space-y-4">
          {activeTab === "approvals" ? (
            approvals.length ? (
              approvals.map((approval) => (
                <ApprovalCard
                  key={approval.id}
                  approval={approval}
                  onOpenDetails={() => void openReasoningForApproval(approval)}
                  onResolve={(decision) => handleResolve(approval.id, decision)}
                />
              ))
            ) : (
              <EmptyState copy="No pending approvals — you're all caught up." />
            )
          ) : null}

          {activeTab === "briefings" ? (
            briefings.length ? (
              briefings.map((briefing) => <BriefingCard key={briefing.id} briefing={briefing} />)
            ) : (
              <EmptyState copy="No briefings yet. Your employee will surface them here as work accumulates." />
            )
          ) : null}

          {activeTab === "alerts" ? (
            alerts.length ? (
              alerts.map((alert) => (
                <article key={alert.id} className="rounded-[24px] border border-ink/10 bg-white/90 p-4 shadow-card">
                  <div className="flex items-center justify-between gap-3">
                    <div className="font-semibold text-ink">{alert.title}</div>
                    <div
                      className={`rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] ${
                        alert.severity === "critical" ? "bg-terracotta/15 text-terracotta" : "bg-gold/20 text-ink"
                      }`}
                    >
                      {alert.severity}
                    </div>
                  </div>
                  <p className="mt-2 text-sm leading-6 text-ink/75">{alert.summary}</p>
                  <div className="mt-2 text-xs text-ink/45">{new Date(alert.createdAt).toLocaleString()}</div>
                </article>
              ))
            ) : (
              <EmptyState copy="No alerts right now. High-signal warnings will land here automatically." />
            )
          ) : null}
        </div>
      </div>
      {selectedReasoningId ? (
        <ReasoningModal
          apiBase={apiBase}
          recordId={selectedReasoningId}
          onClose={() => setSelectedReasoningId("")}
        />
      ) : null}
    </>
  );
}

function EmptyState({ copy }: { copy: string }) {
  return (
    <div className="rounded-[24px] border border-dashed border-ink/15 bg-paper/35 p-6 text-center">
      <svg className="mx-auto h-20 w-20 text-accent/60" viewBox="0 0 120 120" fill="none" aria-hidden="true">
        <rect x="24" y="28" width="72" height="64" rx="18" fill="currentColor" opacity="0.12" />
        <path d="M36 44h48M36 58h30M36 72h38" stroke="currentColor" strokeWidth="6" strokeLinecap="round" />
        <circle cx="88" cy="84" r="10" fill="currentColor" opacity="0.2" />
      </svg>
      <p className="mt-4 text-sm leading-6 text-ink/65">{copy}</p>
    </div>
  );
}
