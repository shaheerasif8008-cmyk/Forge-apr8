"use client";

import type { Approval, MemorySnapshot, UpdateStatus } from "./types";

type Props = {
  approvals: Approval[];
  activity: Record<string, unknown>[];
  settings: Record<string, unknown>;
  metrics: Record<string, unknown>;
  memory: MemorySnapshot;
  updates: UpdateStatus;
};

export function SidebarPanels({ approvals, activity, settings, metrics, memory, updates }: Props) {
  return (
    <div className="flex h-full flex-col gap-4">
      <Panel title={`Inbox (${approvals.length})`}>
        {approvals.length ? approvals.map((approval) => (
          <div key={approval.id} className="rounded-2xl bg-paper/70 p-3 text-sm">
            {(approval.metadata?.brief as { executive_summary?: string } | undefined)?.executive_summary ?? approval.content}
          </div>
        )) : <p className="text-sm text-ink/65">No pending approvals.</p>}
      </Panel>

      <Panel title="Activity">
        <div className="space-y-3 text-sm text-ink/75">
          {activity.slice(-6).map((item, index) => (
            <div key={index} className="rounded-2xl bg-paper/60 p-3">
              {String(item["event_type"] ?? item["node"] ?? "event")}
            </div>
          ))}
        </div>
      </Panel>

      <Panel title="Settings">
        <div className="space-y-2 text-sm text-ink/75">
          {Object.entries(settings).map(([key, value]) => (
            <div key={key} className="flex items-center justify-between gap-3 rounded-2xl bg-paper/60 px-3 py-2">
              <span>{key}</span>
              <span className="text-right">{String(value)}</span>
            </div>
          ))}
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
