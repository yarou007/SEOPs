import { StatCard } from "@/components/ui/stat-card";
import { GLOSSARY, type GlossaryKey } from "@/lib/explain";
import {
  formatNumber,
  formatPercent,
  formatPosition,
  percentChange,
} from "@/lib/format";
import type { Summary } from "@/lib/types";

type Item = {
  key: GlossaryKey;
  value: number | null | undefined;
  before: number | null | undefined;
  format: (value: number | null | undefined) => string;
};

function Cards({
  items,
  size,
  comparison,
}: {
  items: Item[];
  size: "large" | "small";
  comparison: string;
}) {
  return items.map((item) => {
    const entry = GLOSSARY[item.key];
    const change = percentChange(item.value, item.before);
    return (
      <StatCard
        key={item.key}
        label={entry.label}
        technical={entry.technical}
        help={entry.help}
        value={item.format(item.value)}
        change={change === null ? null : change * 100}
        higherIsBetter={entry.higherIsBetter}
        comparison={comparison}
        size={size}
      />
    );
  });
}

export function Kpis({ summary }: { summary: Summary }) {
  const { current, previous } = summary;
  const comparison = "vs previous period";
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-1 gap-3 min-[420px]:grid-cols-2 xl:grid-cols-4">
        <Cards
          size="large"
          comparison={comparison}
          items={[
            {
              key: "clicks",
              value: current.gsc?.clicks,
              before: previous.gsc?.clicks,
              format: formatNumber,
            },
            {
              key: "impressions",
              value: current.gsc?.impressions,
              before: previous.gsc?.impressions,
              format: formatNumber,
            },
            {
              key: "ctr",
              value: current.gsc?.ctr,
              before: previous.gsc?.ctr,
              format: formatPercent,
            },
            {
              key: "position",
              value: current.gsc?.avg_position,
              before: previous.gsc?.avg_position,
              format: formatPosition,
            },
          ]}
        />
      </div>
      <div className="grid grid-cols-1 gap-3 min-[420px]:grid-cols-3">
        <Cards
          size="small"
          comparison={comparison}
          items={[
            {
              key: "sessions",
              value: current.ga4?.sessions,
              before: previous.ga4?.sessions,
              format: formatNumber,
            },
            {
              key: "users",
              value: current.ga4?.total_users,
              before: previous.ga4?.total_users,
              format: formatNumber,
            },
            {
              key: "conversions",
              value: current.ga4?.conversions,
              before: previous.ga4?.conversions,
              format: formatNumber,
            },
          ]}
        />
      </div>
    </div>
  );
}
