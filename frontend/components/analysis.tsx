"use client";

import { Fragment } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";
import {
  axisDefinitions,
  axisFinding,
  deviceBars,
  funnelBars,
  heatmapValue,
  indexSlices,
  positionBand,
  scatterPoints,
  statusDetails,
} from "@/lib/analysis";
import type {
  AxisData,
  AxisKey,
  AxisResponse,
  AxisStatus,
  DataRow,
} from "@/lib/analysis";
import type { Result } from "@/lib/types";
import { AxisUpload } from "./axis-upload";

const colors = {
  accent: "var(--chart-clicks)",
  secondary: "var(--chart-impressions)",
  traffic: "var(--chart-sessions)",
  bad: "var(--bad)",
  muted: "var(--muted)",
};
const tooltipStyle = {
  background: "var(--surface)",
  border: "1px solid var(--border)",
  color: "var(--foreground)",
  borderRadius: 6,
};
const tick = { fill: "var(--muted)", fontSize: 11 };
const bands: Record<string, string> = {
  "1–3": "var(--good)",
  "4–10": colors.traffic,
  "11–20": "var(--warning)",
  "21+": colors.bad,
  Unknown: colors.muted,
};
type Column = readonly [string, string, ("percent" | "number" | "provider")?];
const metrics: Column[] = [
  ["clicks", "Clicks", "number"],
  ["impressions", "Impressions", "number"],
  ["ctr", "CTR", "percent"],
  ["avg_position", "Position", "number"],
];
function formatted(
  value: DataRow[string] | undefined,
  format?: Column[2],
): string {
  if (format === "provider") return "Needs keyword provider";
  if (value == null) return "—";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number")
    return format === "percent"
      ? `${(value * 100).toLocaleString("en-US", { maximumFractionDigits: 2 })}%`
      : value.toLocaleString("en-US", { maximumFractionDigits: 2 });
  return value;
}
export function AxisStatusBadge({
  status,
  reason,
}: {
  status: AxisStatus;
  reason: string | null;
}) {
  const badge = statusDetails(status, reason);
  return (
    <span
      className={`badge ${badge.className}`}
      title={badge.description}
      tabIndex={0}
      aria-label={`${badge.label}: ${badge.description}`}
    >
      {badge.label}
    </span>
  );
}
function Table({
  label,
  rows,
  columns,
}: {
  label: string;
  rows: DataRow[];
  columns: Column[];
}) {
  return (
    <div
      className="table-wrap axis-table"
      tabIndex={0}
      role="region"
      aria-label={`${label} scrollable table`}
    >
      <table aria-label={label}>
        <caption className="sr-only">{label}</caption>
        <thead>
          <tr>
            {columns.map(([key, title]) => (
              <th key={key} scope="col">
                {title}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              {columns.map(([key, , format]) => (
                <td
                  key={key}
                  className={
                    format === "number" || format === "percent" ? "numeric" : ""
                  }
                >
                  {formatted(row[key], format)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
function Empty({ children }: { children: React.ReactNode }) {
  return (
    <p className="axis-empty" data-testid="axis-empty">
      {children}
    </p>
  );
}
function Chart({
  name,
  children,
}: {
  name: string;
  children: React.ReactNode;
}) {
  return (
    <figure
      aria-label={name}
      role="img"
      className="axis-chart"
      data-testid="axis-chart"
    >
      <div aria-hidden="true" className="axis-chart-inner">
        {children}
      </div>
      <figcaption className="sr-only">
        {name}. The same data is provided in the following table.
      </figcaption>
    </figure>
  );
}
function ScatterView({
  rows,
  mode,
}: {
  rows: DataRow[];
  mode: "clicks" | "position";
}) {
  const points = scatterPoints(rows, mode);
  if (!points.length)
    return (
      <Empty>
        Collect GSC rows with impressions, clicks and position for this range.
      </Empty>
    );
  const groups =
    mode === "clicks"
      ? [
          {
            name: "Other rows",
            points: points.filter((row) => !row.highlighted),
            color: colors.accent,
          },
          {
            name: "100+ impressions, zero clicks",
            points: points.filter((row) => row.highlighted),
            color: colors.bad,
          },
        ]
      : [
          {
            name: "Opportunity 100+",
            points: points.filter((row) => row.opportunityBand === "high"),
            color: colors.traffic,
          },
          {
            name: "Opportunity below 100",
            points: points.filter((row) => row.opportunityBand === "low"),
            color: colors.secondary,
          },
          {
            name: "Outside positions 4–20",
            points: points.filter((row) => row.opportunityBand === "unknown"),
            color: colors.muted,
          },
        ];
  return (
    <Chart
      name={
        mode === "clicks"
          ? "Page impressions versus clicks; point size shows average position"
          : "Query impressions versus average position; color shows opportunity"
      }
    >
      <ResponsiveContainer
        width="100%"
        height="100%"
        minWidth={0}
        initialDimension={{ width: 600, height: 300 }}
      >
        <ScatterChart
          margin={{ top: 15, right: 16, bottom: 30, left: 0 }}
          accessibilityLayer={false}
        >
          <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
          <XAxis
            type="number"
            dataKey="x"
            name="Impressions"
            tick={tick}
            label={{
              value: "Impressions",
              position: "insideBottom",
              offset: -15,
              fill: "var(--muted)",
            }}
          />
          <YAxis
            type="number"
            dataKey="y"
            name={mode === "clicks" ? "Clicks" : "Position"}
            width={45}
            tick={tick}
            reversed={mode === "position"}
          />
          {mode === "clicks" && (
            <ZAxis
              type="number"
              dataKey="size"
              range={[45, 300]}
              name="Position"
            />
          )}
          <Tooltip
            contentStyle={tooltipStyle}
            content={({ active, payload }) =>
              active && payload?.length ? (
                <div className="axis-tooltip">
                  <strong>{payload[0].payload.label}</strong>
                  <p>Impressions: {payload[0].payload.x}</p>
                  <p>
                    {mode === "clicks" ? "Clicks" : "Position"}:{" "}
                    {payload[0].payload.y}
                  </p>
                  <p>Position: {payload[0].payload.size}</p>
                </div>
              ) : null
            }
          />
          <Legend verticalAlign="top" wrapperStyle={{ fontSize: 11 }} />
          {groups
            .filter((group) => group.points.length)
            .map((group) => (
              <Scatter
                key={group.name}
                name={group.name}
                data={group.points}
                fill={group.color}
                isAnimationActive={false}
              />
            ))}
        </ScatterChart>
      </ResponsiveContainer>
    </Chart>
  );
}
function Bars({
  rows,
  category,
  series,
  horizontal = false,
  band = false,
  label,
}: {
  rows: DataRow[];
  category: string;
  series: readonly [string, string, string][];
  horizontal?: boolean;
  band?: boolean;
  label: string;
}) {
  if (!rows.length)
    return (
      <Empty>
        No values are available for this chart. Complete the source setup below.
      </Empty>
    );
  const dualAxes = series.some(([key]) => key === "ctr_percent");
  return (
    <Chart name={label}>
      <ResponsiveContainer
        width="100%"
        height="100%"
        minWidth={0}
        initialDimension={{ width: 600, height: 300 }}
      >
        <BarChart
          data={rows}
          layout={horizontal ? "vertical" : "horizontal"}
          margin={{ top: 15, right: 16, bottom: 10, left: 0 }}
          accessibilityLayer={false}
        >
          <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
          <XAxis
            dataKey={horizontal ? undefined : category}
            type={horizontal ? "number" : "category"}
            tick={tick}
          />
          <YAxis
            dataKey={horizontal ? category : undefined}
            type={horizontal ? "category" : "number"}
            width={horizontal ? 105 : 45}
            tick={tick}
          />
          {dualAxes && (
            <YAxis
              yAxisId="position"
              orientation="right"
              width={40}
              tick={tick}
            />
          )}
          <Tooltip contentStyle={tooltipStyle} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          {series.map(([key, name, color], i) => (
            <Bar
              key={key}
              dataKey={key}
              name={name}
              fill={color}
              yAxisId={dualAxes && key === "position" ? "position" : 0}
              isAnimationActive={false}
              radius={[3, 3, 0, 0]}
            >
              {band &&
                i === 0 &&
                rows.map((row, index) => (
                  <Cell
                    key={index}
                    fill={bands[positionBand(row.avg_position)]}
                  />
                ))}
            </Bar>
          ))}
        </BarChart>
      </ResponsiveContainer>
    </Chart>
  );
}
function AxisBody({ axis, data }: { axis: AxisKey; data: AxisData }) {
  if (axis === "impressions-clicks")
    return (
      <>
        <p className="text-sm text-muted">
          Pages · horizontal axis: impressions · vertical axis: clicks · size:
          average position. Red marks 100+ impressions with no clicks.
        </p>
        <ScatterView rows={data.pages ?? []} mode="clicks" />
        {!!data.pages?.length && (
          <Table
            label="Page impressions and clicks"
            rows={data.pages}
            columns={[
              ["page", "Page"],
              ...metrics,
              ["high_impressions_zero_clicks", "100+ impressions, zero clicks"],
            ]}
          />
        )}
        <h4 className="font-semibold">Search terms · partial</h4>
        {data.queries?.length ? (
          <>
            <ScatterView rows={data.queries} mode="clicks" />
            <Table
              label="Query impressions and clicks"
              rows={data.queries}
              columns={[
                ["query", "Query"],
                ...metrics,
                [
                  "high_impressions_zero_clicks",
                  "100+ impressions, zero clicks",
                ],
              ]}
            />
          </>
        ) : (
          <Empty>
            Sync query detail for this range. Google still omits hidden queries.
          </Empty>
        )}
        <p className="text-sm text-muted">{data.explanation}</p>
      </>
    );
  if (axis === "funnel")
    return (
      <>
        <Bars
          rows={funnelBars(data.steps ?? [])}
          category="name"
          series={[["value", "Recorded count", colors.accent]]}
          horizontal
          label="Impressions, clicks, visits and recorded call clicks"
        />
        <Table
          label="Funnel steps and interstep rates"
          rows={(data.steps ?? []).map((row) => ({
            ...row,
            tracking:
              row.value == null
                ? row.name === "Call clicks"
                  ? "Not tracked yet"
                  : "No stored data"
                : "Recorded",
          }))}
          columns={[
            ["name", "Step"],
            ["value", "Count", "number"],
            ["rate_from_previous", "Rate from previous", "percent"],
            ["tracking", "Tracking"],
          ]}
        />
        {data.steps?.some(
          (row) => row.name === "Call clicks" && row.value == null,
        ) && (
          <Empty>
            Call clicks: Not tracked yet. Confirm an existing GA4 call event
            with your administrator.
          </Empty>
        )}
        <p className="text-sm text-muted">{data.note}</p>
      </>
    );
  if (axis === "devices")
    return (
      <>
        <p className="text-sm text-muted">
          CTR (%) uses the left axis; average position uses the right axis. A
          lower position is better.
        </p>
        <Bars
          rows={deviceBars(data.devices ?? [])}
          category="name"
          series={[
            ["ctr_percent", "CTR (%)", colors.accent],
            ["position", "Average position", colors.secondary],
          ]}
          label="GSC CTR percent and average position by device"
        />
        {!!data.devices?.length && (
          <Table
            label="Device metrics"
            rows={data.devices}
            columns={[["device", "Device"], ...metrics]}
          />
        )}
        <h4 className="font-semibold">Operating systems · site-level</h4>
        <Bars
          rows={data.operating_systems ?? []}
          category="os"
          series={[["sessions", "Sessions", colors.traffic]]}
          label="Site-level GA4 sessions by operating system"
        />
        {!!data.operating_systems?.length && (
          <Table
            label="Site-level operating system traffic"
            rows={data.operating_systems}
            columns={[
              ["os", "OS"],
              ["sessions", "Sessions", "number"],
              ["conversions", "Conversions", "number"],
            ]}
          />
        )}
      </>
    );
  if (axis === "geography")
    return (
      <>
        <Bars
          rows={data.zones ?? []}
          category="zone"
          series={[["avg_position", "Average position", colors.accent]]}
          horizontal
          band
          label="Average position by matching service zone"
        />
        {!!data.zones?.length && (
          <>
            <p className="text-sm text-muted">
              Position bands: 1–3 · 4–10 · 11–20 · 21+
            </p>
            <Table
              label="Service-zone visibility"
              rows={data.zones.map((row) => ({
                ...row,
                band: positionBand(row.avg_position),
              }))}
              columns={[
                ["zone", "Zone"],
                ...metrics,
                ["band", "Position band"],
              ]}
            />
          </>
        )}
      </>
    );
  if (axis === "sitemaps") {
    const slices = indexSlices(data);
    return (
      <>
        <p className="text-sm">
          Submitted (API count):{" "}
          <strong>
            {data.submitted?.toLocaleString("en-US") ?? "Unknown"}
          </strong>{" "}
          · Inspected URLs: <strong>{data.inspected ?? 0}</strong>
        </p>
        {slices.length ? (
          <Chart name="Indexed versus not indexed and unknown in the inspected sample">
            <ResponsiveContainer
              width="100%"
              height="100%"
              minWidth={0}
              initialDimension={{ width: 600, height: 300 }}
            >
              <PieChart accessibilityLayer={false}>
                <Pie
                  data={slices}
                  dataKey="value"
                  nameKey="name"
                  innerRadius={60}
                  outerRadius={95}
                  isAnimationActive={false}
                >
                  {slices.map((row) => (
                    <Cell key={row.name} fill={row.fill} />
                  ))}
                </Pie>
                <Tooltip contentStyle={tooltipStyle} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
              </PieChart>
            </ResponsiveContainer>
          </Chart>
        ) : (
          <Empty>
            Collect sitemap metadata, then inspect a sample of submitted page
            URLs to show indexing status.
          </Empty>
        )}
        {!!slices.length && (
          <Table
            label="Inspection verdict counts"
            rows={slices.map(({ name, value }) => ({ name, value }))}
            columns={[
              ["name", "Verdict"],
              ["value", "URLs", "number"],
            ]}
          />
        )}
        {data.note && <p className="text-sm text-muted">{data.note}</p>}
        {!!data.sitemaps?.length && (
          <Table
            label="Submitted sitemaps"
            rows={data.sitemaps}
            columns={[
              ["url", "Sitemap"],
              ["last_submitted", "Last submitted"],
              ["last_downloaded", "Last downloaded"],
            ]}
          />
        )}
        {!!data.urls?.length && (
          <Table
            label="Inspected URL verdicts and indexing reasons"
            rows={data.urls}
            columns={[
              ["url", "URL"],
              ["verdict", "Verdict"],
              ["reason", "Google indexing reason"],
              ["inspected_at", "Inspected at"],
            ]}
          />
        )}
      </>
    );
  }
  if (axis === "internal-links")
    return (
      <>
        {data.pages_count ? (
          <>
            <p>
              {data.orphans?.length ?? 0} orphan candidates ·{" "}
              {data.broken_links?.length ?? 0} broken targets ·{" "}
              {data.pages_count} crawled pages
            </p>
            <Bars
              rows={data.inbound_distribution ?? []}
              category="inbound_links"
              series={[["pages", "Pages", colors.accent]]}
              label="Crawled pages by inbound internal link count"
            />
            <Table
              label="Inbound link distribution"
              rows={data.inbound_distribution ?? []}
              columns={[
                ["inbound_links", "Inbound links", "number"],
                ["pages", "Pages", "number"],
              ]}
            />
            {data.orphans?.length ? (
              <Table
                label="Orphan candidates"
                rows={data.orphans}
                columns={[
                  ["url", "Page"],
                  ["inbound_links", "Inbound links", "number"],
                ]}
              />
            ) : (
              <p>No orphan candidates in this export.</p>
            )}
            {data.broken_links?.length ? (
              <Table
                label="Broken crawl targets"
                rows={data.broken_links}
                columns={[
                  ["url", "Target"],
                  ["http_status", "HTTP status", "number"],
                ]}
              />
            ) : (
              <p>No broken targets in this export.</p>
            )}
            <p className="text-sm text-muted">{data.note}</p>
          </>
        ) : (
          <Empty>
            Upload the latest Ahrefs Site Audit CSV with URL, inbound-link
            counts and HTTP status. Missing exports do not imply a healthy link
            structure.
          </Empty>
        )}
      </>
    );
  if (axis === "site-links") {
    const sites = data.sites ?? [],
      known = (data.matrix ?? []).some((row) => typeof row.links === "number");
    return (
      <>
        {known ? (
          <>
            <p className="text-sm text-muted">
              Rows link to columns. — means the target website has no export.
              Counts represent distinct source/target URL pairs.
            </p>
            <div
              className="axis-heatmap-scroll"
              tabIndex={0}
              role="region"
              aria-label="Portfolio link heatmap"
              data-testid="axis-chart"
            >
              <div
                className="axis-heatmap"
                style={{
                  gridTemplateColumns: `130px repeat(${sites.length}, minmax(100px, 1fr))`,
                }}
              >
                <span>From ↓ / To →</span>
                {sites.map((site) => (
                  <strong key={String(site.slug)}>{site.domain}</strong>
                ))}
                {sites.map((source) => (
                  <Fragment key={String(source.slug)}>
                    <strong>{source.domain}</strong>
                    {sites.map((target) => {
                      const value = heatmapValue(
                        data.matrix ?? [],
                        String(source.domain),
                        String(target.domain),
                      );
                      return (
                        <span
                          key={String(target.slug)}
                          className={`heat-cell ${value == null ? "heat-unknown" : value > 0 ? "heat-positive" : ""}`}
                          title={`${source.domain} → ${target.domain}: ${value ?? "unknown"}`}
                          style={
                            value
                              ? {
                                  background: `color-mix(in srgb, var(--chart-sessions) ${Math.min(85, 20 + Math.log2(value + 1) * 12)}%, var(--surface))`,
                                }
                              : undefined
                          }
                        >
                          {value ?? "—"}
                        </span>
                      );
                    })}
                  </Fragment>
                ))}
              </div>
            </div>
            <Table
              label="Portfolio links by source and target"
              rows={data.matrix ?? []}
              columns={[
                ["source", "From"],
                ["target", "To"],
                ["links", "Links", "number"],
              ]}
            />
          </>
        ) : (
          <Empty>
            Upload backlinks CSVs for the five real websites to build the link
            matrix. An absent export is unknown, not zero links.
          </Empty>
        )}
      </>
    );
  }
  return (
    <>
      <ScatterView rows={data.queries ?? []} mode="position" />
      {data.queries?.length ? (
        <Table
          label="Search opportunities and keyword-provider gaps"
          rows={data.queries}
          columns={[
            ["query", "Query"],
            ...metrics,
            ["opportunity", "Opportunity", "number"],
            ["volume", "Volume", "provider"],
            ["difficulty", "Difficulty", "provider"],
          ]}
        />
      ) : (
        <Empty>
          Sync visible GSC queries for this range. Volume and difficulty need a
          keyword provider.
        </Empty>
      )}
      <p className="text-sm text-muted">
        Opportunity = impressions × (1 − CTR), only for positions 4–20. Color:
        100+ / below 100 / outside range. Volume and difficulty: Needs keyword
        provider.
      </p>
    </>
  );
}
export function Analysis({
  slug,
  axes,
  canManage,
}: {
  slug: string;
  axes: Record<AxisKey, Result<AxisResponse>>;
  canManage: boolean;
}) {
  return (
    <div className="analysis space-y-6">
      <header>
        <h2 className="text-xl font-semibold">Analysis</h2>
        <p className="mt-1 text-muted">
          Eight questions, with the evidence and its limits shown together.
        </p>
      </header>
      <nav aria-label="Analysis axes" className="axis-index">
        {axisDefinitions.map(([key, title], index) => (
          <a key={key} href={`#axis-${key}`}>
            <span>{String(index + 1).padStart(2, "0")}</span>
            {title}
          </a>
        ))}
      </nav>
      {axisDefinitions.map(([key, title, question], index) => {
        const result = axes[key],
          response = result.data;
        return (
          <section
            className="panel axis-section"
            id={`axis-${key}`}
            key={key}
            aria-labelledby={`title-${key}`}
            data-testid={`axis-${key}`}
          >
            <div className="axis-heading">
              <div>
                <p className="axis-number">
                  AXIS {String(index + 1).padStart(2, "0")}
                </p>
                <h3 id={`title-${key}`}>{title}</h3>
              </div>
              <AxisStatusBadge
                status={response?.status ?? "needs_setup"}
                reason={response?.reason ?? result.error}
              />
            </div>
            <p className="text-muted">{question}</p>
            {response ? (
              <>
                <p className="axis-finding">
                  {axisFinding(key, response.data)}
                </p>
                <AxisBody axis={key} data={response.data} />
                {response.reason && (
                  <p className="axis-reason">{response.reason}</p>
                )}
                {response.data.scope && (
                  <p className="text-xs text-muted">{response.data.scope}</p>
                )}
                {response.data.collected_at && (
                  <p className="text-xs text-muted">
                    Evidence collected: {response.data.collected_at}
                  </p>
                )}
              </>
            ) : (
              <p role="alert" className="axis-empty">
                {result.error ??
                  "Could not load this axis. Reload to try again."}
              </p>
            )}
            {canManage &&
              (key === "internal-links" || key === "site-links") && (
                <AxisUpload
                  slug={slug}
                  kind={
                    key === "internal-links" ? "internal-links" : "backlinks"
                  }
                />
              )}
          </section>
        );
      })}
    </div>
  );
}
