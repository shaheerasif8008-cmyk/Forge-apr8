export function StreamingIndicator() {
  return (
    <div className="inline-flex items-center gap-2 rounded-full border border-black/10 bg-white/70 px-3 py-2 text-sm text-ink/70 shadow-card">
      <span className="h-2 w-2 animate-pulse rounded-full bg-accent" />
      Arthur is processing the intake
    </div>
  );
}
