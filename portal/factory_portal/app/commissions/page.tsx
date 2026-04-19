import Link from "next/link";

export default function CommissionsPage() {
  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      <div className="rounded-[28px] border border-black/10 bg-white/85 p-8 shadow-lg">
        <div className="text-xs uppercase tracking-[0.28em] text-black/45">Commissions</div>
        <h1 className="mt-3 text-4xl font-semibold">Queue new employees and track build progress.</h1>
        <p className="mt-4 text-black/70">
          The generalized factory supports legal-intake and executive-assistant archetypes through the shared
          commission and build pipeline.
        </p>
        <Link
          className="mt-6 inline-flex rounded-full bg-black px-5 py-3 text-sm font-semibold text-white"
          href="/commission"
        >
          Open the 4-step commission flow
        </Link>
      </div>
    </main>
  );
}
