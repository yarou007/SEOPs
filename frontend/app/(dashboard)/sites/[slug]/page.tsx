import { Analysis } from "@/components/analysis";
import {
  axisDefinitions,
  type AxisKey,
  type AxisResponse,
} from "@/lib/analysis";
import { notFound } from "next/navigation";
import { serverApi, result } from "@/lib/server-api";
import { pageOffset, PAGE_SIZE } from "@/lib/params";
import type {
  DateRange,
  Device,
  Ga4Page,
  GscPage,
  GscQuery,
  Result,
  SourceStatus,
  Summary,
} from "@/lib/types";
import { DateControl } from "@/components/date-control";
import { DeviceFilter } from "@/components/device-filter";
import { DataTable, type Column } from "@/components/data-table";
import { Kpis } from "@/components/kpis";
import { TimeseriesChart } from "@/components/timeseries-chart";
import { StatusTable } from "@/components/status-table";
import { WeeklyReport } from "@/components/weekly-report";
import { Headline } from "@/components/overview/headline";
import { NextActions } from "@/components/overview/next-actions";
import { AiAdvice } from "@/components/overview/ai-advice";
import { InsightsPanel } from "@/components/insights-panel";
import { EmptyState, ErrorState } from "@/components/states";
import { PageHeader } from "@/components/ui/page-header";
import { SECTIONS } from "@/lib/nav";

const gscColumns = [
  { key: "clicks", label: "Clicks", kind: "number", sortable: true },
  { key: "impressions", label: "Impressions", kind: "number", sortable: true },
  { key: "ctr", label: "CTR", kind: "percent", sortable: true },
  { key: "avg_position", label: "Position", kind: "position", sortable: true },
] as const;
const pageColumns: Column<GscPage>[] = [
  { key: "page", label: "Page", kind: "text" },
  ...gscColumns,
];
const queryColumns: Column<GscQuery>[] = [
  { key: "query", label: "Query", kind: "text" },
  ...gscColumns,
  { key: "top_page", label: "Top page", kind: "text" },
];
const trafficColumns: Column<Ga4Page>[] = [
  { key: "page_path", label: "Page path", kind: "text" },
  { key: "sessions", label: "Sessions", kind: "number", sortable: true },
  { key: "total_users", label: "Total users", kind: "number", sortable: true },
  { key: "conversions", label: "Conversions", kind: "number", sortable: true },
  {
    key: "engagement_rate",
    label: "Engagement rate",
    kind: "percent",
    sortable: true,
  },
];
type Query = Record<string, string | string[] | undefined>;
function scalar(value: Query[string]) {
  return Array.isArray(value) ? value[0] : value;
}

async function canManage(slug: string): Promise<boolean> {
  const api = await serverApi();
  return (await result(api.connection(slug))).data?.can_manage ?? false;
}

async function InsightsTab({
  slug,
  range,
}: {
  slug: string;
  range: DateRange;
}) {
  const api = await serverApi();
  const [manage, usage, conversations, insights] = await Promise.all([
    canManage(slug),
    result(api.insightsStatus(slug)),
    result(api.conversations(slug)),
    result(api.insights(slug)),
  ]);
  if (!insights.data || !conversations.data)
    return (
      <ErrorState
        message={
          insights.error ?? conversations.error ?? "Could not load insights."
        }
      />
    );
  return (
    <InsightsPanel
      slug={slug}
      canManage={manage}
      range={range}
      initialUsage={usage.data}
      initialConversations={conversations.data}
      initialInsights={insights.data}
    />
  );
}

async function Overview({ slug, summary }: { slug: string; summary: Summary }) {
  const api = await serverApi();
  const [series, report, manage, insights] = await Promise.all([
    result(api.timeseries(slug, summary.current_window)),
    result(api.report(slug)),
    canManage(slug),
    result(api.insights(slug)),
  ]);
  const weekly = report.data ?? null;
  return (
    <div className="space-y-6">
      <Headline summary={summary} report={weekly} />
      <Kpis summary={summary} />
      {series.data ? (
        <TimeseriesChart rows={series.data} />
      ) : (
        <ErrorState message={series.error ?? "Could not load the chart."} />
      )}
      {!weekly && report.status !== 404 && (
        <ErrorState
          message={report.error ?? "Could not load the weekly report."}
        />
      )}
      <div className="grid min-w-0 gap-6 lg:grid-cols-2">
        <NextActions report={weekly} slug={slug} />
        <AiAdvice
          slug={slug}
          canManage={manage}
          summary={weekly?.ai_summary ?? null}
          hasReport={!!weekly}
          insights={insights.data ?? []}
        />
      </div>
      {weekly ? (
        <WeeklyReport report={weekly} />
      ) : (
        report.status === 404 && (
          <EmptyState>
            No weekly report yet. It is created after the first data sync.
          </EmptyState>
        )
      )}
    </div>
  );
}

async function Search({
  slug,
  summary,
  query,
}: {
  slug: string;
  summary: Summary;
  query: Query;
}) {
  const api = await serverApi();
  const device = scalar(query.device) as Device | undefined;
  const pagesOffset = pageOffset(scalar(query.pagesOffset)),
    queriesOffset = pageOffset(scalar(query.queriesOffset));
  const [pages, queries] = await Promise.all([
    result(
      api.gscPages(
        slug,
        summary.current_window,
        device,
        PAGE_SIZE + 1,
        pagesOffset,
      ),
    ),
    result(
      api.gscQueries(
        slug,
        summary.current_window,
        device,
        PAGE_SIZE + 1,
        queriesOffset,
      ),
    ),
  ]);
  return (
    <div className="space-y-7">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h2 className="text-lg font-semibold">Search performance</h2>
        <DeviceFilter />
      </div>
      {pages.data ? (
        <DataTable
          title="Pages"
          rows={pages.data}
          columns={pageColumns}
          rowKey="page"
          offset={pagesOffset}
          offsetKey="pagesOffset"
          defaultSort="impressions"
        />
      ) : (
        <ErrorState message={pages.error ?? "Could not load pages."} />
      )}
      {queries.data ? (
        <DataTable
          title="Queries"
          rows={queries.data}
          columns={queryColumns}
          rowKey="query"
          offset={queriesOffset}
          offsetKey="queriesOffset"
          defaultSort="impressions"
        />
      ) : (
        <ErrorState message={queries.error ?? "Could not load queries."} />
      )}
      <p className="text-xs text-muted">
        Partial query data: Google hides some queries. Use query-free page
        totals for pages and property totals for KPIs.
      </p>
    </div>
  );
}

async function Traffic({
  slug,
  summary,
  query,
}: {
  slug: string;
  summary: Summary;
  query: Query;
}) {
  const offset = pageOffset(scalar(query.trafficOffset));
  const rows = await result(
    (await serverApi()).ga4Pages(
      slug,
      summary.current_window,
      PAGE_SIZE + 1,
      offset,
    ),
  );
  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-lg font-semibold">Traffic performance</h2>
        <p className="mt-1 text-sm text-muted">
          Google Analytics 4 page metrics. User counts are summed daily/page
          counts.
        </p>
      </div>
      {rows.data ? (
        <DataTable
          title="Traffic pages"
          rows={rows.data}
          columns={trafficColumns}
          rowKey="page_path"
          offset={offset}
          offsetKey="trafficOffset"
          defaultSort="sessions"
        />
      ) : (
        <ErrorState message={rows.error ?? "Could not load traffic pages."} />
      )}
    </div>
  );
}

async function AnalysisTab({
  slug,
  summary,
}: {
  slug: string;
  summary: Summary;
}) {
  const api = await serverApi();
  const [responses, connection] = await Promise.all([
    Promise.all(
      axisDefinitions.map(
        async ([key]) =>
          [
            key,
            await result(api.axis(slug, key, summary.current_window)),
          ] as const,
      ),
    ),
    result(api.connection(slug)),
  ]);
  return (
    <Analysis
      slug={slug}
      axes={
        Object.fromEntries(responses) as Record<AxisKey, Result<AxisResponse>>
      }
      canManage={connection.data?.can_manage ?? false}
    />
  );
}

export default async function SitePage({
  params,
  searchParams,
}: {
  params: Promise<{ slug: string }>;
  searchParams: Promise<Query>;
}) {
  const { slug } = await params;
  const query = await searchParams;
  const api = await serverApi();
  // Verify through the site's access dependency before using any site data.
  const status: Result<SourceStatus> = await result(api.status(slug), true);
  if (!status.data)
    return <ErrorState message={status.error ?? "Could not load this site."} />;
  const [sites, defaults] = await Promise.all([
    result(api.sites()),
    result(api.summary(slug), true),
  ]);
  if (!sites.data || !defaults.data)
    return (
      <ErrorState
        message={sites.error ?? defaults.error ?? "Could not load this site."}
      />
    );
  const site = sites.data.find((site) => site.slug === slug);
  if (!site) notFound();
  const start = scalar(query.start),
    end = scalar(query.end);
  const selected =
    start || end
      ? await result(api.summary(slug, { start, end }), true)
      : defaults;
  const range = selected.data?.current_window ?? {
    start: start ?? defaults.data.current_window.start,
    end: end ?? defaults.data.current_window.end,
  };
  const requested = scalar(query.tab) ?? "overview";
  const tab = SECTIONS.some(
    (item) => item.key === requested && item.key !== "setup",
  )
    ? requested
    : "overview";
  const section = SECTIONS.find((item) => item.key === tab) ?? SECTIONS[0];
  return (
    <div className="min-w-0">
      <PageHeader
        title={tab === "overview" ? site.display_name : section.label}
        description={
          tab === "overview" ? (
            <span className="break-all">{site.domain}</span>
          ) : (
            <>
              {site.display_name}{" "}
              <span className="break-all text-muted">({site.domain})</span>
            </>
          )
        }
      />
      {!["ahrefs", "status"].includes(tab) && (
        <DateControl
          key={`${range.start}:${range.end}`}
          range={range}
          defaultEnd={defaults.data.current_window.end}
        />
      )}
      {!selected.data ? (
        <ErrorState message={selected.error ?? "Could not load this range."} />
      ) : tab === "search" ? (
        <Search slug={slug} summary={selected.data} query={query} />
      ) : tab === "traffic" ? (
        <Traffic slug={slug} summary={selected.data} query={query} />
      ) : tab === "analysis" ? (
        <AnalysisTab slug={slug} summary={selected.data} />
      ) : tab === "insights" ? (
        <InsightsTab slug={slug} range={selected.data.current_window} />
      ) : tab === "ahrefs" ? (
        <section className="panel p-6">
          <h2 className="text-lg font-semibold">Ahrefs</h2>
          <p className="mt-2 text-muted">
            Ahrefs data is entered manually and will be added in a later step.
          </p>
        </section>
      ) : tab === "status" ? (
        <StatusTable status={status.data} />
      ) : (
        <Overview slug={slug} summary={selected.data} />
      )}
    </div>
  );
}
