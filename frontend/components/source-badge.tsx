import type { SyncLog } from "@/lib/types";

export function SourceBadge({ log }: { log: SyncLog | null }) {
  if (!log || !log.status)
    return <span className="badge badge-muted">Not connected</span>;
  return (
    <span
      className={`badge ${log.status === "ok" ? "badge-good" : "badge-bad"}`}
    >
      {log.status === "ok" ? "OK" : "Error"}
    </span>
  );
}
