import { describe, expect, it } from "vitest";
import { activeSection, sectionHref, SECTIONS, slugFromPath } from "../lib/nav";

describe("sectionHref", () => {
  it("keeps the date range and drops table offsets", () => {
    const query = new URLSearchParams(
      "start=2026-10-01&end=2026-10-28&pagesOffset=50&tab=search&device=MOBILE",
    );
    expect(sectionHref("arlington", "traffic", query)).toBe(
      "/sites/arlington?start=2026-10-01&end=2026-10-28&device=MOBILE&tab=traffic",
    );
  });
  it("links Overview without a tab and encodes the slug", () => {
    expect(sectionHref("a b", "overview")).toBe("/sites/a%20b");
  });
  it("sends Setup to the settings page without the query", () => {
    expect(
      sectionHref("arlington", "setup", new URLSearchParams("start=x")),
    ).toBe("/sites/arlington/settings");
  });
});

describe("activeSection", () => {
  it("reads the settings path and the tab", () => {
    expect(activeSection("/sites/arlington/settings", null)).toBe("setup");
    expect(activeSection("/sites/arlington", "insights")).toBe("insights");
    expect(activeSection("/sites/arlington", null)).toBe("overview");
    expect(activeSection("/sites/arlington", "nope")).toBe("overview");
  });
});

describe("slugFromPath", () => {
  it("finds the site slug", () => {
    expect(slugFromPath("/sites/arlington/settings")).toBe("arlington");
    expect(slugFromPath("/sites/a%20b")).toBe("a b");
    expect(slugFromPath("/sites")).toBeNull();
    expect(slugFromPath("/sites/new")).toBeNull();
  });
});

it("lists the sections in order", () => {
  expect(SECTIONS.map((section) => section.key)).toEqual([
    "overview",
    "search",
    "traffic",
    "analysis",
    "insights",
    "ahrefs",
    "setup",
    "status",
  ]);
});
