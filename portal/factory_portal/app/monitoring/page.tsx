"use client";

import { useEffect, useState } from "react";

import {
  fetchFactoryContext,
  fetchMonitoringEvents,
  fetchMonitoringMetrics,
  fetchRoster,
  type ClientOrg,
  type Deployment,
} from "@/lib/api";

export default function MonitoringPage() {
  const [orgs, setOrgs] = useState<ClientOrg[]>([]);
  const [orgId, setOrgId] = useState("");
  const [deployments, setDeployments] = useState<Deployment[]>([]);
  const [deploymentId, setDeploymentId] = useState("");
  const [events, setEvents] = useState<Array<Record<string, unknown>>>([]);
  const [metrics, setMetrics] = useState<Array<Record<string, unknown>>>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function loadContext() {
      const context = await fetchFactoryContext();
      if (cancelled) return;
      const preferredOrgId = context.default_org_id || context.orgs[0]?.id || "";
      setOrgs(context.orgs);
      setOrgId(preferredOrgId);
      setLoading(false);
      if (preferredOrgId) {
        await loadDeployments(preferredOrgId);
      }
    }
    void loadContext();
    return () => {
      cancelled = true;
    };
  }, []);

  async function loadDeployments(nextOrgId: string) {
    setOrgId(nextOrgId);
    const nextDeployments = nextOrgId ? await fetchRoster(nextOrgId) : [];
    setDeployments(nextDeployments);
    const nextDeploymentId = nextDeployments[0]?.id || "";
    setDeploymentId(nextDeploymentId);
    if (nextDeploymentId) {
      await loadMonitoring(nextDeploymentId);
    } else {
      setEvents([]);
      setMetrics([]);
    }
  }

  async function loadMonitoring(nextDeploymentId = deploymentId) {
    if (!nextDeploymentId) return;
    setDeploymentId(nextDeploymentId);
    const [nextEvents, nextMetrics] = await Promise.all([
      fetchMonitoringEvents(nextDeploymentId),
      fetchMonitoringMetrics(nextDeploymentId),
    ]);
    setEvents(nextEvents);
    setMetrics(nextMetrics);
  }

  return (
    <main className="mx-auto max-w-6xl px-6 py-10">
      <div className="rounded-[28px] border border-black/10 bg-white/85 p-8 shadow-lg">
        <div className="text-xs uppercase tracking-[0.28em] text-black/45">Monitoring</div>
        <h1 className="mt-3 text-4xl font-semibold">Health events and deployment metrics.</h1>

        <div className="mt-6 flex flex-wrap gap-3">
          <select
            className="min-w-[260px] rounded-full border border-black/10 bg-stone-50 px-4 py-3"
            disabled={loading || !orgs.length}
            onChange={(event) => void loadDeployments(event.target.value)}
            value={orgId}
          >
            {orgs.length ? null : <option value="">No accessible organizations found</option>}
            {orgs.map((org) => (
              <option key={org.id} value={org.id}>
                {org.name} ({org.slug})
              </option>
            ))}
          </select>
          <select
            className="min-w-[280px] rounded-full border border-black/10 bg-stone-50 px-4 py-3"
            disabled={!deployments.length}
            onChange={(event) => void loadMonitoring(event.target.value)}
            value={deploymentId}
          >
            {deployments.length ? null : <option value="">No deployments found</option>}
            {deployments.map((deployment) => (
              <option key={deployment.id} value={deployment.id}>
                {deployment.id} ({deployment.status})
              </option>
            ))}
          </select>
          <button
            className="rounded-full bg-black px-5 py-3 text-sm font-semibold text-white disabled:bg-black/30"
            disabled={!deploymentId}
            onClick={() => void loadMonitoring()}
            type="button"
          >
            Refresh
          </button>
        </div>

        <div className="mt-8 grid gap-6 lg:grid-cols-2">
          <section className="rounded-[24px] border border-black/10 bg-stone-50 p-5">
            <div className="text-sm font-semibold">Events</div>
            <div className="mt-4 space-y-3">
              {events.map((event, index) => (
                <article key={`event-${index}`} className="rounded-[18px] bg-white p-4 text-sm text-black/75">
                  <div className="font-semibold">{String(event.title ?? event.category ?? event.event_type ?? "event")}</div>
                  <pre className="mt-2 overflow-x-auto whitespace-pre-wrap text-xs">{JSON.stringify(event, null, 2)}</pre>
                </article>
              ))}
              {!events.length ? <div className="rounded-[18px] bg-white p-4 text-sm text-black/55">No monitoring events recorded for this deployment.</div> : null}
            </div>
          </section>

          <section className="rounded-[24px] border border-black/10 bg-white p-5">
            <div className="text-sm font-semibold">Metrics</div>
            <div className="mt-4 space-y-3">
              {metrics.map((metric, index) => (
                <article key={`metric-${index}`} className="rounded-[18px] bg-stone-50 p-4 text-sm text-black/75">
                  <div className="font-semibold">{String(metric.metric_name ?? "metric")}</div>
                  <div className="mt-1">
                    {String(metric.value ?? "")} {String(metric.unit ?? "")}
                  </div>
                </article>
              ))}
              {!metrics.length ? <div className="rounded-[18px] bg-stone-50 p-4 text-sm text-black/55">No performance metrics recorded for this deployment.</div> : null}
            </div>
          </section>
        </div>
      </div>
    </main>
  );
}
