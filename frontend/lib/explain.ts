// Plain-language explanations computed only from stored data. Never invents a cause or a number.
import { formatDate, formatNumber, percentChange } from "./format";
import type { PageFlag, Summary, WeeklyReport } from "./types";

export const GLOSSARY = {
  clicks: {
    label: "Clicks from Google",
    technical: "Search Console clicks",
    help: "How many times someone clicked your website in Google search results.",
    higherIsBetter: true,
  },
  impressions: {
    label: "Times shown on Google",
    technical: "Search Console impressions",
    help: "How many times your website appeared in someone's Google search results, clicked or not.",
    higherIsBetter: true,
  },
  ctr: {
    label: "Click rate",
    technical: "CTR",
    help: "The share of people who clicked after seeing your website on Google. Clicks divided by times shown.",
    higherIsBetter: true,
  },
  position: {
    label: "Average Google position",
    technical: "Average position",
    help: "Where your website usually appears in Google results. 1 is the top; lower is better. Page 1 is roughly positions 1 to 10.",
    higherIsBetter: false,
  },
  sessions: {
    label: "Visits",
    technical: "GA4 sessions",
    help: "Visits to your website counted by Google Analytics, from any source.",
    higherIsBetter: true,
  },
  users: {
    label: "Visitors",
    technical: "GA4 total users",
    help: "People counted by Google Analytics. Summed per day and page, so one person can count more than once.",
    higherIsBetter: true,
  },
  conversions: {
    label: "Conversions",
    technical: "GA4 conversions",
    help: "Actions you marked as valuable in Google Analytics, such as calls or form sends.",
    higherIsBetter: true,
  },
  bounce_rate: {
    label: "Left without acting",
    technical: "Bounce rate",
    help: "The share of visits that left after one page without doing anything else. Lower is usually better.",
    higherIsBetter: false,
  },
  entrances: {
    label: "Arrivals",
    technical: "Entrances",
    help: "How many visits started on this page.",
    higherIsBetter: true,
  },
  exit_rate: {
    label: "Leave rate",
    technical: "Exit rate",
    help: "The share of page views after which the visitor left the website.",
    higherIsBetter: false,
  },
  visitors: {
    label: "Visitors",
    technical: "Ahrefs visitors",
    help: "People counted by Ahrefs Web Analytics. It is a separate tracker, so the count differs from Google Analytics.",
    higherIsBetter: true,
  },
} as const;
export type GlossaryKey = keyof typeof GLOSSARY;

export function pagePath(url: string): string {
  try {
    return new URL(url).pathname || "/";
  } catch {
    return url;
  }
}

function percent(value: number | null | undefined, digits = 1): string {
  return value == null
    ? "—"
    : `${(value * 100).toFixed(digits).replace(/\.0+$/, "")}%`;
}

function days(range: { start: string; end: string }): number {
  return (
    Math.round(
      (Date.parse(`${range.end}T00:00:00Z`) -
        Date.parse(`${range.start}T00:00:00Z`)) /
        86_400_000,
    ) + 1
  );
}

export function headline(
  summary: Summary,
  report: WeeklyReport | null,
): { text: string; tone: "good" | "bad" | "neutral" } {
  const now = summary.current.gsc?.clicks;
  const before = summary.previous.gsc?.clicks;
  if (now == null)
    return {
      text: "No Search Console data for this period yet.",
      tone: "neutral",
    };
  if (before == null || before === 0)
    return {
      text: `${formatNumber(now)} clicks from Google in this period. No earlier period to compare yet.`,
      tone: "neutral",
    };
  const change = percentChange(now, before)!;
  const period = `the previous ${days(summary.current_window)} days`;
  if (Math.abs(change) < 0.005)
    return {
      text: `Clicks from Google stayed the same (${formatNumber(now)}) compared with ${period}.`,
      tone: "neutral",
    };
  const amount = `${Math.abs(change * 100)
    .toFixed(1)
    .replace(/\.0$/, "")}%`;
  let text = `Clicks from Google ${change > 0 ? "rose" : "fell"} ${amount} compared with ${period}.`;
  const drop = report?.top_pages.find((page) =>
    ["clicks_dropping", "trend"].includes(page.check),
  );
  if (change < 0 && drop && report) {
    const window = report.windows.current;
    text += ` The biggest drop is on ${pagePath(drop.page)} (weekly report, ${formatDate(window.start)} – ${formatDate(window.end)}).`;
  }
  return { text, tone: change > 0 ? "good" : "bad" };
}

export interface NextAction {
  page: string;
  title: string;
  detail: string;
  check: string;
}

function action(flag: PageFlag): NextAction | null {
  const path = pagePath(flag.page);
  const base = { page: flag.page, check: flag.check };
  switch (flag.check) {
    case "zero_clicks":
      return {
        ...base,
        title: `Rewrite the title and description of ${path}`,
        detail: `Shown ${formatNumber(flag.impressions)} times on Google with no clicks.`,
      };
    case "low_ctr":
      return {
        ...base,
        title: `Improve the search snippet of ${path}`,
        detail: `Click rate ${percent(flag.ctr)} vs ${percent(flag.median_ctr_for_band)} typical at this position.`,
      };
    case "clicks_dropping":
    case "trend":
      return {
        ...base,
        title: `Check what changed on ${path}`,
        detail:
          flag.drop_percent != null
            ? `Clicks down ${flag.drop_percent}% vs the previous period.`
            : `Clicks are falling week after week.`,
      };
    case "mobile_gap":
      return {
        ...base,
        title: `Fix the mobile page of ${path}`,
        detail: `Mobile click rate ${percent(flag.mobile_ctr)} vs desktop ${percent(flag.desktop_ctr)}.`,
      };
    default:
      return null;
  }
}

export function nextActions(
  report: WeeklyReport | null,
  limit = 5,
): NextAction[] {
  if (!report) return [];
  const actions = report.top_pages
    .map(action)
    .filter((item): item is NextAction => item !== null);
  for (const candidate of report.query_candidates)
    actions.push({
      page: candidate.top_page,
      check: "query",
      title: `Push “${candidate.query}” onto page 1 of Google`,
      detail: `Ranks ${candidate.avg_position?.toFixed(2) ?? "—"} with ${formatNumber(candidate.impressions)} impressions.`,
    });
  return actions.slice(0, limit);
}
