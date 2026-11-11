"use client";

import { AlertTriangle, Target } from "lucide-react";
import type { AiInsight, InsightStatus } from "@/lib/types";

const PRIORITY: Record<
  AiInsight["priority"],
  { badge: string; stripe: string; label: string }
> = {
  high: {
    badge: "badge badge-bad",
    stripe: "border-l-bad",
    label: "High priority",
  },
  medium: {
    badge: "badge badge-warning",
    stripe: "border-l-warning",
    label: "Medium priority",
  },
  low: {
    badge: "badge badge-muted",
    stripe: "border-l-border",
    label: "Low priority",
  },
};
const STATUS: Record<InsightStatus, string> = {
  new: "New",
  accepted: "Accepted",
  dismissed: "Dismissed",
  done: "Done",
};
const ACTIONS: [InsightStatus, string][] = [
  ["accepted", "Accept"],
  ["done", "Mark done"],
  ["dismissed", "Dismiss"],
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
  const priority = PRIORITY[insight.priority];
  return (
    <li className={`panel space-y-3 border-l-4 p-4 ${priority.stripe}`}>
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className={priority.badge}>{priority.label}</span>
        <span className="badge badge-muted">{STATUS[insight.status]}</span>
        <span className="text-muted">
          {insight.source === "weekly"
            ? `Weekly analysis${insight.report_date ? `, ${insight.report_date}` : ""}`
            : "From a chat answer"}
        </span>
      </div>
      <h3 className="font-semibold [overflow-wrap:anywhere]">
        {insight.title}
      </h3>
      <p className="text-sm text-muted">{insight.problem}</p>
      <div className="rounded-md bg-surface-muted p-3 text-sm">
        <p className="font-medium">What to do</p>
        <p className="mt-0.5">{insight.advice}</p>
      </div>
      <p className="flex flex-wrap items-center gap-1 text-xs text-muted [overflow-wrap:anywhere]">
        <Target size={13} aria-hidden /> Watch: {insight.target_kpi}
        {insight.target_url && (
          <>
            {" "}
            on{" "}
            <a
              href={insight.target_url}
              target="_blank"
              rel="noreferrer"
              className="text-accent hover:underline"
            >
              {insight.target_url}
            </a>
          </>
        )}
      </p>
      {insight.evidence.length > 0 && (
        <ul className="flex flex-wrap gap-1.5" aria-label="Evidence">
          {insight.evidence.map((item, index) => (
            <li
              key={index}
              className={`rounded-md border px-2 py-1 text-xs ${item.grounded ? "border-border bg-surface" : "border-warning/40 bg-warning-soft text-warning"}`}
              title={
                item.grounded
                  ? undefined
                  : "This figure was not found in the data sent to the AI."
              }
            >
              {!item.grounded && (
                <AlertTriangle size={12} aria-hidden className="mr-1 inline" />
              )}
              {item.metric}:{" "}
              <strong className="figure">{String(item.value)}</strong>{" "}
              <span className="text-muted">({item.period})</span>
              {!item.grounded && <span> unverified</span>}
            </li>
          ))}
        </ul>
      )}
      {canManage && (
        <div className="flex flex-wrap gap-2">
          {ACTIONS.filter(([status]) => status !== insight.status).map(
            ([status, label]) => (
              <button
                key={status}
                type="button"
                className="button text-xs"
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
