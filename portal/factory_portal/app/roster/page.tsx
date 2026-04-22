"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { fetchFactoryContext, fetchRoster, type ClientOrg } from "@/lib/api";

type Deployment = {
  id: string;
  status: string;
  format: string;
  access_url: string;
  build_id: string;
};

export default function RosterPage() {
  const [orgId, setOrgId] = useState("");
  const [orgs, setOrgs] = useState<ClientOrg[]>([]);
  const [deployments, setDeployments] = useState<Deployment[]>([]);
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
      if (preferredOrgId) {
        setDeployments((await fetchRoster(preferredOrgId)) as Deployment[]);
      }
    }
    void loadContext();
    return () => {
      cancelled = true;
    };
  }, []);

  async function loadRoster() {
    if (!orgId) {
      return;
    }
    setDeployments((await fetchRoster(orgId)) as Deployment[]);
  }

  return (
    <main className="mx-auto min-h-screen max-w-6xl px-6 py-10">
      <div className="rounded-[32px] border border-black/10 bg-white/85 p-8 shadow-xl">
        <div className="text-xs uppercase tracking-[0.28em] text-black/45">Roster</div>
        <h1 className="mt-3 text-5xl font-semibold">See every deployed employee for an organization.</h1>

        <div className="mt-6 flex flex-wrap gap-3">
          <select
            className="min-w-[320px] rounded-full border border-black/10 bg-stone-50 px-4 py-3"
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
          <button
            className="rounded-full bg-black px-5 py-3 text-sm font-semibold text-white"
            disabled={!orgId || loadingContext}
            onClick={() => void loadRoster()}
            type="button"
          >
            Load Roster
          </button>
        </div>

        <div className="mt-8 grid gap-4 md:grid-cols-2">
          {deployments.map((deployment) => (
            <article key={deployment.id} className="rounded-[24px] border border-black/10 bg-stone-50 p-5">
              <div className="text-xs uppercase tracking-[0.18em] text-black/45">{deployment.format}</div>
              <div className="mt-2 text-lg font-semibold">{deployment.id}</div>
              <div className="mt-2 text-sm text-black/70">Status: {deployment.status}</div>
              <div className="mt-1 break-all text-sm text-black/60">Access: {deployment.access_url || "not yet assigned"}</div>
              <Link
                className="mt-4 inline-flex rounded-full bg-black px-4 py-2 text-sm font-semibold text-white"
                href={`/employees/${deployment.id}`}
              >
                Open Employee Detail
              </Link>
            </article>
          ))}
          {!deployments.length ? (
            <div className="rounded-[24px] bg-stone-100 p-8 text-center text-black/55">
              No deployments found for the selected organization.
            </div>
          ) : null}
        </div>
      </div>
    </main>
  );
}
