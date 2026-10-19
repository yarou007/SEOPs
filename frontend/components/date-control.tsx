"use client";
import { useState, useTransition } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { presetRange, validDate, validateRange } from "@/lib/dates";
import type { DateRange } from "@/lib/types";

export function DateControl({
  range,
  defaultEnd,
}: {
  range: DateRange;
  defaultEnd: string;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const search = useSearchParams();
  const [start, setStart] = useState(validDate(range.start) ? range.start : "");
  const [end, setEnd] = useState(validDate(range.end) ? range.end : "");
  const last28 = presetRange(28, defaultEnd);
  const last90 = presetRange(90, defaultEnd);
  const initialPreset =
    range.start === last28.start && range.end === last28.end
      ? "28"
      : range.start === last90.start && range.end === last90.end
        ? "90"
        : "custom";
  const [preset, setPreset] = useState(initialPreset);
  const [error, setError] = useState("");
  const [pending, transition] = useTransition();
  function apply(next: DateRange) {
    const error = validateRange(next);
    setError(error ?? "");
    if (error) return;
    const params = new URLSearchParams(search.toString());
    params.set("start", next.start);
    params.set("end", next.end);
    for (const key of ["pagesOffset", "queriesOffset", "trafficOffset"])
      params.delete(key);
    transition(() => router.push(`${pathname}?${params}`, { scroll: false }));
  }
  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        apply({ start, end });
      }}
      className="panel mb-7 p-4"
    >
      <div className="grid grid-cols-2 items-end gap-3 sm:flex sm:flex-wrap">
        <div className="col-span-2 sm:w-40">
          <label
            className="mb-1 block text-xs font-medium text-muted"
            htmlFor="preset"
          >
            Date range
          </label>
          <select
            className="w-full"
            id="preset"
            value={preset}
            onChange={(event) => {
              const value = event.target.value;
              setPreset(value);
              if (value !== "custom") {
                const next = presetRange(value === "28" ? 28 : 90, defaultEnd);
                setStart(next.start);
                setEnd(next.end);
                apply(next);
              }
            }}
          >
            <option value="28">Last 28 days</option>
            <option value="90">Last 90 days</option>
            <option value="custom">Custom</option>
          </select>
        </div>
        <div className="sm:w-40">
          <label
            className="mb-1 block text-xs font-medium text-muted"
            htmlFor="start"
          >
            Start
          </label>
          <input
            id="start"
            type="date"
            value={start}
            required
            onChange={(event) => {
              setStart(event.target.value);
              setPreset("custom");
            }}
          />
        </div>
        <div className="sm:w-40">
          <label
            className="mb-1 block text-xs font-medium text-muted"
            htmlFor="end"
          >
            End
          </label>
          <input
            id="end"
            type="date"
            value={end}
            required
            onChange={(event) => {
              setEnd(event.target.value);
              setPreset("custom");
            }}
          />
        </div>
        <button
          type="submit"
          className="button col-span-2 sm:ml-1"
          disabled={pending}
        >
          {pending ? "Applying…" : "Apply"}
        </button>
        <p className="col-span-2 text-xs text-muted sm:ml-auto">
          Compared with the preceding equal-length period
        </p>
      </div>
      {error && (
        <p role="alert" className="mt-3 text-sm text-bad">
          {error}
        </p>
      )}
    </form>
  );
}
