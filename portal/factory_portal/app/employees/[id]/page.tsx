"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";

import {
  fetchDeployment,
  fetchMonitoringEvents,
  fetchMonitoringMetrics,
  fetchUpdates,
  pauseDeployment,
  restartDeployment,
  rollbackDeployment,
  scheduleModuleUpgrade,
} from "@/lib/api";

type Deployment = {
  id: string;
  status: string;
  format: string;
  access_url: string;
  build_id: string;
};

export default function EmployeeDetailPage() {
  const params = useParams<{ id: string }>();
  const deploymentId = Array.isArray(params?.id) ? params.id[0] : params?.id;
  const [deployment, setDeployment] = useState<Deployment | null>(null);
  const [events, setEvents] = useState<Array<Record<string, unknown>>>([]);
  const [metrics, setMetrics] = useState<Array<Record<string, unknown>>>([]);
  const [updates, setUpdates] = useState<Record<string, unknown>>({});
  const [componentId, setComponentId] = useState("research_engine");
  const [targetVersion, setTargetVersion] = useState("2.0.0");

  async function load() {
    if (!deploymentId) {
      return;
    }
    const [nextDeployment, nextEvents, nextMetrics, nextUpdates] = await Promise.all([
      fetchDeployment(deploymentId),
      fetchMonitoringEvents(deploymentId),
      fetchMonitoringMetrics(deploymentId),
      fetchUpdates(deploymentId),
    ]);
    setDeployment(nextDeployment as Deployment);
    setEvents(nextEvents);
    setMetrics(nextMetrics);
    setUpdates(nextUpdates);
  }

  useEffect(() => {
    void load();
  }, [deploymentId]);

  async function perform(action: "pause" | "restart" | "rollback") {
    if (!deploymentId) {
      return;
    }
    if (action === "pause") {
      await pauseDeployment(deploymentId);
    } else if (action === "restart") {
      await restartDeployment(deploymentId);
    } else {
      await rollbackDeployment(deploymentId);
    }
    await load();
  }

  async function queueUpdate() {
    if (!deploymentId) {
      return;
    }
    await scheduleModuleUpgrade(deploymentId, {
      component_id: componentId,
      target_version: targetVersion,
      summary: "Requested from roster detail view",
    });
    await load();
  }

  return (
    <main className="mx-auto min-h-screen max-w-6xl px-6 py-10">
      <div className="rounded-[32px] border border-black/10 bg-white/85 p-8 shadow-xl">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="text-xs uppercase tracking-[0.28em] text-black/45">Employee Detail</div>
            <h1 className="mt-3 text-4xl font-semibold">Deployment state, monitoring, and control actions.</h1>
          </div>
          <Link className="rounded-full bg-black px-4 py-2 text-sm font-semibold text-white" href="/roster">
            Back to Roster
          </Link>
        </div>

        {deployment ? (
          <>
            <div className="mt-6 grid gap-4 md:grid-cols-4">
              <StatCard label="Deployment" value={deployment.id} />
              <StatCard label="Status" value={deployment.status} />
              <StatCard label="Format" value={deployment.format} />
              <StatCard label="Access URL" value={deployment.access_url || "not yet assigned"} />
            </div>

            <div className="mt-6 flex flex-wrap gap-3">
              <button className="rounded-full bg-stone-900 px-5 py-3 text-sm font-semibold text-white" onClick={() => void perform("pause")} type="button">
                Pause
              </button>
              <button className="rounded-full bg-emerald-700 px-5 py-3 text-sm font-semibold text-white" onClick={() => void perform("restart")} type="button">
                Restart
              </button>
              <button className="rounded-full bg-amber-700 px-5 py-3 text-sm font-semibold text-white" onClick={() => void perform("rollback")} type="button">
                Rollback
              </button>
            </div>

            <div className="mt-6 rounded-[24px] border border-black/10 bg-stone-50 p-5">
              <div className="text-sm font-semibold">Schedule Module Update</div>
              <div className="mt-4 flex flex-wrap gap-3">
                <input
                  className="rounded-full border border-black/10 bg-white px-4 py-3"
                  onChange={(event) => setComponentId(event.target.value)}
                  placeholder="component_id"
                  value={componentId}
                />
                <input
                  className="rounded-full border border-black/10 bg-white px-4 py-3"
                  onChange={(event) => setTargetVersion(event.target.value)}
                  placeholder="target_version"
                  value={targetVersion}
                />
                <button className="rounded-full bg-black px-5 py-3 text-sm font-semibold text-white" onClick={() => void queueUpdate()} type="button">
                  Queue Update
                </button>
              </div>
              <pre className="mt-4 overflow-x-auto whitespace-pre-wrap text-xs leading-6 text-black/70">
                {JSON.stringify(updates, null, 2)}
              </pre>
            </div>

            <div className="mt-6 grid gap-6 lg:grid-cols-2">
              <section className="rounded-[24px] border border-black/10 bg-stone-50 p-5">
                <div className="text-sm font-semibold">Monitoring Events</div>
                <div className="mt-4 space-y-3">
                  {events.map((event, index) => (
                    <article key={`event-${index}`} className="rounded-[18px] bg-white p-4 text-sm text-black/75">
                      <div className="font-semibold">{String(event.title ?? event.category ?? "event")}</div>
                      <div className="mt-2 whitespace-pre-wrap">{JSON.stringify(event.detail ?? event, null, 2)}</div>
                    </article>
                  ))}
                </div>
              </section>

              <section className="rounded-[24px] border border-black/10 bg-white p-5">
                <div className="text-sm font-semibold">Performance Metrics</div>
                <div className="mt-4 space-y-3">
                  {metrics.map((metric, index) => (
                    <article key={`metric-${index}`} className="rounded-[18px] bg-stone-50 p-4 text-sm text-black/75">
                      <div className="font-semibold">{String(metric.metric_name ?? "metric")}</div>
                      <div className="mt-1">
                        {String(metric.value ?? "")} {String(metric.unit ?? "")}
                      </div>
                    </article>
                  ))}
                </div>
              </section>
            </div>
          </>
        ) : (
          <div className="mt-8 rounded-[24px] bg-stone-100 p-8 text-center text-black/55">Loading deployment…</div>
        )}
      </div>
    </main>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[22px] border border-black/10 bg-stone-50 p-4">
      <div className="text-xs uppercase tracking-[0.18em] text-black/45">{label}</div>
      <div className="mt-2 break-all text-sm font-semibold text-black">{value}</div>
    </div>
  );
}
