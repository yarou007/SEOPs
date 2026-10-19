"use client";
import { useEffect, useRef, useState } from "react";
import type { DayMetrics } from "@/lib/types";
import { formatDate, formatNumber } from "@/lib/format";
import { EmptyState } from "./states";

const series = [
  { key: "gsc_clicks", label: "GSC clicks", color: "var(--chart-clicks)" },
  {
    key: "gsc_impressions",
    label: "GSC impressions",
    color: "var(--chart-impressions)",
  },
  {
    key: "ga4_sessions",
    label: "GA4 sessions",
    color: "var(--chart-sessions)",
  },
] as const;

export function TimeseriesChart({ rows }: { rows: DayMetrics[] }) {
  const parent = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(900);
  const [index, setIndex] = useState<number | null>(null);
  const values = rows
    .flatMap((row) => series.map((s) => row[s.key]))
    .filter((value): value is number => value !== null);
  const hasData = values.length > 0;
  useEffect(() => {
    if (!parent.current) return;
    const observer = new ResizeObserver((entries) =>
      setWidth(Math.max(280, entries[0].contentRect.width)),
    );
    observer.observe(parent.current);
    return () => observer.disconnect();
  }, [hasData]);
  if (!rows.length || !values.length)
    return <EmptyState>No data in this range.</EmptyState>;
  const max = Math.max(1, ...values);
  const plot = width - 64;
  const x = (i: number) =>
    44 + (rows.length === 1 ? plot / 2 : (i / (rows.length - 1)) * plot);
  const y = (value: number) => 190 - (value / max) * 160;
  const selected = rows[Math.min(index ?? rows.length - 1, rows.length - 1)];
  return (
    <section className="panel min-w-0 p-4 sm:p-5">
      <h3 className="mb-4 font-semibold">Daily performance</h3>
      <div className="mb-3 flex flex-wrap gap-x-5 gap-y-2 text-xs">
        {series.map((s) => (
          <span key={s.key} className="flex items-center gap-2">
            <span className="h-0.5 w-4" style={{ background: s.color }} />
            {s.label}
          </span>
        ))}
      </div>
      <div ref={parent} className="min-w-0">
        <svg
          role="img"
          aria-label="Daily GSC clicks, GSC impressions, and GA4 sessions"
          className="block h-[240px] w-full"
          viewBox={`0 0 ${width} 240`}
          onPointerMove={(event) => {
            const box = event.currentTarget.getBoundingClientRect();
            setIndex(
              Math.max(
                0,
                Math.min(
                  rows.length - 1,
                  Math.round(
                    ((((event.clientX - box.left) / box.width) * width - 44) /
                      plot) *
                      (rows.length - 1),
                  ),
                ),
              ),
            );
          }}
          onPointerLeave={() => setIndex(null)}
        >
          {[0, 0.5, 1].map((fraction) => (
            <g key={fraction}>
              <line
                x1={44}
                x2={width - 20}
                y1={y(max * fraction)}
                y2={y(max * fraction)}
                stroke="var(--border)"
              />
              <text
                x={36}
                y={y(max * fraction) + 4}
                textAnchor="end"
                fontSize={11}
                fill="var(--muted)"
              >
                {formatNumber(max * fraction)}
              </text>
            </g>
          ))}
          {series.map((s) => {
            const segments: string[] = [];
            let points = "";
            rows.forEach((row, i) => {
              if (row[s.key] === null) {
                if (points) segments.push(points);
                points = "";
              } else points += `${x(i)},${y(row[s.key]!)} `;
            });
            if (points) segments.push(points);
            return (
              <g key={s.key}>
                {segments.map((points, i) => (
                  <polyline
                    key={i}
                    points={points}
                    fill="none"
                    stroke={s.color}
                    strokeWidth={2}
                    strokeLinejoin="round"
                  />
                ))}
              </g>
            );
          })}
          {[0, Math.floor((rows.length - 1) / 2), rows.length - 1]
            .filter((value, i, all) => all.indexOf(value) === i)
            .map((i) => (
              <text
                key={i}
                x={x(i)}
                y={220}
                textAnchor={
                  i === 0 ? "start" : i === rows.length - 1 ? "end" : "middle"
                }
                fontSize={11}
                fill="var(--muted)"
              >
                {rows[i].data_date.slice(5)}
              </text>
            ))}
        </svg>
      </div>
      <input
        aria-label="Inspect date in chart"
        type="range"
        min={0}
        max={rows.length - 1}
        value={index ?? rows.length - 1}
        onChange={(event) => setIndex(Number(event.target.value))}
        className="sr-only focus:not-sr-only focus:w-full"
      />
      <div
        aria-live="polite"
        className="flex flex-wrap gap-x-5 gap-y-1 border-t border-border pt-3 text-xs text-muted"
      >
        <span>{formatDate(selected.data_date)}</span>
        {series.map((s) => (
          <span key={s.key}>
            {s.label}:{" "}
            <span className="font-medium text-foreground tabular-nums">
              {formatNumber(selected[s.key])}
            </span>
          </span>
        ))}
      </div>
    </section>
  );
}
