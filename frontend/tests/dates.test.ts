import { describe, expect, it } from "vitest";
import {
  addDays,
  defaultWindow,
  isStale,
  presetRange,
  subtractMonths,
  validDate,
  validateRange,
} from "../lib/dates";

describe("backend-anchored inclusive date windows", () => {
  it("uses the backend end for a 28-day default", () =>
    expect(defaultWindow("2026-10-16")).toEqual({
      start: "2026-09-19",
      end: "2026-10-16",
    }));
  it("uses 90 inclusive days", () =>
    expect(presetRange(90, "2026-10-16")).toEqual({
      start: "2026-07-19",
      end: "2026-10-16",
    }));
  it("crosses year boundaries", () =>
    expect(presetRange(28, "2026-01-03")).toEqual({
      start: "2025-12-07",
      end: "2026-01-03",
    }));
  it("handles leap days", () =>
    expect(addDays("2024-03-01", -1)).toBe("2024-02-29"));
  it("clamps calendar months", () =>
    expect(subtractMonths("2026-06-30", 16)).toBe("2025-02-28"));
  it.each(["", "2026-02-30", "2026-13-01", "2026-2-01", "0000-01-01"])(
    "rejects invalid date %s",
    (date) => expect(validDate(date)).toBe(false),
  );
  it("accepts a valid leap day", () =>
    expect(validDate("2024-02-29")).toBe(true));
  it("accepts a single day", () =>
    expect(
      validateRange({ start: "2026-10-16", end: "2026-10-16" }),
    ).toBeNull());
  it("rejects an inverted range", () =>
    expect(validateRange({ start: "2026-10-17", end: "2026-10-16" })).toContain(
      "before",
    ));
  it("rejects more than 16 calendar months", () =>
    expect(validateRange({ start: "2025-06-15", end: "2026-10-16" })).toContain(
      "16 calendar months",
    ));
  it("accepts exactly 16 calendar months", () =>
    expect(
      validateRange({ start: "2025-06-16", end: "2026-10-16" }),
    ).toBeNull());
  it("requires both dates", () =>
    expect(validateRange({ start: "", end: "2026-10-16" })).toContain("valid"));
  it("marks more than five days stale", () =>
    expect(isStale("2026-10-13", "2026-10-19")).toBe(true));
  it("does not mark exactly five days stale", () =>
    expect(isStale("2026-10-14", "2026-10-19")).toBe(false));
  it("does not invent a date for a missing sync", () =>
    expect(isStale(null, "2026-10-19")).toBe(false));
});
