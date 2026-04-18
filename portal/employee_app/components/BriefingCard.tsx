"use client";

import { ChevronDown } from "lucide-react";
import { useState } from "react";

import type { Briefing } from "./types";

export function BriefingCard({ briefing }: { briefing: Briefing }) {
  const [showEvidence, setShowEvidence] = useState(false);

  return (
    <article className="rounded-[28px] border border-ink/10 bg-white/90 p-4 shadow-card">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="text-xs font-semibold uppercase tracking-[0.22em] text-ink/45">Briefing</div>
          <h3 className="mt-1 font-display text-2xl text-ink">{briefing.title}</h3>
        </div>
        <div className="text-xs text-ink/55">{new Date(briefing.createdAt).toLocaleString()}</div>
      </div>

      <Section title="What Happened" tone="bg-paper/70">
        {briefing.whatHappened}
      </Section>
      <Section title="Why It Matters" tone="bg-moss/10">
        {briefing.whyItMatters}
      </Section>
      <Section title="Recommended Action" tone="bg-accent/10">
        {briefing.recommendedAction}
      </Section>

      <div className="mt-4 rounded-2xl border border-ink/10 bg-white/80 p-3">
        <button
          className="flex w-full items-center justify-between text-left text-xs font-semibold uppercase tracking-[0.2em] text-ink/55"
          onClick={() => setShowEvidence((current) => !current)}
          type="button"
        >
          Evidence
          <ChevronDown className={`h-4 w-4 transition ${showEvidence ? "rotate-180" : ""}`} />
        </button>
        {showEvidence ? (
          <ul className="mt-3 space-y-2 text-sm text-ink/75">
            {briefing.evidence.length ? briefing.evidence.map((item) => <li key={item}>• {item}</li>) : <li>No supporting evidence provided.</li>}
          </ul>
        ) : null}
      </div>
    </article>
  );
}

function Section({
  title,
  tone,
  children,
}: {
  title: string;
  tone: string;
  children: React.ReactNode;
}) {
  return (
    <section className={`mt-4 rounded-2xl p-4 ${tone}`}>
      <div className="text-xs font-semibold uppercase tracking-[0.2em] text-ink/45">{title}</div>
      <p className="mt-2 text-sm leading-6 text-ink/80">{children}</p>
    </section>
  );
}
