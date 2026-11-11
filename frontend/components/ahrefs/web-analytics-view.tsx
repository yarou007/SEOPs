import { Card } from "@/components/ui/card";
import { Collapsible } from "@/components/ui/collapsible";
import { StatCard } from "@/components/ui/stat-card";
import { EmptyState } from "@/components/states";
import { pageLabel, REPORT_LABELS, weightedBounce } from "@/lib/ahrefs";
import { GLOSSARY } from "@/lib/explain";
import { formatDate, formatNumber, formatTime } from "@/lib/format";
import type {
  AhrefsData,
  WebAnalyticsReport,
  WebAnalyticsRow,
} from "@/lib/types";

type Column = {
  key: keyof WebAnalyticsRow;
  label: string;
  format: "number" | "percent" | "duration";
};
const percent = (value?: number) =>
  value == null ? "—" : `${(value * 100).toFixed(1).replace(/\.0$/, "")}%`;
function duration(value?: number) {
  if (value == null) return "—";
  const seconds = Math.round(value);
  return seconds >= 60
    ? `${Math.floor(seconds / 60)}m ${seconds % 60}s`
    : `${seconds}s`;
}
const show = (value: number | undefined, kind: Column["format"]) =>
  kind === "percent"
    ? percent(value)
    : kind === "duration"
      ? duration(value)
      : formatNumber(value);

const VISITORS: Column = {
  key: "visitors",
  label: "Visitors",
  format: "number",
};
const BOUNCE: Column = {
  key: "bounce_rate",
  label: GLOSSARY.bounce_rate.label,
  format: "percent",
};
const DURATION: Column = {
  key: "visit_duration",
  label: "Visit length",
  format: "duration",
};
const COLUMNS: Partial<Record<WebAnalyticsReport, Column[]>> = {
  top_pages: [
    VISITORS,
    { key: "views", label: "Views", format: "number" },
    BOUNCE,
    { key: "time_on_page", label: "Time on page", format: "duration" },
  ],
  entry_pages: [
    VISITORS,
    { key: "entrances", label: GLOSSARY.entrances.label, format: "number" },
    DURATION,
  ],
  exit_pages: [
    VISITORS,
    { key: "exits", label: "Exits", format: "number" },
    { key: "exit_rate", label: GLOSSARY.exit_rate.label, format: "percent" },
  ],
  channels: [VISITORS, BOUNCE, DURATION],
  sources: [VISITORS, BOUNCE, DURATION],
  devices: [VISITORS, BOUNCE, DURATION],
  countries: [VISITORS],
  cities: [VISITORS],
  events: [
    VISITORS,
    { key: "count", label: "Times", format: "number" },
    { key: "conversion_rate", label: "Share of visitors", format: "percent" },
  ],
  outbound_links: [
    { key: "count", label: "Clicks", format: "number" },
    VISITORS,
  ],
};

function ReportTable({
  report,
  rows,
  domain,
}: {
  report: WebAnalyticsReport;
  rows: WebAnalyticsRow[];
  domain: string;
}) {
  const columns = COLUMNS[report] ?? [VISITORS];
  return (
    <div className="table-wrap">
      <table aria-label={REPORT_LABELS[report]} className="min-w-[480px]">
        <thead>
          <tr>
            <th>
              {report.endsWith("pages")
                ? "Page"
                : report === "outbound_links"
                  ? "Link"
                  : "Name"}
            </th>
            {columns.map((column) => (
              <th key={column.key} className="numeric">
                {column.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => {
            const name = row.page
              ? pageLabel(row.page, domain)
              : (row.href ?? row.name ?? "");
            return (
              <tr key={`${name}:${index}`}>
                <td className="min-w-[200px] max-w-[360px] [overflow-wrap:anywhere]">
                  {row.href?.startsWith("tel:")
                    ? `Phone call (${row.href.slice(4)})`
                    : name}
                </td>
                {columns.map((column) => (
                  <td key={column.key} className="numeric">
                    {show(row[column.key] as number | undefined, column.format)}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function History({ history }: { history: AhrefsData["history"] }) {
  const max = Math.max(...history.map((item) => item.visitors), 1);
  return (
    <Card
      title="Visitors per import"
      description="Each bar is one imported period, oldest first."
    >
      <ul className="space-y-2">
        {history.map((item) => (
          <li
            key={`${item.period_start}:${item.period_end}`}
            className="grid grid-cols-[minmax(0,11rem)_1fr_auto] items-center gap-3 text-sm"
          >
            <span className="text-muted">
              {formatDate(item.period_start)} – {formatDate(item.period_end)}
            </span>
            <span
              className="h-3 overflow-hidden rounded-full bg-surface-muted"
              aria-hidden
            >
              <span
                className="block h-full rounded-full bg-brass"
                style={{ width: `${(item.visitors / max) * 100}%` }}
              />
            </span>
            <span className="figure">
              {formatNumber(item.visitors)} visitors,{" "}
              {formatNumber(item.phone_clicks)} phone clicks
            </span>
          </li>
        ))}
      </ul>
    </Card>
  );
}

const MAIN: WebAnalyticsReport[] = ["top_pages", "channels", "devices"];
const MORE: WebAnalyticsReport[] = [
  "entry_pages",
  "exit_pages",
  "sources",
  "countries",
  "cities",
  "events",
  "outbound_links",
];

export function WebAnalyticsView({
  data,
  domain,
}: {
  data: AhrefsData;
  domain: string;
}) {
  const latest = data.web_analytics;
  if (!latest)
    return (
      <EmptyState>
        No Ahrefs Web Analytics data yet. Import an export above to see
        visitors, pages and phone clicks.
      </EmptyState>
    );
  const previous = data.previous;
  const comparison = previous
    ? `vs ${formatDate(previous.period_start)} – ${formatDate(previous.period_end)}`
    : "";
  const change = (key: "visitors" | "phone_clicks" | "bounce_rate") =>
    data.changes[key]?.change_percent ?? null;
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold">
          Visitors from {formatDate(latest.period_start)} to{" "}
          {formatDate(latest.period_end)}
        </h2>
        <p className="text-sm text-muted">
          Ahrefs Web Analytics, imported {formatTime(latest.imported_at)}. A
          separate tracker, so its numbers differ from Google Analytics.
        </p>
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        <StatCard
          label="Visitors"
          help={GLOSSARY.visitors.help}
          value={formatNumber(latest.totals.visitors)}
          change={change("visitors")}
          comparison={comparison}
        />
        <StatCard
          label="Phone clicks"
          help="Clicks on a phone number link (tel:) on the website. Each one is likely a call."
          value={formatNumber(latest.totals.phone_clicks)}
          change={change("phone_clicks")}
          comparison={comparison}
        />
        <StatCard
          label={GLOSSARY.bounce_rate.label}
          technical={GLOSSARY.bounce_rate.technical}
          help={GLOSSARY.bounce_rate.help}
          value={percent(weightedBounce(latest.reports.channels) ?? undefined)}
          change={change("bounce_rate")}
          higherIsBetter={false}
          comparison={comparison}
        />
      </div>
      {data.history.length > 1 && <History history={data.history} />}
      {MAIN.filter((report) => latest.reports[report]?.length).map((report) => (
        <Card key={report} title={REPORT_LABELS[report]}>
          <ReportTable
            report={report}
            rows={latest.reports[report]!}
            domain={domain}
          />
        </Card>
      ))}
      <div className="space-y-3">
        {MORE.filter((report) => latest.reports[report]?.length).map(
          (report) => (
            <Collapsible
              key={report}
              title={REPORT_LABELS[report]}
              summary={`${latest.reports[report]!.length} ${latest.reports[report]!.length === 1 ? "row" : "rows"}`}
            >
              <ReportTable
                report={report}
                rows={latest.reports[report]!}
                domain={domain}
              />
            </Collapsible>
          ),
        )}
      </div>
    </div>
  );
}
