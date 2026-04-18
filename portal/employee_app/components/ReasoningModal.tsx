"use client";

import { useEffect, useState } from "react";

import type { ReasoningRecord } from "./types";

type Props = {
  apiBase: string;
  recordId: string;
  onClose: () => void;
};

export function ReasoningModal({ apiBase, recordId, onClose }: Props) {
  const [record, setRecord] = useState<ReasoningRecord | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    const load = async () => {
      const response = await fetch(`${apiBase}/api/v1/reasoning/record/${recordId}`, { signal: controller.signal });
      if (!response.ok) {
        return;
      }
      setRecord(await response.json());
    };
    void load();
    return () => controller.abort();
  }, [apiBase, recordId]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/45 px-4" onClick={onClose}>
      <div className="max-h-[85vh] w-full max-w-3xl overflow-y-auto rounded-[32px] bg-white p-6 shadow-card" onClick={(event) => event.stopPropagation()}>
        <div className="flex items-start justify-between gap-4 border-b border-ink/10 pb-4">
          <div>
            <div className="text-xs font-semibold uppercase tracking-[0.24em] text-ink/45">Reasoning Record</div>
            <h2 className="font-display text-3xl">{record?.node_id ?? "Loading..."}</h2>
          </div>
          <button className="rounded-full border border-ink/15 px-3 py-1 text-sm font-semibold text-ink" onClick={onClose} type="button">
            Close
          </button>
        </div>

        {record ? (
          <div className="mt-5 space-y-4 text-sm text-ink/80">
            <section className="rounded-2xl bg-paper/60 p-4">
              <div className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Decision</div>
              <div className="mt-2 text-lg font-semibold">{record.decision}</div>
              <p className="mt-2 leading-6">{record.rationale}</p>
            </section>

            <section className="grid gap-4 md:grid-cols-3">
              <Metric label="Confidence" value={`${Math.round((record.confidence ?? 0) * 100)}%`} />
              <Metric label="Token Cost" value={String(record.token_cost ?? 0)} />
              <Metric label="Latency" value={`${record.latency_ms ?? 0} ms`} />
            </section>

            <section className="rounded-2xl border border-ink/10 p-4">
              <div className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Alternatives</div>
              <div className="mt-3 space-y-3">
                {record.alternatives.length ? record.alternatives.map((alternative) => (
                  <div key={alternative.option} className="rounded-2xl bg-paper/60 p-3">
                    <div className="font-semibold">{alternative.option}</div>
                    <div className="text-xs text-ink/55">Score {alternative.score}</div>
                    <p className="mt-1 text-sm">{alternative.why_not_chosen || "Chosen path."}</p>
                  </div>
                )) : <div className="text-ink/55">No alternatives recorded.</div>}
              </div>
            </section>

            <section className="rounded-2xl border border-ink/10 p-4">
              <div className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Evidence</div>
              <div className="mt-3 space-y-3">
                {record.evidence.length ? record.evidence.map((source, index) => (
                  <div key={`${source.reference}-${index}`} className="rounded-2xl bg-paper/60 p-3">
                    <div className="font-semibold">{source.source_type}</div>
                    <div className="text-xs text-ink/55">{source.reference}</div>
                    <p className="mt-1 text-sm leading-6">{source.content_snippet}</p>
                  </div>
                )) : <div className="text-ink/55">No evidence recorded.</div>}
              </div>
            </section>

            <section className="rounded-2xl border border-ink/10 p-4">
              <div className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Modules Invoked</div>
              <div className="mt-3 flex flex-wrap gap-2">
                {record.modules_invoked.length ? record.modules_invoked.map((moduleId) => (
                  <span key={moduleId} className="rounded-full bg-accent px-3 py-1 text-xs font-semibold text-white">
                    {moduleId}
                  </span>
                )) : <span className="text-ink/55">No module metadata.</span>}
              </div>
            </section>
          </div>
        ) : (
          <div className="mt-5 text-sm text-ink/60">Loading reasoning record…</div>
        )}
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-ink/10 bg-white/85 p-4">
      <div className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">{label}</div>
      <div className="mt-2 text-xl font-semibold text-ink">{value}</div>
    </div>
  );
}
