import Link from "next/link";
import { Card } from "@/components/ui/card";
import { WeeklyAi } from "@/components/weekly-ai";
import { sortInsights } from "@/lib/insights";
import type { AiInsight } from "@/lib/types";

const PRIORITY = {
  high: "badge badge-bad",
  medium: "badge badge-warning",
  low: "badge badge-muted",
};

export function AiAdvice({
  slug,
  canManage,
  summary,
  hasReport,
  insights,
}: {
  slug: string;
  canManage: boolean;
  summary: string | null;
  hasReport: boolean;
  insights: AiInsight[];
}) {
  const open = sortInsights(
    insights.filter(
      (item) => item.status === "new" || item.status === "accepted",
    ),
  ).slice(0, 3);
  return (
    <Card
      title="AI advice"
      description="Written by AI from your stored data. Check before acting."
    >
      <div className="space-y-5">
        {hasReport ? (
          <WeeklyAi slug={slug} canManage={canManage} summary={summary} />
        ) : (
          <p className="text-sm text-muted">
            The AI analysis appears after the first weekly report.
          </p>
        )}
        {open.length > 0 && (
          <div>
            <h3 className="mb-2 text-sm font-semibold">Top open advice</h3>
            <ul className="space-y-2">
              {open.map((item) => (
                <li key={item.id} className="rounded-md bg-surface-muted p-3">
                  <div className="flex items-start gap-2">
                    <span className={PRIORITY[item.priority]}>
                      <span className="capitalize">{item.priority}</span>
                    </span>
                    <p className="min-w-0 text-sm font-medium [overflow-wrap:anywhere]">
                      {item.title}
                    </p>
                  </div>
                  <p className="mt-1 text-sm text-muted">{item.advice}</p>
                </li>
              ))}
            </ul>
          </div>
        )}
        <Link
          href={`/sites/${encodeURIComponent(slug)}?tab=insights`}
          className="inline-block text-sm text-accent hover:underline"
        >
          Open AI Insights to ask questions
        </Link>
      </div>
    </Card>
  );
}
