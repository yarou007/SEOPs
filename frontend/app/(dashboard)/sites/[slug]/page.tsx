import Link from "next/link";
import { notFound } from "next/navigation";
import { serverApi, result } from "@/lib/server-api";
import { pageOffset, PAGE_SIZE } from "@/lib/params";
import type {
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
import { EmptyState, ErrorState } from "@/components/states";

const tabs = [
  ["overview", "Overview"],
  ["search", "Search"],
  ["traffic", "Traffic"],
  ["ahrefs", "Ahrefs"],
  ["status", "Data status"],
] as const;
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

async function Overview({ slug, summary }: { slug: string; summary: Summary }) {
  const api = await serverApi();
  const [series, report] = await Promise.all([
    result(api.timeseries(slug, summary.current_window)),
    result(api.report(slug)),
  ]);
  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold">Overview</h2>
      <Kpis summary={summary} />
      {series.data ? (
        <TimeseriesChart rows={series.data} />
      ) : (
        <ErrorState message={series.error ?? "Could not load the chart."} />
      )}
      {report.data ? (
        <WeeklyReport report={report.data} />
      ) : report.status === 404 ? (
        <section className="space-y-3">
          <h2 className="text-lg font-semibold">Weekly report</h2>
          <EmptyState>No weekly report yet.</EmptyState>
        </section>
      ) : (
        <ErrorState
          message={report.error ?? "Could not load the weekly report."}
        />
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
        Google hides some queries. Use page totals as the main figure.
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
  const tab = tabs.some(([key]) => key === scalar(query.tab))
    ? scalar(query.tab)
    : "overview";
  const link = (tab: string) => {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(query)) {
      const item = scalar(value);
      if (
        item &&
        !["pagesOffset", "queriesOffset", "trafficOffset"].includes(key)
      )
        params.set(key, item);
    }
    params.set("tab", tab);
    return `/sites/${encodeURIComponent(slug)}?${params}`;
  };
  return (
    <div className="min-w-0">
      <Link
        className="mb-4 inline-block text-xs text-muted hover:text-accent"
        href="/sites"
      >
        ← All sites
      </Link>
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">
          {site.display_name}
        </h1>
        <p className="mt-1 break-all text-muted">{site.domain}</p>
      </div>
      <nav
        aria-label="Site sections"
        className="mb-6 flex max-w-full gap-5 overflow-x-auto border-b border-border"
      >
        {tabs.map(([key, label]) => (
          <Link
            key={key}
            href={link(key)}
            aria-current={tab === key ? "page" : undefined}
            className={`whitespace-nowrap border-b-2 px-1 pb-3 text-sm font-medium ${tab === key ? "border-accent text-accent" : "border-transparent text-muted hover:text-foreground"}`}
          >
            {label}
          </Link>
        ))}
      </nav>
      <DateControl
        key={`${range.start}:${range.end}`}
        range={range}
        defaultEnd={defaults.data.current_window.end}
      />
      {!selected.data ? (
        <ErrorState message={selected.error ?? "Could not load this range."} />
      ) : tab === "search" ? (
        <Search slug={slug} summary={selected.data} query={query} />
      ) : tab === "traffic" ? (
        <Traffic slug={slug} summary={selected.data} query={query} />
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
