import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import { InfoTip } from "./info-tip";

/** One number with its plain name, technical name, explanation and change. */
export function StatCard({
  label,
  technical,
  help,
  value,
  change,
  higherIsBetter = true,
  comparison = "vs previous period",
  size = "large",
}: {
  label: string;
  technical?: string;
  help?: string;
  value: string;
  change: number | null;
  higherIsBetter?: boolean;
  comparison?: string;
  size?: "large" | "small";
}) {
  const flat = change === null || Math.abs(change) < 0.005;
  const good = !flat && (higherIsBetter ? change! > 0 : change! < 0);
  const Arrow = flat ? Minus : change! > 0 ? ArrowUpRight : ArrowDownRight;
  return (
    <article className="panel flex min-w-0 flex-col p-4 sm:p-5">
      <h3 className="flex items-center gap-1 text-sm font-medium">
        <span className="min-w-0">{label}</span>
        {help && <InfoTip label={label}>{help}</InfoTip>}
      </h3>
      {technical && <p className="text-xs text-muted">{technical}</p>}
      <p
        className={`figure mt-3 font-semibold ${size === "large" ? "text-3xl" : "text-2xl"}`}
      >
        {value}
      </p>
      <p
        className={`mt-2 flex items-center gap-1 text-xs ${flat ? "text-muted" : good ? "text-good" : "text-bad"}`}
      >
        <Arrow size={14} aria-hidden />
        <span className="figure">
          {change === null
            ? "No earlier period to compare"
            : `${change > 0 ? "+" : ""}${change.toFixed(1)}% ${comparison}`}
        </span>
        {!flat && (
          <span className="sr-only">({good ? "good" : "bad"} change)</span>
        )}
      </p>
    </article>
  );
}
