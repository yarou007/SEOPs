export const axisDefinitions = [
  [
    "impressions-clicks",
    "Impressions vs clicks",
    "Which pages and search terms get seen but earn few clicks?",
  ],
  [
    "funnel",
    "Break points",
    "Where do impressions turn into clicks, visits and call clicks?",
  ],
  [
    "devices",
    "Mobile & iOS",
    "How do device visibility and site-level OS behavior differ?",
  ],
  [
    "geography",
    "Geography / zones",
    "How visible are emergency locksmith searches for each service zone?",
  ],
  [
    "sitemaps",
    "Sitemaps",
    "What was submitted, and what does Google say about the inspected URLs?",
  ],
  [
    "internal-links",
    "Internal links",
    "Which pages may be orphaned, and which crawl targets are broken?",
  ],
  [
    "site-links",
    "Links between our sites",
    "Which portfolio sites link to each other?",
  ],
  [
    "search-requests",
    "Search requests",
    "Which visible searches have the greatest click opportunity?",
  ],
] as const;
export type AxisKey = (typeof axisDefinitions)[number][0];
export type AxisStatus = "ready" | "partial" | "needs_setup";
export type DataRow = Record<string, string | number | boolean | null>;
export interface AxisData {
  pages?: DataRow[];
  queries?: DataRow[];
  steps?: DataRow[];
  devices?: DataRow[];
  operating_systems?: DataRow[];
  zones?: DataRow[];
  sitemaps?: DataRow[];
  urls?: DataRow[];
  orphans?: DataRow[];
  broken_links?: DataRow[];
  inbound_distribution?: DataRow[];
  sites?: DataRow[];
  matrix?: DataRow[];
  submitted?: number | null;
  indexed?: number;
  not_indexed?: number;
  unknown?: number;
  inspected?: number;
  pages_count?: number;
  collected_at?: string | null;
  scope?: string;
  note?: string;
  explanation?: string;
  call_event?: string | null;
}
export interface AxisResponse {
  status: AxisStatus;
  reason: string | null;
  data: AxisData;
}
export function statusDetails(status: AxisStatus, reason?: string | null) {
  const labels = {
    ready: "Ready",
    partial: "Partial",
    needs_setup: "Needs setup",
  };
  const classes = {
    ready: "badge-good",
    partial: "badge-warning",
    needs_setup: "badge-muted",
  };
  return {
    label: labels[status],
    className: classes[status],
    description:
      reason ||
      (status === "ready"
        ? "Required evidence is available."
        : "More evidence is needed."),
  };
}
function number(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}
export function scatterPoints(rows: DataRow[], mode: "clicks" | "position") {
  return rows
    .filter(
      (row) =>
        number(row.impressions) &&
        number(row.clicks) &&
        number(row.avg_position),
    )
    .map((row) => ({
      ...row,
      label: String(row.page ?? row.query ?? ""),
      x: row.impressions as number,
      y: (mode === "clicks" ? row.clicks : row.avg_position) as number,
      size: row.avg_position as number,
      highlighted: row.high_impressions_zero_clicks === true,
      opportunityBand: !number(row.opportunity)
        ? "unknown"
        : row.opportunity >= 100
          ? "high"
          : "low",
    }));
}
export function deviceBars(rows: DataRow[]) {
  return rows.map((row) => ({
    ...row,
    name: String(row.device),
    ctr_percent: number(row.ctr) ? row.ctr * 100 : null,
    position: number(row.avg_position) ? row.avg_position : null,
  }));
}
export function positionBand(value: unknown) {
  return !number(value)
    ? "Unknown"
    : value < 4
      ? "1–3"
      : value < 11
        ? "4–10"
        : value < 21
          ? "11–20"
          : "21+";
}
export function funnelBars(rows: DataRow[]) {
  return rows
    .filter((row) => number(row.value))
    .map((row) => ({ ...row, name: String(row.name) }));
}
export function indexSlices(data: AxisData) {
  return [
    {
      name: "Indexed in sample",
      value: data.indexed ?? 0,
      fill: "var(--good)",
    },
    {
      name: "Not indexed in sample",
      value: data.not_indexed ?? 0,
      fill: "var(--bad)",
    },
    { name: "Unknown verdict", value: data.unknown ?? 0, fill: "var(--muted)" },
  ].filter((row) => row.value > 0);
}
export function heatmapValue(
  matrix: DataRow[],
  source: string,
  target: string,
): number | null {
  const value = matrix.find(
    (row) => row.source === source && row.target === target,
  )?.links;
  return number(value) ? value : null;
}
export function axisFinding(axis: AxisKey, data: AxisData): string {
  if (axis === "impressions-clicks") {
    const pages = data.pages ?? [],
      flagged = pages.filter((row) => row.high_impressions_zero_clicks);
    return pages.length
      ? `${flagged.length} of ${pages.length} displayed pages have at least 100 impressions and no clicks.`
      : "Query-free page totals are needed before page click gaps can be assessed.";
  }
  if (axis === "funnel") {
    const steps = data.steps ?? [],
      calls = steps.find((row) => row.name === "Call clicks");
    return calls?.value == null
      ? "The journey currently ends at visits because call clicks are not tracked yet."
      : `${calls.value} call clicks were recorded for the configured event.`;
  }
  if (axis === "devices") {
    const top = [...(data.devices ?? [])].sort(
      (a, b) => Number(b.impressions) - Number(a.impressions),
    )[0];
    return top
      ? `${top.device} has the most recorded search impressions (${Number(top.impressions).toLocaleString("en-US")}); OS traffic is site-level.`
      : "Device totals and the site-level OS report need to be collected.";
  }
  if (axis === "geography") {
    const top = [...(data.zones ?? [])]
      .filter((row) => number(row.avg_position))
      .sort((a, b) => Number(a.avg_position) - Number(b.avg_position))[0];
    return top
      ? `${top.zone} has the strongest observed average position (${top.avg_position}) among matching zones.`
      : "No matching service-zone queries are available yet.";
  }
  if (axis === "sitemaps")
    return data.inspected
      ? `${data.indexed ?? 0} of ${data.inspected} inspected URLs have an indexed verdict; this is a sample.`
      : "Sitemap metadata alone does not establish which individual pages are indexed.";
  if (axis === "internal-links")
    return data.pages_count
      ? `${data.orphans?.length ?? 0} orphan candidates and ${data.broken_links?.length ?? 0} broken targets appear in the latest crawl.`
      : "A crawl export is needed to assess internal link structure.";
  if (axis === "site-links") {
    const known = (data.matrix ?? []).filter((row) => number(row.links));
    return known.length
      ? `${known.filter((row) => Number(row.links) > 0).length} portfolio connections have links in the available exports; unknown cells stay unknown.`
      : "Backlink exports are needed before portfolio connections can be counted.";
  }
  const top = [...(data.queries ?? [])]
    .filter((row) => number(row.opportunity))
    .sort((a, b) => Number(b.opportunity) - Number(a.opportunity))[0];
  return top
    ? `“${top.query}” has the largest displayed opportunity score (${Number(top.opportunity).toLocaleString("en-US")}).`
    : "No visible query in positions 4–20 has an opportunity score in this range.";
}
