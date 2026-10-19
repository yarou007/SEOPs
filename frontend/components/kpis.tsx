import type { Summary } from "@/lib/types";
import {
  formatChange,
  formatNumber,
  formatPercent,
  formatPosition,
  percentChange,
} from "@/lib/format";

export function Kpis({ summary }: { summary: Summary }) {
  const { current, previous } = summary;
  const items = [
    {
      name: "GSC clicks",
      value: current.gsc?.clicks,
      before: previous.gsc?.clicks,
      format: formatNumber,
    },
    {
      name: "GSC impressions",
      value: current.gsc?.impressions,
      before: previous.gsc?.impressions,
      format: formatNumber,
    },
    {
      name: "GSC CTR",
      value: current.gsc?.ctr,
      before: previous.gsc?.ctr,
      format: formatPercent,
    },
    {
      name: "Avg. position",
      value: current.gsc?.avg_position,
      before: previous.gsc?.avg_position,
      format: formatPosition,
      inverse: true,
    },
    {
      name: "GA4 sessions",
      value: current.ga4?.sessions,
      before: previous.ga4?.sessions,
      format: formatNumber,
    },
    {
      name: "GA4 total users",
      value: current.ga4?.total_users,
      before: previous.ga4?.total_users,
      format: formatNumber,
    },
    {
      name: "GA4 conversions",
      value: current.ga4?.conversions,
      before: previous.ga4?.conversions,
      format: formatNumber,
    },
  ];
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7">
      {items.map((item) => {
        const change = percentChange(item.value, item.before);
        const good =
          change !== null && (item.inverse ? change < 0 : change > 0);
        return (
          <article className="panel p-4" key={item.name}>
            <h3 className="text-xs text-muted">{item.name}</h3>
            <p className="mt-2 text-2xl font-semibold tabular-nums">
              {item.format(item.value)}
            </p>
            <p
              className={`mt-2 text-xs tabular-nums ${change == null || change === 0 ? "text-muted" : good ? "text-good" : "text-bad"}`}
            >
              {change === null
                ? "No prior baseline"
                : `${formatChange(change)} vs previous`}
            </p>
          </article>
        );
      })}
    </div>
  );
}
