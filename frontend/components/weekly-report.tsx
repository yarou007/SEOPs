import type { WeeklyReport as Report } from "@/lib/types";
import {
  formatDate,
  formatNumber,
  formatPercent,
  formatPosition,
} from "@/lib/format";

export function WeeklyReport({ report }: { report: Report }) {
  return (
    <section className="panel space-y-6 p-4 sm:p-6">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-lg font-semibold">Weekly report</h2>
        <span className="text-xs text-muted">
          Saved {formatDate(report.report_date)}
        </span>
      </div>
      <p className="text-sm text-muted">
        {formatDate(report.windows.current.start)} –{" "}
        {formatDate(report.windows.current.end)}. This saved report is
        independent of the selected date range.
      </p>
      {report.warnings.length > 0 && (
        <ul className="space-y-1 rounded-md bg-warning-soft p-3 text-sm text-warning">
          {report.warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      )}
      <div>
        <h3 className="font-semibold">Flagged pages</h3>
        <p className="mt-1 text-xs text-muted">
          Showing {Math.min(report.top_pages.length, 3)} of{" "}
          {formatNumber(report.flagged_pages_count)} flagged pages.
        </p>
        {!report.top_pages.length ? (
          <p className="mt-3 text-sm text-muted">No flagged pages.</p>
        ) : (
          <ul className="mt-3 divide-y divide-border">
            {report.top_pages.slice(0, 3).map((flag) => (
              <li key={flag.page} className="py-3">
                <p className="break-all text-sm font-medium">{flag.page}</p>
                <p className="mt-1 text-sm">{flag.reason}</p>
                <p className="mt-1 text-xs text-muted">
                  {formatNumber(flag.impressions)} impressions ·{" "}
                  {formatNumber(flag.clicks)} clicks · CTR{" "}
                  {formatPercent(flag.ctr)} · Position{" "}
                  {formatPosition(flag.avg_position)}
                </p>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div>
        <h3 className="mb-3 font-semibold">Device split</h3>
        <div className="table-wrap">
          <table aria-label="Weekly device split" className="min-w-[440px]">
            <thead>
              <tr>
                <th>Device</th>
                <th className="numeric">Clicks</th>
                <th className="numeric">CTR</th>
                <th className="numeric">Position</th>
              </tr>
            </thead>
            <tbody>
              {(["MOBILE", "DESKTOP"] as const).map((device) => (
                <tr key={device}>
                  <td>{device}</td>
                  <td className="numeric">
                    {formatNumber(report.device_split[device]?.clicks)}
                  </td>
                  <td className="numeric">
                    {formatPercent(report.device_split[device]?.ctr)}
                  </td>
                  <td className="numeric">
                    {formatPosition(report.device_split[device]?.avg_position)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      <div>
        <h3 className="mb-3 font-semibold">Query candidates</h3>
        {!report.query_candidates.length ? (
          <p className="text-sm text-muted">No query candidates.</p>
        ) : (
          <div className="table-wrap">
            <table
              aria-label="Weekly query candidates"
              className="min-w-[700px]"
            >
              <thead>
                <tr>
                  <th>Query / top page</th>
                  <th className="numeric">Impressions</th>
                  <th className="numeric">Position</th>
                  <th>Reason</th>
                </tr>
              </thead>
              <tbody>
                {report.query_candidates.map((query) => (
                  <tr key={query.query}>
                    <td className="min-w-[220px] max-w-[360px] break-words">
                      <span className="font-medium">{query.query}</span>
                      <p className="mt-1 break-all text-xs text-muted">
                        {query.top_page}
                      </p>
                    </td>
                    <td className="numeric">
                      {formatNumber(query.impressions)}
                    </td>
                    <td className="numeric">
                      {formatPosition(query.avg_position)}
                    </td>
                    <td className="min-w-[200px]">{query.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      <details className="border-t border-border pt-4 text-xs text-muted">
        <summary className="cursor-pointer font-medium">Data notes</summary>
        <ul className="mt-2 list-disc space-y-1 pl-4">
          {report.data_notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      </details>
    </section>
  );
}
