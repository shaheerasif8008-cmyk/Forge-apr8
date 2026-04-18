"use client";

import { useEffect, useMemo, useState } from "react";

import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  MessageSquareText,
  Scale,
} from "lucide-react";

import { fetchActivity } from "@/lib/api";

import { ReasoningModal } from "./ReasoningModal";
import type { ActivityItem } from "./types";

type Props = {
  apiBase: string;
};

type FilterId = "all" | "decision" | "communication" | "error";

export function ActivityPanel({ apiBase }: Props) {
  const [activity, setActivity] = useState<ActivityItem[]>([]);
  const [filter, setFilter] = useState<FilterId>("all");
  const [selectedReasoningId, setSelectedReasoningId] = useState("");

  useEffect(() => {
    void fetchActivity(apiBase, 50).then(setActivity);
  }, [apiBase]);

  const filtered = useMemo(
    () => (filter === "all" ? activity : activity.filter((item) => item.category === filter)),
    [activity, filter],
  );

  const grouped = useMemo(() => groupByTimeBucket(filtered), [filtered]);

  return (
    <>
      <div className="rounded-[28px] border border-ink/10 bg-white/80 p-4 shadow-card">
        <div className="text-xs font-semibold uppercase tracking-[0.24em] text-ink/45">Activity</div>
        <div className="mt-3 flex flex-wrap gap-2">
          {(["all", "decision", "communication", "error"] as FilterId[]).map((chip) => (
            <button
              key={chip}
              className={`rounded-full px-3 py-2 text-sm font-semibold transition ${
                filter === chip ? "bg-accent text-white" : "bg-paper text-ink/65"
              }`}
              onClick={() => setFilter(chip)}
              type="button"
            >
              {chip === "all" ? "All" : chip === "decision" ? "Decisions" : chip === "communication" ? "Communications" : "Errors"}
            </button>
          ))}
        </div>

        <div className="mt-4 space-y-5">
          {Object.entries(grouped).map(([bucket, items]) => (
            <section key={bucket}>
              <div className="mb-2 text-xs font-semibold uppercase tracking-[0.2em] text-ink/45">{bucket}</div>
              <div className="space-y-3">
                {items.map((item) => {
                  const Icon = iconForActivity(item);
                  return (
                    <button
                      key={item.id}
                      className="flex w-full items-start gap-3 rounded-[22px] bg-paper/55 p-3 text-left transition hover:bg-paper/80"
                      disabled={!item.record_id}
                      onClick={() => item.record_id && setSelectedReasoningId(item.record_id)}
                      type="button"
                    >
                      <div className="grid h-10 w-10 place-items-center rounded-full bg-white text-accent shadow-sm">
                        <Icon className="h-4 w-4" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="font-semibold text-ink">{item.event_type.replaceAll("_", " ")}</div>
                        <div className="mt-1 text-sm leading-6 text-ink/70">{item.description}</div>
                      </div>
                      <div className="text-xs text-ink/45">{relativeTime(item.occurred_at)}</div>
                    </button>
                  );
                })}
              </div>
            </section>
          ))}
          {!Object.keys(grouped).length ? <div className="rounded-[22px] bg-paper/45 p-4 text-sm text-ink/60">No activity yet. Completed tasks and decision records will appear here.</div> : null}
        </div>
      </div>
      {selectedReasoningId ? (
        <ReasoningModal apiBase={apiBase} recordId={selectedReasoningId} onClose={() => setSelectedReasoningId("")} />
      ) : null}
    </>
  );
}

function iconForActivity(item: ActivityItem) {
  if (item.category === "decision") {
    return Scale;
  }
  if (item.category === "communication") {
    return MessageSquareText;
  }
  if (item.category === "error") {
    return AlertTriangle;
  }
  if (item.event_type.includes("completed")) {
    return CheckCircle2;
  }
  return Bot;
}

function groupByTimeBucket(items: ActivityItem[]) {
  const now = new Date();
  const grouped: Record<string, ActivityItem[]> = {};
  for (const item of items) {
    const date = new Date(item.occurred_at);
    const diffDays = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24));
    const bucket = diffDays <= 0 ? "Today" : diffDays === 1 ? "Yesterday" : diffDays < 7 ? "This Week" : "Earlier";
    grouped[bucket] ??= [];
    grouped[bucket].push(item);
  }
  return grouped;
}

function relativeTime(value: string) {
  const date = new Date(value);
  const diff = Math.max(0, Date.now() - date.getTime());
  const minutes = Math.floor(diff / (1000 * 60));
  if (minutes < 1) {
    return "just now";
  }
  if (minutes < 60) {
    return `${minutes}m`;
  }
  const hours = Math.floor(minutes / 60);
  if (hours < 24) {
    return `${hours}h`;
  }
  return `${Math.floor(hours / 24)}d`;
}
