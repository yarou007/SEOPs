import Link from "next/link";
import {
  ExternalLink,
  MousePointerClick,
  Smartphone,
  TrendingDown,
  Type,
  Search,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { nextActions } from "@/lib/explain";
import { formatDate } from "@/lib/format";
import type { WeeklyReport } from "@/lib/types";

const ICONS: Record<string, typeof Type> = {
  zero_clicks: Type,
  low_ctr: MousePointerClick,
  clicks_dropping: TrendingDown,
  trend: TrendingDown,
  mobile_gap: Smartphone,
  query: Search,
};

export function NextActions({
  report,
  slug,
}: {
  report: WeeklyReport | null;
  slug: string;
}) {
  const actions = nextActions(report);
  return (
    <Card
      title="What to do next"
      description={
        report
          ? `From the weekly report for ${formatDate(report.windows.current.start)} – ${formatDate(report.windows.current.end)}.`
          : "Appears after the first weekly report."
      }
    >
      {!actions.length ? (
        <p className="text-sm text-muted">
          Nothing urgent in the latest weekly report.
        </p>
      ) : (
        <ul className="divide-y divide-border">
          {actions.map((item) => {
            const Icon = ICONS[item.check] ?? Type;
            return (
              <li
                key={`${item.check}:${item.page}:${item.title}`}
                className="flex gap-3 py-3 first:pt-0 last:pb-0"
              >
                <Icon
                  size={18}
                  aria-hidden
                  className="mt-0.5 shrink-0 text-brass"
                />
                <div className="min-w-0">
                  <p className="font-medium [overflow-wrap:anywhere]">
                    {item.title}
                  </p>
                  <p className="text-sm text-muted">{item.detail}</p>
                  <a
                    href={item.page}
                    target="_blank"
                    rel="noreferrer"
                    className="mt-1 inline-flex items-center gap-1 text-xs text-accent hover:underline"
                  >
                    Open the page <ExternalLink size={12} aria-hidden />
                    <span className="sr-only">(opens in a new tab)</span>
                  </a>
                </div>
              </li>
            );
          })}
        </ul>
      )}
      <Link
        href={`/sites/${encodeURIComponent(slug)}?tab=search`}
        className="mt-4 inline-block text-sm text-accent hover:underline"
      >
        See all pages and searches
      </Link>
    </Card>
  );
}
