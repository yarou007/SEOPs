import type { AiInsight, UsageInfo } from "./types";

export const STARTER_QUESTIONS = [
  "Why did clicks change vs last period?",
  "Which pages have the best quick-win potential?",
  "What should we fix first this week?",
];

export function quotaLabel(usage: UsageInfo): string {
  if (!usage.configured) return "AI not configured";
  if (usage.exhausted || usage.remaining <= 0) return "Daily AI limit reached";
  return `${usage.remaining} AI requests left today`;
}

const PRIORITY: Record<AiInsight["priority"], number> = {
  high: 0,
  medium: 1,
  low: 2,
};

export function sortInsights(insights: AiInsight[]): AiInsight[] {
  return [...insights].sort(
    (a, b) =>
      PRIORITY[a.priority] - PRIORITY[b.priority] ||
      b.created_at.localeCompare(a.created_at),
  );
}

export type StatusFilter = "open" | "all" | "done" | "dismissed";
export type PriorityFilter = "all" | AiInsight["priority"];

export function filterInsights(
  insights: AiInsight[],
  status: StatusFilter,
  priority: PriorityFilter,
): AiInsight[] {
  return sortInsights(
    insights.filter(
      (item) =>
        (status === "all" ||
          (status === "open"
            ? item.status === "new" || item.status === "accepted"
            : item.status === status)) &&
        (priority === "all" || item.priority === priority),
    ),
  );
}

/** Share of today's AI requests already used, 0 to 100. */
export function quotaPercent(usage: UsageInfo): number {
  if (usage.exhausted) return 100;
  if (usage.budget <= 0) return 0;
  return Math.min(100, Math.round((usage.used / usage.budget) * 100));
}
