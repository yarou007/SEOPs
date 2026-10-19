import type { DateRange } from "./types";

export function isoDate(date: Date): string {
  return date.toISOString().slice(0, 10);
}
export function validDate(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value) || value.startsWith("0000"))
    return false;
  const date = new Date(`${value}T00:00:00Z`);
  return !Number.isNaN(date.valueOf()) && isoDate(date) === value;
}
export function addDays(value: string, days: number): string {
  const date = new Date(`${value}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return isoDate(date);
}
export function subtractMonths(value: string, months: number): string {
  const date = new Date(`${value}T00:00:00Z`);
  const day = date.getUTCDate();
  date.setUTCDate(1);
  date.setUTCMonth(date.getUTCMonth() - months);
  const end = new Date(date);
  end.setUTCMonth(end.getUTCMonth() + 1);
  end.setUTCDate(0);
  date.setUTCDate(Math.min(day, end.getUTCDate()));
  return isoDate(date);
}
export function presetRange(days: 28 | 90, backendEnd: string): DateRange {
  return { start: addDays(backendEnd, -(days - 1)), end: backendEnd };
}
export function defaultWindow(backendEnd: string): DateRange {
  return presetRange(28, backendEnd);
}
export function validateRange(range: DateRange): string | null {
  if (!validDate(range.start) || !validDate(range.end))
    return "Enter a valid start and end date.";
  if (range.start > range.end) return "Start must be on or before end.";
  if (range.start < subtractMonths(range.end, 16))
    return "Range must not exceed 16 calendar months.";
  return null;
}
export function isStale(
  lastLoaded: string | null | undefined,
  today = isoDate(new Date()),
): boolean {
  if (!lastLoaded || !validDate(lastLoaded)) return false;
  return (
    new Date(`${today}T00:00:00Z`).valueOf() -
      new Date(`${lastLoaded}T00:00:00Z`).valueOf() >
    5 * 86400000
  );
}
