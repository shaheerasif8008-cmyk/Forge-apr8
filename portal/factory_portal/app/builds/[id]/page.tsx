"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { fetchBuild, resolveFactoryApiBaseUrl, retryBuild } from "@/lib/api";

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
    void fetchBuild(buildId).then((build) => {
      setStatus(build.status);
      setIteration(build.iteration);
      setLogs((build.logs as BuildLog[]) ?? []);
    });

    const source = new EventSource(`${resolveFactoryApiBaseUrl()}/api/v1/builds/${buildId}/stream`);
    source.addEventListener("build", (event) => {
      const payload = JSON.parse((event as MessageEvent).data) as {
        status: string;
        iteration: number;
        logs: BuildLog[];
      };
      setStatus(payload.status);
      setIteration(payload.iteration);
      setLogs((current) => (current.length === 0 ? payload.logs : [...current, ...payload.logs]));
    });
    return () => source.close();
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
            className="rounded-full bg-black px-5 py-3 text-sm font-semibold text-white disabled:bg-black/30"
            disabled={status !== "failed"}
            onClick={() => void handleRetry()}
            type="button"
          >
            Retry Failed Build
          </button>
        </div>

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
