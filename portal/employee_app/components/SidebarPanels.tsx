"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Settings2 } from "lucide-react";

import { fetchMemory, fetchMetrics, fetchUpdates } from "@/lib/api";

import { ActivityPanel } from "./ActivityPanel";
import { InboxPanel } from "./InboxPanel";
import type { MemorySnapshot, UpdateStatus } from "./types";

type Props = {
  apiBase: string;
  onApprovalsCountChange?: (count: number) => void;
  onUrgentApproval?: (approval: import("./types").Approval) => void;
};

export function SidebarPanels({ apiBase, onApprovalsCountChange, onUrgentApproval }: Props) {
  const [metrics, setMetrics] = useState<Record<string, unknown>>({});
  const [memory, setMemory] = useState<MemorySnapshot>({});
  const [updates, setUpdates] = useState<UpdateStatus>({});

  useEffect(() => {
    const load = async () => {
      const [nextMetrics, nextMemory, nextUpdates] = await Promise.all([
        fetchMetrics(apiBase),
        fetchMemory(apiBase),
        fetchUpdates(apiBase),
      ]);
      setMetrics(nextMetrics);
      setMemory(nextMemory);
      setUpdates(nextUpdates);
    };
    void load();
  }, [apiBase]);

  return (
    <div className="flex h-full flex-col gap-4">
      <InboxPanel
        apiBase={apiBase}
        onApprovalsCountChange={onApprovalsCountChange}
        onUrgentApproval={onUrgentApproval}
      />
      <ActivityPanel apiBase={apiBase} />

      <Panel title="Settings">
        <div className="rounded-[22px] bg-paper/55 p-4">
          <div className="text-sm leading-6 text-ink/70">
            Communication, approval limits, integrations, and org map now live on a dedicated settings route.
          </div>
          <Link
            className="mt-4 inline-flex items-center gap-2 rounded-full bg-accent px-4 py-2 text-sm font-semibold text-white transition hover:bg-accent/90"
            href="/settings"
          >
            <Settings2 className="h-4 w-4" />
            Open Settings
          </Link>
        </div>
      </Panel>

      <Panel title="Memory">
        <div className="space-y-3 text-sm text-ink/75">
          {Object.entries(memory).filter(([, items]) => items.length > 0).slice(0, 3).map(([category, items]) => (
            <div key={category} className="rounded-2xl bg-paper/60 p-3">
              <div className="text-[10px] uppercase tracking-[0.18em] text-ink/45">{category}</div>
              <div className="mt-2 space-y-2">
                {items.slice(0, 2).map((item) => (
                  <div key={item.key}>
                    <div className="font-medium">{item.key}</div>
                    <div className="text-xs text-ink/55">{JSON.stringify(item.value)}</div>
                  </div>
                ))}
              </div>
            </div>
          ))}
          <Link
            className="inline-flex items-center rounded-full bg-accent px-4 py-2 text-sm font-semibold text-white transition hover:bg-accent/90"
            href="/memory"
          >
            Open Memory Browser
          </Link>
        </div>
      </Panel>

      <Panel title="Updates">
        <div className="space-y-3 text-sm text-ink/75">
          {Object.entries(updates).map(([key, value]) => (
            <div key={key} className="rounded-2xl bg-paper/60 p-3">
              <div className="text-[10px] uppercase tracking-[0.18em] text-ink/45">{key}</div>
              <div className="mt-1 text-xs text-ink/60">{JSON.stringify(value)}</div>
            </div>
          ))}
        </div>
      </Panel>

      <Panel title="Metrics">
        <div className="grid grid-cols-2 gap-3 text-sm">
          {Object.entries(metrics).map(([key, value]) => (
            <div key={key} className="rounded-2xl bg-paper/60 p-3">
              <div className="text-[10px] uppercase tracking-[0.18em] text-ink/45">{key}</div>
              <div className="mt-1 text-base font-semibold">{typeof value === "object" ? JSON.stringify(value) : String(value)}</div>
            </div>
          ))}
        </div>
        <Link
          className="mt-3 inline-flex items-center rounded-full bg-ink px-4 py-2 text-sm font-semibold text-white transition hover:bg-ink/90"
          href="/metrics"
        >
          Open Metrics Dashboard
        </Link>
      </Panel>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-[28px] border border-ink/10 bg-white/80 p-4 shadow-card">
      <div className="text-xs font-semibold uppercase tracking-[0.24em] text-ink/45">{title}</div>
      <div className="mt-3">{children}</div>
    </section>
  );
}
