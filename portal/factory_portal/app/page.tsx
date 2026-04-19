import Link from "next/link";

const links = [
  { href: "/commission", label: "Commission Flow" },
  { href: "/builds", label: "Build Tracker" },
  { href: "/roster", label: "Roster" },
  { href: "/monitoring", label: "Monitoring" },
  { href: "/updates", label: "Updates & Policies" },
];

export default function HomePage() {
  return (
    <main className="mx-auto min-h-screen max-w-6xl px-6 py-10">
      <div className="rounded-[32px] border border-black/10 bg-white/80 p-8 shadow-xl">
        <div className="text-xs uppercase tracking-[0.28em] text-black/45">Forge Factory Portal</div>
        <h1 className="mt-3 text-5xl font-semibold">Commission, build, deploy, and supervise AI employees.</h1>
        <p className="mt-4 max-w-3xl text-lg text-black/70">
          This portal is the Layer 1 surface for the generalized Forge factory: analyst intake, blueprint preview,
          build tracking, deployment oversight, monitoring, and updates.
        </p>

        <div className="mt-8 grid gap-4 md:grid-cols-2 xl:grid-cols-5">
          {links.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="rounded-[24px] border border-black/10 bg-sand p-5 text-lg font-medium transition hover:-translate-y-0.5 hover:bg-white"
            >
              {link.label}
            </Link>
          ))}
        </div>
      </div>
    </main>
  );
}
