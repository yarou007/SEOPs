import { Minus, TrendingDown, TrendingUp } from "lucide-react";
import { headline } from "@/lib/explain";
import { formatDate } from "@/lib/format";
import type { Summary, WeeklyReport } from "@/lib/types";

const TONE = {
  good: {
    Icon: TrendingUp,
    className: "bg-good-soft text-good",
    word: "Good news",
  },
  bad: {
    Icon: TrendingDown,
    className: "bg-bad-soft text-bad",
    word: "Needs attention",
  },
  neutral: {
    Icon: Minus,
    className: "bg-surface-muted text-muted",
    word: "Summary",
  },
};

/** The one sentence a client should read first. */
export function Headline({
  summary,
  report,
}: {
  summary: Summary;
  report: WeeklyReport | null;
}) {
  const { text, tone } = headline(summary, report);
  const { Icon, className, word } = TONE[tone];
  return (
    <section aria-label="Summary" className="flex items-start gap-4 py-2">
      <span
        className={`mt-1 flex size-10 shrink-0 items-center justify-center rounded-full ${className}`}
      >
        <Icon size={20} aria-hidden />
        <span className="sr-only">{word}</span>
      </span>
      <div className="min-w-0">
        <p className="max-w-[40ch] text-[1.45rem] font-semibold leading-snug tracking-[-0.015em] sm:text-[1.85rem]">
          {text}
        </p>
        <p className="mt-2 text-sm text-muted">
          {formatDate(summary.current_window.start)} –{" "}
          {formatDate(summary.current_window.end)}, compared with{" "}
          {formatDate(summary.previous_window.start)} –{" "}
          {formatDate(summary.previous_window.end)}.
        </p>
      </div>
    </section>
  );
}
