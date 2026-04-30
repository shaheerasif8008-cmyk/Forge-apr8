"use client";

import { useEffect, useState } from "react";

import {
  addPolicyRule,
  fetchFactoryContext,
  fetchRoster,
  fetchUpdates,
  scheduleModuleUpgrade,
  setLearningState,
  type ClientOrg,
  type Deployment,
} from "@/lib/api";

export default function UpdatesPage() {
  const [orgs, setOrgs] = useState<ClientOrg[]>([]);
  const [orgId, setOrgId] = useState("");
  const [deployments, setDeployments] = useState<Deployment[]>([]);
  const [deploymentId, setDeploymentId] = useState("");
  const [updates, setUpdates] = useState<Record<string, unknown>>({});
  const [componentId, setComponentId] = useState("research_engine");
  const [targetVersion, setTargetVersion] = useState("2.0.0");
  const [policyDescription, setPolicyDescription] = useState("No non-urgent messages after quiet hours.");
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
      setUpdates(await fetchUpdates(nextDeploymentId));
    } else {
      setUpdates({});
    }
  }

  async function loadUpdates(nextDeploymentId = deploymentId) {
    if (!nextDeploymentId) return;
    setDeploymentId(nextDeploymentId);
    setUpdates(await fetchUpdates(nextDeploymentId));
  }

  async function toggleLearning(enabled: boolean) {
    if (!deploymentId) return;
    await setLearningState(deploymentId, enabled);
    await loadUpdates();
  }

  async function queueModuleUpgrade() {
    if (!deploymentId) return;
    await scheduleModuleUpgrade(deploymentId, {
      component_id: componentId,
      target_version: targetVersion,
      summary: "Requested from updates console",
    });
    await loadUpdates();
  }

  async function createPolicyRule() {
    if (!deploymentId || !policyDescription.trim()) return;
    await addPolicyRule(deploymentId, {
      rule_id: `policy-${Date.now()}`,
      description: policyDescription.trim(),
      condition: "time_of_day > 17:00",
      action: "suppress_non_urgent_messages",
      priority: 2,
      active: true,
    });
    await loadUpdates();
  }

  return (
    <main className="mx-auto max-w-6xl px-6 py-10">
      <div className="rounded-[28px] border border-black/10 bg-white/85 p-8 shadow-lg">
        <div className="text-xs uppercase tracking-[0.28em] text-black/45">Updates & Policies</div>
        <h1 className="mt-3 text-4xl font-semibold">Security, learning, modules, marketplace, and rules.</h1>

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
            onChange={(event) => void loadUpdates(event.target.value)}
            value={deploymentId}
          >
            {deployments.length ? null : <option value="">No deployments found</option>}
            {deployments.map((deployment) => (
              <option key={deployment.id} value={deployment.id}>
                {deployment.id} ({deployment.status})
              </option>
            ))}
          </select>
        </div>

        <div className="mt-8 grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
          <section className="rounded-[24px] border border-black/10 bg-stone-50 p-5">
            <div className="text-sm font-semibold">Current Update State</div>
            <pre className="mt-4 max-h-[620px] overflow-auto whitespace-pre-wrap rounded-[18px] bg-white p-4 text-xs leading-6 text-black/70">
              {JSON.stringify(updates, null, 2)}
            </pre>
          </section>

          <section className="space-y-4">
            <div className="rounded-[24px] border border-black/10 bg-white p-5">
              <div className="text-sm font-semibold">Learning</div>
              <div className="mt-4 flex gap-3">
                <button className="rounded-full bg-emerald-700 px-4 py-2 text-sm font-semibold text-white disabled:bg-emerald-300" disabled={!deploymentId} onClick={() => void toggleLearning(true)} type="button">
                  Enable
                </button>
                <button className="rounded-full bg-stone-900 px-4 py-2 text-sm font-semibold text-white disabled:bg-stone-300" disabled={!deploymentId} onClick={() => void toggleLearning(false)} type="button">
                  Pause
                </button>
              </div>
            </div>

            <div className="rounded-[24px] border border-black/10 bg-white p-5">
              <div className="text-sm font-semibold">Module Upgrade</div>
              <input className="mt-4 w-full rounded-full border border-black/10 bg-stone-50 px-4 py-3" onChange={(event) => setComponentId(event.target.value)} value={componentId} />
              <input className="mt-3 w-full rounded-full border border-black/10 bg-stone-50 px-4 py-3" onChange={(event) => setTargetVersion(event.target.value)} value={targetVersion} />
              <button className="mt-4 rounded-full bg-black px-5 py-3 text-sm font-semibold text-white disabled:bg-black/30" disabled={!deploymentId || !componentId.trim() || !targetVersion.trim()} onClick={() => void queueModuleUpgrade()} type="button">
                Queue Upgrade
              </button>
            </div>

            <div className="rounded-[24px] border border-black/10 bg-white p-5">
              <div className="text-sm font-semibold">Policy Rule</div>
              <textarea className="mt-4 min-h-28 w-full rounded-[18px] border border-black/10 bg-stone-50 px-4 py-3" onChange={(event) => setPolicyDescription(event.target.value)} value={policyDescription} />
              <button className="mt-4 rounded-full bg-black px-5 py-3 text-sm font-semibold text-white disabled:bg-black/30" disabled={!deploymentId || !policyDescription.trim()} onClick={() => void createPolicyRule()} type="button">
                Add Rule
              </button>
            </div>
          </section>
        </div>
      </div>
    </main>
  );
}
