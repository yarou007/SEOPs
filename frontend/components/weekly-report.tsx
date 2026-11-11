import { Collapsible } from "@/components/ui/collapsible";
import { GLOSSARY } from "@/lib/explain";
import type { WeeklyReport as Report } from "@/lib/types";
import {
  formatDate,
  formatNumber,
  formatPercent,
  formatPosition,
} from "@/lib/format";

/** The full saved weekly report, unchanged in content, folded away below the summary. */
export function WeeklyReport({ report }: { report: Report }) {
  const period = `${formatDate(report.windows.current.start)} – ${formatDate(report.windows.current.end)}`;
  return (
    <section aria-labelledby="weekly-report" className="space-y-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="weekly-report" className="text-lg font-semibold">
          Weekly report details
        </h2>
        <span className="text-xs text-muted">
          {period}, saved {formatDate(report.report_date)}. Not affected by the
          date range above.
        </span>
      </div>
      {report.warnings.length > 0 && (
        <ul className="space-y-1 rounded-md bg-warning-soft p-3 text-sm text-warning">
          {report.warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      )}
      <Collapsible
        title="Pages that need attention"
        summary={`${formatNumber(report.flagged_pages_count)} pages flagged by the weekly checks.`}
      >
        {!report.top_pages.length ? (
          <p className="text-sm text-muted">No flagged pages.</p>
        ) : (
          <ul className="divide-y divide-border">
            {report.top_pages.map((flag) => (
              <li
                key={`${flag.check}:${flag.page}`}
                className="py-3 first:pt-0"
              >
                <p className="break-all text-sm font-medium">{flag.page}</p>
                <p className="mt-1 text-sm">{flag.reason}</p>
                <p className="mt-1 text-xs text-muted">
                  Shown {formatNumber(flag.impressions)} times,{" "}
                  {formatNumber(flag.clicks)} clicks, click rate{" "}
                  {formatPercent(flag.ctr)}, position{" "}
                  {formatPosition(flag.avg_position)}
                </p>
              </li>
            ))}
          </ul>
        )}
      </Collapsible>
      <Collapsible
        title="Phone vs computer"
        summary="Clicks and click rate by device."
      >
        <div className="table-wrap">
          <table aria-label="Weekly device split" className="min-w-[440px]">
            <thead>
              <tr>
                <th>Device</th>
                <th className="numeric">{GLOSSARY.clicks.label}</th>
                <th className="numeric">{GLOSSARY.ctr.label}</th>
                <th className="numeric">{GLOSSARY.position.label}</th>
              </tr>
            </thead>
            <tbody>
              {(["MOBILE", "DESKTOP"] as const).map((device) => (
                <tr key={device}>
                  <td>{device === "MOBILE" ? "Phone" : "Computer"}</td>
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
      </Collapsible>
      <Collapsible
        title="Searches close to page 1"
        summary={`${report.query_candidates.length} searches where a small push could bring more clicks.`}
      >
        {!report.query_candidates.length ? (
          <p className="text-sm text-muted">No searches close to page 1.</p>
        ) : (
          <div className="table-wrap">
            <table
              aria-label="Weekly query candidates"
              className="min-w-[700px]"
            >
              <thead>
                <tr>
                  <th>Search and best page</th>
                  <th className="numeric">{GLOSSARY.impressions.label}</th>
                  <th className="numeric">{GLOSSARY.position.label}</th>
                  <th>Why</th>
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
      </Collapsible>
      <Collapsible
        title="How to read this data"
        summary="Limits of the Google data."
      >
        <ul className="list-disc space-y-1 pl-4 text-sm text-muted">
          {report.data_notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      </Collapsible>
    </section>
  );
}
