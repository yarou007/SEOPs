"use client";

import { useState } from "react";
import { pickerTyping } from "@/lib/setup";
import type { Ga4PropertyOption } from "@/lib/types";

/** Pick a property Google says SEOPs can read, or type it by hand. */
export function PropertyPicker({
  source,
  value,
  onChange,
  options,
  loading,
  error,
  disabled,
}: {
  source: "gsc" | "ga4";
  value: string;
  onChange: (value: string) => void;
  options: string[] | Ga4PropertyOption[] | null;
  loading: boolean;
  error: string | null;
  disabled: boolean;
}) {
  const list = (options ?? []).map((item) =>
    typeof item === "string"
      ? { value: item, label: item }
      : {
          value: item.id,
          label: `${item.name} (${item.id}) in ${item.account}`,
        },
  );
  const known = list.some((item) => item.value === value);
  const [mode, setMode] = useState<"auto" | "type" | "list">("auto");
  const typing = pickerTyping({
    manual: mode === "type",
    chooseList: mode === "list",
    loading,
    listLength: list.length,
    valueKnown: known,
    value,
  });
  const id = `${source}-property`;
  const label = source === "gsc" ? "Search Console property" : "GA4 property";
  return (
    <div>
      <div className="mb-1.5 flex flex-wrap items-baseline justify-between gap-2">
        <label htmlFor={id} className="font-medium">
          {label}
        </label>
        {list.length > 0 && !disabled && (
          <button
            type="button"
            className="text-xs text-accent hover:underline"
            onClick={() => setMode(typing ? "list" : "type")}
          >
            {typing ? "Choose from the list" : "Type it instead"}
          </button>
        )}
      </div>
      {typing ? (
        <input
          id={id}
          className="w-full"
          value={value}
          disabled={disabled}
          onChange={(event) => onChange(event.target.value)}
          placeholder={source === "gsc" ? "sc-domain:example.com" : "123456789"}
          inputMode={source === "ga4" ? "numeric" : undefined}
          pattern={source === "ga4" ? "[1-9][0-9]{0,29}" : undefined}
          maxLength={source === "gsc" ? 2048 : 30}
          aria-describedby={`${id}-help`}
        />
      ) : (
        <select
          id={id}
          className="w-full"
          value={known ? value : ""}
          disabled={disabled || loading}
          onChange={(event) => onChange(event.target.value)}
          aria-describedby={`${id}-help`}
        >
          <option value="">
            {loading ? "Loading your properties…" : "Not connected"}
          </option>
          {list.map((item) => (
            <option key={item.value} value={item.value}>
              {item.label}
            </option>
          ))}
        </select>
      )}
      <p id={`${id}-help`} className="mt-1.5 text-xs text-muted">
        {error ??
          (source === "gsc"
            ? "The list shows the Search Console properties SEOPs can already read. Typed by hand: sc-domain:example.com or https://example.com/."
            : "The list shows the GA4 properties SEOPs can already read. Typed by hand: the numeric property ID from Admin, then Property details (not the G- ID).")}
      </p>
    </div>
  );
}
