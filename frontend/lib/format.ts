export const EMPTY = "—";
export function formatNumber(value: number | null | undefined): string {
  return value == null || !Number.isFinite(value)
    ? EMPTY
    : new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(
        value,
      );
}
export function formatPercent(value: number | null | undefined): string {
  return value == null || !Number.isFinite(value)
    ? EMPTY
    : new Intl.NumberFormat("en-US", {
        style: "percent",
        maximumFractionDigits: 2,
      }).format(value);
}
export function formatPosition(value: number | null | undefined): string {
  return value == null || !Number.isFinite(value) ? EMPTY : value.toFixed(2);
}
export function percentChange(
  current: number | null | undefined,
  previous: number | null | undefined,
): number | null {
  if (
    current == null ||
    previous == null ||
    !Number.isFinite(current) ||
    !Number.isFinite(previous)
  )
    return null;
  if (previous === 0) return current === 0 ? 0 : null;
  return (current - previous) / Math.abs(previous);
}
export function formatChange(value: number | null): string {
  return value == null
    ? EMPTY
    : `${value > 0 ? "+" : ""}${formatPercent(value)}`;
}
export function formatDate(value: string | null | undefined): string {
  if (!value) return EMPTY;
  const date = new Date(`${value}T00:00:00Z`);
  return Number.isNaN(date.valueOf())
    ? EMPTY
    : new Intl.DateTimeFormat("en-GB", {
        day: "2-digit",
        month: "short",
        year: "numeric",
        timeZone: "UTC",
      }).format(date);
}
export function formatTime(value: string | null | undefined): string {
  if (!value) return EMPTY;
  const date = new Date(value);
  return Number.isNaN(date.valueOf())
    ? EMPTY
    : new Intl.DateTimeFormat("en-GB", {
        dateStyle: "medium",
        timeStyle: "short",
        timeZone: "UTC",
      }).format(date) + " UTC";
}
