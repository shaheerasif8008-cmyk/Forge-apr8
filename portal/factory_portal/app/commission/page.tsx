"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import {
  commissionFromSession,
  fetchFactoryContext,
  fetchRequirements,
  previewBlueprint,
  sendAnalystMessage,
  startAnalystSession,
  type AnalystSessionResponse,
  type ClientOrg,
} from "@/lib/api";

export default function CommissionPage() {
  const router = useRouter();
  const [orgId, setOrgId] = useState("");
  const [orgs, setOrgs] = useState<ClientOrg[]>([]);
  const [initialPrompt, setInitialPrompt] = useState("");
  const [session, setSession] = useState<AnalystSessionResponse | null>(null);
  const [draftReply, setDraftReply] = useState("");
  const [requirements, setRequirements] = useState<Record<string, unknown> | null>(null);
  const [blueprint, setBlueprint] = useState<Record<string, unknown> | null>(null);
  const [step, setStep] = useState(1);
  const [loadingContext, setLoadingContext] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function loadContext() {
      const context = await fetchFactoryContext();
      if (cancelled) {
        return;
      }
      setOrgs(context.orgs);
      const preferredOrgId = context.default_org_id || context.orgs[0]?.id || "";
      setOrgId(preferredOrgId);
      setLoadingContext(false);
    }
    void loadContext();
    return () => {
      cancelled = true;
    };
  }, []);

  async function beginIntake() {
    const created = await startAnalystSession(orgId, initialPrompt);
    setSession(created);
    setStep(2);
  }

  async function sendReply() {
    if (!session || !draftReply.trim()) {
      return;
    }
    const updated = await sendAnalystMessage(session.session_id, draftReply);
    setSession(updated);
    setDraftReply("");
  }

  async function moveToReview() {
    if (!session) {
      return;
    }
    const builtRequirements = await fetchRequirements(session.session_id);
    const builtBlueprint = await previewBlueprint(builtRequirements);
    setRequirements(builtRequirements);
    setBlueprint(builtBlueprint);
    setStep(3);
  }

  async function submitCommission() {
    if (!session) {
      return;
    }
    const result = await commissionFromSession(session.session_id, orgId);
    setStep(4);
    router.push(`/builds/${result.build_id}`);
  }

  return (
    <main className="mx-auto min-h-screen max-w-6xl px-6 py-10">
      <div className="rounded-[32px] border border-black/10 bg-white/85 p-8 shadow-xl">
        <div className="text-xs uppercase tracking-[0.28em] text-black/45">Commission Flow</div>
        <h1 className="mt-3 text-5xl font-semibold">Run intake, review the design, then queue the build.</h1>

        <div className="mt-8 grid gap-3 md:grid-cols-4">
          {["Start", "Chat", "Review", "Submit"].map((label, index) => (
            <div
              key={label}
              className={`rounded-[20px] px-4 py-3 text-sm font-medium ${
                step === index + 1 ? "bg-black text-white" : step > index + 1 ? "bg-emerald-100 text-emerald-900" : "bg-stone-100 text-black/60"
              }`}
            >
              {index + 1}. {label}
            </div>
          ))}
        </div>

        {step === 1 ? (
          <section className="mt-8 grid gap-4">
            <label className="grid gap-2">
              <span className="text-sm font-medium text-black/70">Organization</span>
              <select
                className="rounded-[22px] border border-black/10 bg-stone-50 px-4 py-3"
                disabled={loadingContext || !orgs.length}
                onChange={(event) => setOrgId(event.target.value)}
                value={orgId}
              >
                {orgs.length ? null : <option value="">No accessible organizations found</option>}
                {orgs.map((org) => (
                  <option key={org.id} value={org.id}>
                    {org.name} ({org.slug})
                  </option>
                ))}
              </select>
            </label>
            <textarea
              className="min-h-40 rounded-[22px] border border-black/10 bg-stone-50 px-4 py-3"
              onChange={(event) => setInitialPrompt(event.target.value)}
              placeholder="Describe the employee the client wants built."
              value={initialPrompt}
            />
            <button
              className="w-fit rounded-full bg-black px-5 py-3 text-sm font-semibold text-white"
              disabled={!initialPrompt.trim() || !orgId || loadingContext}
              onClick={() => void beginIntake()}
              type="button"
            >
              Start Intake Session
            </button>
          </section>
        ) : null}

        {step === 2 && session ? (
          <section className="mt-8 grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
            <div className="rounded-[24px] border border-black/10 bg-stone-50 p-5">
              <div className="text-sm font-semibold">Transcript</div>
              <div className="mt-4 space-y-3">
                {session.transcript.map((message, index) => (
                  <div key={`${message.role}-${index}`} className="rounded-[20px] bg-white p-4">
                    <div className="text-xs uppercase tracking-[0.18em] text-black/45">{message.role}</div>
                    <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-black/75">{message.content}</p>
                  </div>
                ))}
              </div>
              <div className="mt-5 rounded-[20px] bg-white p-4">
                <div className="text-xs uppercase tracking-[0.18em] text-black/45">Next Question</div>
                <div className="mt-2 text-sm text-black/75">{session.next_question || "Analyst has enough information to move to review."}</div>
              </div>
              <div className="mt-4 flex gap-3">
                <textarea
                  className="min-h-24 flex-1 rounded-[20px] border border-black/10 bg-white px-4 py-3"
                  onChange={(event) => setDraftReply(event.target.value)}
                  placeholder="Answer the analyst's current question."
                  value={draftReply}
                />
              </div>
              <div className="mt-4 flex flex-wrap gap-3">
                <button
                  className="rounded-full bg-black px-5 py-3 text-sm font-semibold text-white"
                  onClick={() => void sendReply()}
                  type="button"
                >
                  Send Reply
                </button>
                <button
                  className="rounded-full bg-stone-200 px-5 py-3 text-sm font-semibold text-black"
                  onClick={() => void moveToReview()}
                  type="button"
                >
                  Review Requirements
                </button>
              </div>
            </div>

            <div className="rounded-[24px] border border-black/10 bg-white p-5">
              <div className="text-xs uppercase tracking-[0.18em] text-black/45">Session Summary</div>
              <div className="mt-4 space-y-3 text-sm text-black/75">
                <div>Employee type: <span className="font-semibold">{session.employee_type}</span></div>
                <div>Risk tier: <span className="font-semibold">{session.risk_tier}</span></div>
                <div>Completeness: <span className="font-semibold">{session.completeness_score.toFixed(2)}</span></div>
                <div>Ready: <span className="font-semibold">{String(session.is_complete)}</span></div>
              </div>
            </div>
          </section>
        ) : null}

        {step === 3 ? (
          <section className="mt-8 grid gap-6 lg:grid-cols-2">
            <div className="rounded-[24px] border border-black/10 bg-stone-50 p-5">
              <div className="text-sm font-semibold">Requirements</div>
              <pre className="mt-4 overflow-x-auto whitespace-pre-wrap text-xs leading-6 text-black/75">
                {JSON.stringify(requirements, null, 2)}
              </pre>
            </div>
            <div className="rounded-[24px] border border-black/10 bg-white p-5">
              <div className="text-sm font-semibold">Blueprint Preview</div>
              <pre className="mt-4 overflow-x-auto whitespace-pre-wrap text-xs leading-6 text-black/75">
                {JSON.stringify(blueprint, null, 2)}
              </pre>
            </div>
            <button
              className="w-fit rounded-full bg-black px-5 py-3 text-sm font-semibold text-white"
              onClick={() => void submitCommission()}
              type="button"
            >
              Submit Commission and Queue Build
            </button>
          </section>
        ) : null}
      </div>
    </main>
  );
}
