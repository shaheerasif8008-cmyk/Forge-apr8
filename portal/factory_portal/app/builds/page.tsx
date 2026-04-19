"use client";

import Link from "next/link";
import { useState } from "react";

export default function BuildsPage() {
  const [buildId, setBuildId] = useState("");

  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      <div className="rounded-[28px] border border-black/10 bg-white/85 p-8 shadow-lg">
        <div className="text-xs uppercase tracking-[0.28em] text-black/45">Build Timeline</div>
        <h1 className="mt-3 text-4xl font-semibold">Inspect pipeline logs and build events.</h1>
        <p className="mt-4 text-black/70">Enter a build ID to open the live tracker with streamed logs and retry controls.</p>
        <div className="mt-6 flex flex-wrap gap-3">
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
      </div>
    </main>
  );
}
