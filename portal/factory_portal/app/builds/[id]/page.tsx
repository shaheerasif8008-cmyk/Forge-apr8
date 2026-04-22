"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { approveBuild, fetchBuild, rejectBuild, retryBuild } from "@/lib/api";

type BuildLog = {
  timestamp?: string;
  stage: string;
  level?: string;
  message: string;
};

export default function BuildDetailPage() {
  const params = useParams<{ id: string }>();
  const buildId = Array.isArray(params?.id) ? params.id[0] : params?.id;
  const [status, setStatus] = useState("");
  const [iteration, setIteration] = useState(1);
  const [logs, setLogs] = useState<BuildLog[]>([]);

  useEffect(() => {
    if (!buildId) {
      return;
    }
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;
    const terminalStatuses = new Set(["failed", "deployed", "pending_review", "pending_client_action"]);

    const poll = async () => {
      const build = await fetchBuild(buildId);
      if (cancelled) {
        return;
      }
      setStatus(build.status);
      setIteration(build.iteration);
      setLogs((build.logs as BuildLog[]) ?? []);
      if (!terminalStatuses.has(build.status)) {
        timer = setTimeout(() => void poll(), 1000);
      }
    };

    void poll();
    return () => {
      cancelled = true;
      if (timer) {
        clearTimeout(timer);
      }
    };
  }, [buildId]);

  async function handleRetry() {
    if (!buildId) {
      return;
    }
    const build = await retryBuild(buildId);
    setStatus(build.status);
    setIteration(build.iteration);
    setLogs((build.logs as BuildLog[]) ?? []);
  }

  async function handleApprove() {
    if (!buildId) {
      return;
    }
    const build = await approveBuild(buildId);
    setStatus(build.status);
    setIteration(build.iteration);
    setLogs((build.logs as BuildLog[]) ?? []);
  }

  async function handleReject() {
    if (!buildId) {
      return;
    }
    const build = await rejectBuild(buildId);
    setStatus(build.status);
    setIteration(build.iteration);
    setLogs((build.logs as BuildLog[]) ?? []);
  }

  return (
    <main className="mx-auto min-h-screen max-w-6xl px-6 py-10">
      <div className="rounded-[32px] border border-black/10 bg-white/85 p-8 shadow-xl">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="text-xs uppercase tracking-[0.28em] text-black/45">Build Tracker</div>
            <h1 className="mt-3 text-4xl font-semibold">Live build state, logs, and retry controls.</h1>
          </div>
          <Link className="rounded-full bg-black px-4 py-2 text-sm font-semibold text-white" href="/builds">
            Back to Builds
          </Link>
        </div>

        <div className="mt-6 grid gap-4 md:grid-cols-3">
          <StatCard label="Build ID" value={buildId ?? ""} />
          <StatCard label="Status" value={status} />
          <StatCard label="Iteration" value={String(iteration)} />
        </div>

        <div className="mt-6 flex flex-wrap gap-3">
          <button
            className="rounded-full bg-emerald-600 px-5 py-3 text-sm font-semibold text-white disabled:bg-emerald-300"
            disabled={status !== "pending_review"}
            onClick={() => void handleApprove()}
            type="button"
          >
            Approve and Deploy
          </button>
          <button
            className="rounded-full bg-amber-500 px-5 py-3 text-sm font-semibold text-white disabled:bg-amber-200"
            disabled={status !== "pending_review"}
            onClick={() => void handleReject()}
            type="button"
          >
            Reject Build
          </button>
          <button
            className="rounded-full bg-black px-5 py-3 text-sm font-semibold text-white disabled:bg-black/30"
            disabled={status !== "failed"}
            onClick={() => void handleRetry()}
            type="button"
          >
            Retry Failed Build
          </button>
        </div>

        {status === "pending_review" ? (
          <div className="mt-4 rounded-[20px] border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            Human review is required before deployment can continue.
          </div>
        ) : null}

        {status === "pending_client_action" ? (
          <div className="mt-4 rounded-[20px] border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-900">
            The build is complete and waiting on client-side setup or activation steps.
          </div>
        ) : null}

        <div className="mt-6 rounded-[24px] border border-black/10 bg-stone-50 p-5">
          <div className="text-sm font-semibold">Build Logs</div>
          <div className="mt-4 space-y-3">
            {logs.map((log, index) => (
              <article key={`${log.stage}-${index}`} className="rounded-[18px] bg-white p-4">
                <div className="flex items-center justify-between gap-3">
                  <div className="text-sm font-semibold">{log.stage}</div>
                  <div className="text-xs uppercase tracking-[0.18em] text-black/45">{log.level ?? "info"}</div>
                </div>
                <p className="mt-2 text-sm leading-6 text-black/75">{log.message}</p>
              </article>
            ))}
            {!logs.length ? <div className="text-sm text-black/55">Waiting for build events…</div> : null}
          </div>
        </div>
      </div>
    </main>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[22px] border border-black/10 bg-stone-50 p-4">
      <div className="text-xs uppercase tracking-[0.18em] text-black/45">{label}</div>
      <div className="mt-2 break-all text-sm font-semibold text-black">{value || "—"}</div>
    </div>
  );
}
