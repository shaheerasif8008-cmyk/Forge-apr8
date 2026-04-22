"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { fetchBuilds, fetchFactoryContext, type Build, type ClientOrg } from "@/lib/api";

export default function BuildsPage() {
  const [orgId, setOrgId] = useState("");
  const [orgs, setOrgs] = useState<ClientOrg[]>([]);
  const [builds, setBuilds] = useState<Build[]>([]);
  const [buildId, setBuildId] = useState("");
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
        setBuilds(await fetchBuilds(preferredOrgId));
      }
    }
    void loadContext();
    return () => {
      cancelled = true;
    };
  }, []);

  async function loadBuildsForOrg(nextOrgId: string) {
    setOrgId(nextOrgId);
    if (!nextOrgId) {
      setBuilds([]);
      return;
    }
    setBuilds(await fetchBuilds(nextOrgId));
  }

  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      <div className="rounded-[28px] border border-black/10 bg-white/85 p-8 shadow-lg">
        <div className="text-xs uppercase tracking-[0.28em] text-black/45">Build Timeline</div>
        <h1 className="mt-3 text-4xl font-semibold">Inspect pipeline logs and build events.</h1>
        <p className="mt-4 text-black/70">Browse recent builds for an accessible organization or jump directly to a known build.</p>
        <div className="mt-6 flex flex-wrap gap-3">
          <select
            className="min-w-[280px] rounded-full border border-black/10 bg-stone-50 px-4 py-3"
            disabled={loadingContext || !orgs.length}
            onChange={(event) => void loadBuildsForOrg(event.target.value)}
            value={orgId}
          >
            {orgs.length ? null : <option value="">No accessible organizations found</option>}
            {orgs.map((org) => (
              <option key={org.id} value={org.id}>
                {org.name} ({org.slug})
              </option>
            ))}
          </select>
          <input
            className="min-w-[320px] rounded-full border border-black/10 bg-stone-50 px-4 py-3"
            onChange={(event) => setBuildId(event.target.value)}
            placeholder="Paste build UUID"
            value={buildId}
          />
          <Link
            className={`rounded-full px-5 py-3 text-sm font-semibold text-white ${buildId ? "bg-black" : "pointer-events-none bg-black/30"}`}
            href={buildId ? `/builds/${buildId}` : "/builds"}
          >
            Open Build Tracker
          </Link>
        </div>

        <div className="mt-8 grid gap-4">
          {builds.map((build) => {
            const latestLog = build.logs[build.logs.length - 1] as { message?: string } | undefined;

            return (
              <Link
                key={build.id}
                className="rounded-[22px] border border-black/10 bg-stone-50 p-5 transition hover:bg-white"
                href={`/builds/${build.id}`}
              >
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <div className="text-xs uppercase tracking-[0.18em] text-black/45">{build.status}</div>
                    <div className="mt-2 font-semibold">{build.id}</div>
                  </div>
                  <div className="text-sm text-black/60">Iteration {build.iteration}</div>
                </div>
                <div className="mt-3 text-sm text-black/65">
                  {latestLog?.message || "No build logs recorded yet."}
                </div>
              </Link>
            );
          })}
          {!builds.length ? (
            <div className="rounded-[22px] bg-stone-100 p-6 text-center text-black/55">
              No builds found for the selected organization.
            </div>
          ) : null}
        </div>
      </div>
    </main>
  );
}
