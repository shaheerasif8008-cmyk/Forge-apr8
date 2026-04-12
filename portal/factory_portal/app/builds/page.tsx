export default function BuildsPage() {
  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      <div className="rounded-[28px] border border-black/10 bg-white/85 p-8 shadow-lg">
        <div className="text-xs uppercase tracking-[0.28em] text-black/45">Build Timeline</div>
        <h1 className="mt-3 text-4xl font-semibold">Inspect pipeline logs and build events.</h1>
        <p className="mt-4 text-black/70">
          Use `/api/v1/builds/:id` and `/api/v1/builds/:id/events` for live build state and event-style log playback.
        </p>
      </div>
    </main>
  );
}
