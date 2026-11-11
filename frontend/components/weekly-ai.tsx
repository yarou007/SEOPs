"use client";

import { useState } from "react";
import Link from "next/link";
import { Markdown } from "@/components/markdown";
import { ApiError, api } from "@/lib/api";

export function WeeklyAi({
  slug,
  canManage,
  summary,
}: {
  slug: string;
  canManage: boolean;
  summary: string | null;
}) {
  const [text, setText] = useState(summary);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  return (
    <div className="space-y-3">
      <h3 className="font-semibold">AI analysis</h3>
      {text ? (
        <>
          <Markdown>{text}</Markdown>
          <Link
            className="text-sm text-accent hover:underline"
            href={`/sites/${encodeURIComponent(slug)}?tab=insights`}
          >
            See all insights →
          </Link>
        </>
      ) : canManage ? (
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            className="button"
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              setError("");
              try {
                setText((await api.generateWeekly(slug)).ai_summary);
              } catch (caught) {
                setError(
                  caught instanceof ApiError
                    ? caught.message
                    : "Something went wrong. Try again.",
                );
              } finally {
                setBusy(false);
              }
            }}
          >
            {busy ? "Generating… (up to 2 minutes)" : "Generate AI analysis"}
          </button>
          <span className="text-xs text-muted">
            Uses 1–2 of today’s AI requests.
          </span>
        </div>
      ) : (
        <p className="text-sm text-muted">
          No AI analysis for this report yet.
        </p>
      )}
      {error && (
        <p role="alert" className="rounded-md bg-bad-soft p-3 text-sm text-bad">
          {error}
        </p>
      )}
    </div>
  );
}
