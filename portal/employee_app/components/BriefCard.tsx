import type { Brief } from "./types";

type BriefCardProps = {
  brief: Brief;
  onDecision?: (decision: "approve" | "decline" | "modify") => void;
};

export function BriefCard({ brief, onDecision }: BriefCardProps) {
  const client = brief.client_info ?? {};
  const analysis = brief.analysis ?? {};
  const confidence = Math.round((brief.confidence_score ?? 0) * 100);
  const isGenericCard = !client.client_name && !client.matter_type && Boolean(brief.title || brief.action_items?.length);

  if (isGenericCard) {
    return (
      <div className="w-full rounded-[28px] border border-ink/10 bg-white/90 p-5 shadow-card">
        <div className="flex items-start justify-between gap-4 border-b border-ink/10 pb-4">
          <div>
            <div className="text-xs font-semibold uppercase tracking-[0.28em] text-ink/45">
              Work Output
            </div>
            <div className="font-display text-2xl">{brief.title ?? "Task Summary"}</div>
          </div>
          <div className="rounded-full bg-paper px-3 py-2 text-sm font-semibold text-ink">
            Confidence {confidence}%
          </div>
        </div>

        <section className="mt-4 rounded-2xl bg-paper/60 p-4">
          <div className="text-xs font-semibold uppercase tracking-[0.24em] text-ink/45">Summary</div>
          <p className="mt-2 text-sm leading-6 text-ink/80">
            {brief.executive_summary ?? "No summary available."}
          </p>
        </section>

        {brief.drafted_response ? (
          <section className="mt-4 rounded-2xl border border-ink/10 bg-white/80 p-4">
            <div className="text-xs font-semibold uppercase tracking-[0.24em] text-ink/45">Drafted Response</div>
            <p className="mt-2 text-sm leading-6 text-ink/80">{brief.drafted_response}</p>
          </section>
        ) : null}

        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <section className="rounded-2xl border border-ink/10 bg-white/80 p-4">
            <div className="text-xs font-semibold uppercase tracking-[0.24em] text-ink/45">Action Items</div>
            <ul className="mt-2 space-y-2 text-sm text-ink/80">
              {(brief.action_items ?? []).slice(0, 5).map((item) => (
                <li key={item}>• {item}</li>
              ))}
            </ul>
          </section>
          <section className="rounded-2xl border border-ink/10 bg-white/80 p-4">
            <div className="text-xs font-semibold uppercase tracking-[0.24em] text-ink/45">Schedule Updates</div>
            <ul className="mt-2 space-y-2 text-sm text-ink/80">
              {(brief.schedule_updates ?? []).slice(0, 5).map((item) => (
                <li key={item}>• {item}</li>
              ))}
            </ul>
          </section>
        </div>

        {onDecision ? (
          <div className="mt-5 flex flex-wrap gap-3">
            <button
              className="rounded-full bg-moss px-4 py-2 text-sm font-semibold text-white"
              onClick={() => onDecision("approve")}
            >
              Approve
            </button>
            <button
              className="rounded-full bg-ink px-4 py-2 text-sm font-semibold text-white"
              onClick={() => onDecision("modify")}
            >
              Modify
            </button>
            <button
              className="rounded-full border border-ink/20 px-4 py-2 text-sm font-semibold text-ink"
              onClick={() => onDecision("decline")}
            >
              Decline
            </button>
          </div>
        ) : null}
      </div>
    );
  }

  return (
    <div className="w-full rounded-[28px] border border-ink/10 bg-white/90 p-5 shadow-card">
      <div className="flex items-start justify-between gap-4 border-b border-ink/10 pb-4">
        <div>
          <div className="text-xs font-semibold uppercase tracking-[0.28em] text-ink/45">
            Intake Brief
          </div>
          <div className="font-display text-2xl">{brief.brief_id ?? "Pending Review"}</div>
        </div>
        <div className="rounded-full bg-paper px-3 py-2 text-sm font-semibold text-ink">
          Confidence {confidence}%
        </div>
      </div>

      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <section className="rounded-2xl bg-paper/70 p-4">
          <div className="text-xs font-semibold uppercase tracking-[0.24em] text-ink/45">Client</div>
          <div className="mt-2 text-lg font-semibold">{client.client_name ?? "Unknown prospect"}</div>
          <div className="text-sm text-ink/70">{client.client_email}</div>
          <div className="text-sm text-ink/70">{client.client_phone}</div>
        </section>
        <section className="rounded-2xl bg-paper/70 p-4">
          <div className="text-xs font-semibold uppercase tracking-[0.24em] text-ink/45">Matter</div>
          <div className="mt-2 text-lg font-semibold">{client.matter_type ?? "Unclear matter type"}</div>
          <div className="text-sm text-ink/70">Urgency: {client.urgency ?? "normal"}</div>
          <div className="text-sm text-ink/70">Value: {client.estimated_value ?? "Not stated"}</div>
        </section>
      </div>

      <section className="mt-4 rounded-2xl bg-paper/60 p-4">
        <div className="text-xs font-semibold uppercase tracking-[0.24em] text-ink/45">Assessment</div>
        <div className="mt-2 text-base font-semibold">
          {(analysis.qualification_decision ?? "needs_review").replaceAll("_", " ")}
        </div>
        <p className="mt-2 text-sm leading-6 text-ink/80">
          {brief.executive_summary ?? analysis.summary ?? "No summary available."}
        </p>
      </section>

      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <section className="rounded-2xl border border-ink/10 bg-white/80 p-4">
          <div className="text-xs font-semibold uppercase tracking-[0.24em] text-ink/45">Key Facts</div>
          <ul className="mt-2 space-y-2 text-sm text-ink/80">
            {(client.key_facts ?? []).slice(0, 4).map((fact) => (
              <li key={fact}>• {fact}</li>
            ))}
          </ul>
        </section>
        <section className="rounded-2xl border border-ink/10 bg-white/80 p-4">
          <div className="text-xs font-semibold uppercase tracking-[0.24em] text-ink/45">Next Steps</div>
          <ul className="mt-2 space-y-2 text-sm text-ink/80">
            {(brief.next_steps ?? analysis.recommended_actions ?? []).slice(0, 4).map((step) => (
              <li key={step}>• {step}</li>
            ))}
          </ul>
        </section>
      </div>

      <section className="mt-4 rounded-2xl border border-dashed border-accent/30 bg-accent/5 p-4">
        <div className="text-xs font-semibold uppercase tracking-[0.24em] text-ink/45">Flags</div>
        <div className="mt-2 text-sm text-ink/80">
          {(brief.flags ?? analysis.risk_flags ?? []).length
            ? (brief.flags ?? analysis.risk_flags ?? []).join(" • ")
            : "None"}
        </div>
      </section>

      {onDecision ? (
        <div className="mt-5 flex flex-wrap gap-3">
          <button
            className="rounded-full bg-moss px-4 py-2 text-sm font-semibold text-white"
            onClick={() => onDecision("approve")}
          >
            Approve
          </button>
          <button
            className="rounded-full bg-ink px-4 py-2 text-sm font-semibold text-white"
            onClick={() => onDecision("modify")}
          >
            Modify
          </button>
          <button
            className="rounded-full border border-ink/20 px-4 py-2 text-sm font-semibold text-ink"
            onClick={() => onDecision("decline")}
          >
            Decline
          </button>
        </div>
      ) : null}
    </div>
  );
}
