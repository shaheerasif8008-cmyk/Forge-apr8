"use client";

import { useState, useTransition } from "react";

import { ArrowRight, Check, CircleAlert, Pencil, X } from "lucide-react";

import type { Approval } from "./types";

type Props = {
  approval: Approval;
  onResolve: (decision: "approve" | "decline" | "modify") => Promise<void>;
  onOpenDetails: () => void;
};

export function ApprovalCard({ approval, onResolve, onOpenDetails }: Props) {
  const [isPending, startTransition] = useTransition();
  const [isResolved, setIsResolved] = useState(false);

  const brief = approval.metadata?.brief ?? {};
  const urgency = String(
    approval.metadata?.urgency
      ?? brief.client_info?.urgency
      ?? (brief.flags?.includes("guidance required") ? "high" : "normal"),
  );
  const requester = approval.metadata?.requester ?? brief.client_info?.client_name ?? "Employee runtime";
  const title = brief.title ?? brief.brief_id ?? "Approval requested";
  const summary = brief.executive_summary ?? approval.content;

  function handleDecision(decision: "approve" | "decline" | "modify") {
    startTransition(async () => {
      await onResolve(decision);
      if (decision !== "modify") {
        setIsResolved(true);
      }
    });
  }

  return (
    <article
      className={`rounded-[28px] border border-ink/10 bg-white/90 p-4 shadow-card transition-all duration-300 ${
        isResolved ? "pointer-events-none scale-[0.98] opacity-0" : "opacity-100"
      }`}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-2">
          <div className="flex items-center gap-3">
            <div className="grid h-10 w-10 place-items-center rounded-full bg-accent/15 text-sm font-semibold text-accent">
              {requester.slice(0, 2).toUpperCase()}
            </div>
            <div>
              <div className="text-sm font-semibold text-ink">{title}</div>
              <div className="text-xs text-ink/55">Requested by {requester}</div>
            </div>
          </div>
          <p className="text-sm leading-6 text-ink/75">{summary}</p>
        </div>
        <UrgencyChip urgency={urgency} />
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <ActionButton
          icon={<Check className="h-4 w-4" />}
          label="Approve"
          tone="approve"
          disabled={isPending}
          onClick={() => handleDecision("approve")}
        />
        <ActionButton
          icon={<X className="h-4 w-4" />}
          label="Decline"
          tone="decline"
          disabled={isPending}
          onClick={() => handleDecision("decline")}
        />
        <ActionButton
          icon={<Pencil className="h-4 w-4" />}
          label="Modify"
          tone="neutral"
          disabled={isPending}
          onClick={() => handleDecision("modify")}
        />
        <button
          className="inline-flex items-center gap-2 rounded-full px-3 py-2 text-sm font-semibold text-ink/75 transition hover:bg-paper"
          onClick={onOpenDetails}
          type="button"
        >
          <ArrowRight className="h-4 w-4" />
          See Details
        </button>
      </div>
    </article>
  );
}

function ActionButton({
  icon,
  label,
  tone,
  disabled,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  tone: "approve" | "decline" | "neutral";
  disabled: boolean;
  onClick: () => void;
}) {
  const tones = {
    approve: "bg-moss text-white hover:bg-moss/90",
    decline: "bg-terracotta text-white hover:bg-terracotta/90",
    neutral: "border border-ink/15 bg-white text-ink hover:bg-paper",
  } as const;
  return (
    <button
      className={`inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-semibold transition ${tones[tone]} disabled:cursor-not-allowed disabled:opacity-60`}
      disabled={disabled}
      onClick={onClick}
      type="button"
    >
      {icon}
      {label}
    </button>
  );
}

function UrgencyChip({ urgency }: { urgency: string }) {
  const normalized = urgency.toLowerCase();
  const palette =
    normalized === "urgent"
      ? "bg-terracotta/15 text-terracotta"
      : normalized === "high"
        ? "bg-gold/20 text-ink"
        : "bg-moss/15 text-moss";
  return (
    <div className={`inline-flex items-center gap-2 rounded-full px-3 py-2 text-xs font-semibold uppercase tracking-[0.18em] ${palette}`}>
      <CircleAlert className="h-3.5 w-3.5" />
      {urgency || "normal"}
    </div>
  );
}
