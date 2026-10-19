import type { SourceStatus } from "@/lib/types";
import { formatDate, formatNumber, formatTime } from "@/lib/format";
import { isStale } from "@/lib/dates";
import { SourceBadge } from "./source-badge";

export function StatusTable({ status }: { status: SourceStatus }) {
  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold">Data status</h2>
        <p className="mt-1 text-sm text-muted">
          Source sync progress. Dates more than 5 days old are marked stale.
        </p>
      </div>
      <div className="table-wrap">
        <table aria-label="Data status" className="min-w-[800px]">
          <thead>
            <tr>
              <th>Source</th>
              <th>Last loaded</th>
              <th>Last run</th>
              <th>Status</th>
              <th className="numeric">Rows loaded</th>
              <th>Error</th>
            </tr>
          </thead>
          <tbody>
            {(["gsc", "ga4"] as const).map((source) => {
              const log = status[source];
              return (
                <tr key={source}>
                  <td className="font-medium">
                    {source === "gsc" ? "Search Console" : "Google Analytics 4"}
                  </td>
                  <td>
                    <div className="flex flex-wrap items-center gap-2">
                      {formatDate(log?.last_loaded_date)}
                      {isStale(log?.last_loaded_date) && (
                        <span className="badge badge-warning">Stale</span>
                      )}
                    </div>
                  </td>
                  <td className="whitespace-nowrap">
                    {formatTime(log?.last_run_at)}
                  </td>
                  <td>
                    <SourceBadge log={log} />
                  </td>
                  <td className="numeric">{formatNumber(log?.rows_loaded)}</td>
                  <td>
                    {log?.error ? (
                      <details className="min-w-[140px] max-w-sm">
                        <summary className="cursor-pointer text-bad">
                          View error
                        </summary>
                        <p className="mt-2 whitespace-pre-wrap break-words text-xs text-bad">
                          {log.error}
                        </p>
                      </details>
                    ) : (
                      "—"
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
