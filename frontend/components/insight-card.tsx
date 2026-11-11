"use client";

import type { AiInsight, InsightStatus } from "@/lib/types";

const PRIORITY_BADGE: Record<AiInsight["priority"], string> = {
  high: "badge badge-bad",
  medium: "badge badge-warning",
  low: "badge badge-muted",
};
const ACTIONS: [InsightStatus, string][] = [
  ["accepted", "Accept"],
  ["dismissed", "Dismiss"],
  ["done", "Done"],
];

export function InsightCard({
  insight,
  canManage,
  busy,
  onStatus,
}: {
  insight: AiInsight;
  canManage: boolean;
  busy: boolean;
  onStatus: (status: InsightStatus) => void;
}) {
  return (
    <li className="panel space-y-3 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className={PRIORITY_BADGE[insight.priority]}>
          {insight.priority}
        </span>
        <span className="badge badge-muted">{insight.status}</span>
        <span className="text-xs text-muted">
          {insight.source === "weekly"
            ? `Weekly report ${insight.report_date ?? ""}`
            : "From chat"}
        </span>
      </div>
      <h3 className="font-semibold [overflow-wrap:anywhere]">
        {insight.title}
      </h3>
      <p className="text-sm">{insight.problem}</p>
      <p className="text-sm">
        <span className="font-medium">Advice: </span>
        {insight.advice}
      </p>
      <p className="text-xs text-muted [overflow-wrap:anywhere]">
        KPI: {insight.target_kpi}
        {insight.target_url ? ` · Page: ${insight.target_url}` : ""}
      </p>
      <ul className="space-y-1 text-xs">
        {insight.evidence.map((item, index) => (
          <li key={index} className="flex flex-wrap items-center gap-2">
            <span>
              {item.metric}: <strong>{String(item.value)}</strong> (
              {item.period})
            </span>
            {!item.grounded && (
              <span
                className="badge badge-warning"
                title="This figure was not found in the data sent to the AI."
              >
                unverified
              </span>
            )}
          </li>
        ))}
      </ul>
      {canManage && (
        <div className="flex flex-wrap gap-2">
          {ACTIONS.filter(([status]) => status !== insight.status).map(
            ([status, label]) => (
              <button
                key={status}
                type="button"
                className="button"
                disabled={busy}
                onClick={() => onStatus(status)}
              >
                {label}
              </button>
            ),
          )}
        </div>
      )}
    </li>
  );
}
