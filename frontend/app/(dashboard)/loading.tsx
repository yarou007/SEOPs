export default function Loading() {
  return (
    <div role="status" aria-live="polite" className="space-y-5">
      <p className="text-muted">Loading dashboard…</p>
      <div className="h-14 animate-pulse rounded-md bg-surface-muted" />
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="panel h-28 animate-pulse" />
        ))}
      </div>
      <div className="panel h-64 animate-pulse" />
    </div>
  );
}
