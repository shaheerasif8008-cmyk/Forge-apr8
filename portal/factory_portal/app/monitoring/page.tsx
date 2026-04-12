export default function MonitoringPage() {
  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      <div className="rounded-[28px] border border-black/10 bg-white/85 p-8 shadow-lg">
        <div className="text-xs uppercase tracking-[0.28em] text-black/45">Monitoring</div>
        <h1 className="mt-3 text-4xl font-semibold">Review health events and deployment metrics.</h1>
        <p className="mt-4 text-black/70">
          Hosted deployments now persist monitoring events and performance metrics through the factory API.
        </p>
      </div>
    </main>
  );
}
