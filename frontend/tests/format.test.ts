import { describe, expect, it } from "vitest";
import {
  EMPTY,
  formatChange,
  formatDate,
  formatNumber,
  formatPercent,
  formatPosition,
  percentChange,
} from "../lib/format";

describe("metric formatting and change", () => {
  it("adds thousands separators", () =>
    expect(formatNumber(1234567)).toBe("1,234,567"));
  it("preserves a real zero", () => expect(formatNumber(0)).toBe("0"));
  it("formats a ratio as percent", () =>
    expect(formatPercent(0.1234)).toBe("12.34%"));
  it("formats a zero percentage", () => expect(formatPercent(0)).toBe("0%"));
  it("formats position to two decimals", () =>
    expect(formatPosition(3.9)).toBe("3.90"));
  it.each([formatNumber, formatPercent, formatPosition])(
    "displays missing values as an em dash",
    (format) => {
      expect(format(null)).toBe(EMPTY);
      expect(format(undefined)).toBe(EMPTY);
    },
  );
  it("does not display NaN", () => expect(formatNumber(NaN)).toBe(EMPTY));
  it("calculates relative change", () =>
    expect(percentChange(150, 100)).toBe(0.5));
  it("calculates a decline", () => expect(percentChange(60, 100)).toBe(-0.4));
  it("handles unchanged zero", () => expect(percentChange(0, 0)).toBe(0));
  it("has no baseline when previous is zero", () =>
    expect(percentChange(10, 0)).toBeNull());
  it("has no comparison for missing data", () => {
    expect(percentChange(null, 10)).toBeNull();
    expect(percentChange(10, null)).toBeNull();
  });
  it("formats positive change", () => expect(formatChange(0.5)).toBe("+50%"));
  it("formats missing change", () => expect(formatChange(null)).toBe(EMPTY));
  it("formats calendar dates consistently", () =>
    expect(formatDate("2026-10-16")).toBe("16 Oct 2026"));
  it("formats a missing date", () => expect(formatDate(null)).toBe(EMPTY));
});
