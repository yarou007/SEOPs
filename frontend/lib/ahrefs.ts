// Ahrefs Web Analytics "all stats" export: read files in the browser before uploading.
// The header row identifies each report, mirroring the backend's REPORTS table exactly.
import type { WebAnalyticsReport, WebAnalyticsRow } from "./types";

const SIGNATURES: Record<WebAnalyticsReport, string> = {
  top_pages: "page|visitors|views|bouncerate|timeonpage",
  entry_pages: "entrypage|visitors|entrances|visitduration",
  exit_pages: "page|visitors|exits|exitrate",
  channels: "channel|visitors|bouncerate|visitduration",
  sources: "source|visitors|bouncerate|visitduration",
  devices: "device|visitors|bouncerate|visitduration",
  browsers: "browser|visitors|bouncerate|visitduration",
  os: "os|visitors|bouncerate|visitduration",
  countries: "country|visitors",
  cities: "city|visitors",
  continents: "continent|visitors",
  languages: "language|visitors",
  utm_campaign: "utmcampaign|visitors|bouncerate|visitduration",
  utm_content: "utmcontent|visitors|bouncerate|visitduration",
  utm_medium: "utmmedium|visitors|bouncerate|visitduration",
  utm_source: "utmsource|visitors|bouncerate|visitduration",
  utm_term: "utmterm|visitors|bouncerate|visitduration",
  events: "event|visitors|count|conversionrate",
  outbound_links: "eventpropertyhref|count|visitors",
};

export const REPORT_LABELS: Record<WebAnalyticsReport, string> = {
  top_pages: "Top pages",
  entry_pages: "Entry pages",
  exit_pages: "Exit pages",
  channels: "Channels",
  sources: "Sources",
  devices: "Devices",
  browsers: "Browsers",
  os: "Operating systems",
  countries: "Countries",
  cities: "Cities",
  continents: "Continents",
  languages: "Languages",
  utm_campaign: "UTM campaigns",
  utm_content: "UTM content",
  utm_medium: "UTM medium",
  utm_source: "UTM sources",
  utm_term: "UTM terms",
  events: "Tracked events",
  outbound_links: "Outbound link clicks",
};

export function decodeExport(bytes: Uint8Array): string {
  const encoding =
    bytes[0] === 0xff && bytes[1] === 0xfe
      ? "utf-16le"
      : bytes[0] === 0xfe && bytes[1] === 0xff
        ? "utf-16be"
        : "utf-8";
  return new TextDecoder(encoding, { fatal: true })
    .decode(bytes)
    .replace(/^\uFEFF/, "");
}

const normalise = (cell: string) =>
  cell
    .replace(/^"|"$/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]/g, "");

export function recogniseReport(
  text: string,
): WebAnalyticsReport | "empty" | "unknown" {
  const lines = text.split(/\r?\n/).filter((line) => line.trim());
  if (!lines.length) return "empty";
  const header = lines[0].split("\t").map(normalise).join("|");
  const report = (Object.keys(SIGNATURES) as WebAnalyticsReport[]).find(
    (key) => SIGNATURES[key] === header,
  );
  if (!report) return "unknown";
  return lines.length > 1 ? report : "empty";
}

const iso = (date: Date) => date.toISOString().slice(0, 10);

/** Ahrefs exports carry no dates; default to its "Last 30 days", which includes the export day. */
export function periodFromFolder(
  name: string,
  today: Date = new Date(),
): { start: string; end: string } {
  const match = /_(\d{4}-\d{2}-\d{2})_\d{2}-\d{2}-\d{2}/.exec(name);
  const end = match
    ? new Date(`${match[1]}T00:00:00Z`)
    : new Date(iso(today) + "T00:00:00Z");
  const start = new Date(end.valueOf() - 29 * 86_400_000);
  return { start: iso(start), end: iso(end) };
}

/** Bounce rate across channels, weighted by visitors; null without data. */
export function weightedBounce(
  rows: WebAnalyticsRow[] | undefined,
): number | null {
  const visitors = (rows ?? []).reduce(
    (sum, row) => sum + (row.visitors ?? 0),
    0,
  );
  if (!visitors) return null;
  return (
    (rows ?? []).reduce(
      (sum, row) => sum + (row.visitors ?? 0) * (row.bounce_rate ?? 0),
      0,
    ) / visitors
  );
}

/** The page path, plus the host when it is not the website's own (for example www.). */
export function pageLabel(url: string, domain: string): string {
  try {
    const parsed = new URL(url);
    if (!/^https?:$/.test(parsed.protocol)) return url;
    return parsed.hostname === domain
      ? parsed.pathname
      : `${parsed.hostname}${parsed.pathname}`;
  } catch {
    return url;
  }
}
