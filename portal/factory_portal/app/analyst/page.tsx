export default function AnalystPage() {
  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      <div className="rounded-[28px] border border-black/10 bg-white/85 p-8 shadow-lg">
        <div className="text-xs uppercase tracking-[0.28em] text-black/45">Analyst Intake</div>
        <h1 className="mt-3 text-4xl font-semibold">Run structured intake before a commission is queued.</h1>
        <p className="mt-4 text-black/70">
          Use the `/api/v1/analyst/sessions` endpoints to open an intake session, collect clarifications, synthesize
          requirements, preview the blueprint, and commission directly from the analyst output.
        </p>
      </div>
    </main>
  );
}
