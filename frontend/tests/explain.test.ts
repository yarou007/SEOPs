import { describe, expect, it } from "vitest";
import { GLOSSARY, headline, nextActions, pagePath } from "../lib/explain";
import type { PageFlag, Summary, WeeklyReport } from "../lib/types";

const range = { start: "2026-10-12", end: "2026-11-08" };
function summary(clicks: number | null, before: number | null): Summary {
  const gsc = (value: number | null) =>
    value === null
      ? null
      : { clicks: value, impressions: 100, ctr: 0.1, avg_position: 5 };
  return {
    current_window: range,
    previous_window: { start: "2026-09-14", end: "2026-10-11" },
    current: { gsc: gsc(clicks), ga4: null },
    previous: { gsc: gsc(before), ga4: null },
  };
}
function flag(check: string, extra: Partial<PageFlag> = {}): PageFlag {
  return {
    page: "https://dcemergencylockanddoor.com/panic-bar-repair-washington-dc",
    clicks: 0,
    impressions: 459,
    ctr: 0,
    avg_position: 23.65,
    check,
    reason: "",
    position_band: "21+",
    median_ctr_for_band: 0.012,
    impressions_lost: 5,
    ...extra,
  };
}
function report(
  pages: PageFlag[],
  candidates = [] as WeeklyReport["query_candidates"],
) {
  return {
    windows: { current: range },
    top_pages: pages,
    query_candidates: candidates,
  } as unknown as WeeklyReport;
}

describe("headline", () => {
  it("says clicks fell, with the period length", () => {
    expect(headline(summary(6, 12), null)).toEqual({
      text: "Clicks from Google fell 50% compared with the previous 28 days.",
      tone: "bad",
    });
  });
  it("says clicks rose", () => {
    expect(headline(summary(9, 6), null).text).toBe(
      "Clicks from Google rose 50% compared with the previous 28 days.",
    );
    expect(headline(summary(9, 6), null).tone).toBe("good");
  });
  it("says unchanged", () => {
    expect(headline(summary(6, 6), null)).toEqual({
      text: "Clicks from Google stayed the same (6) compared with the previous 28 days.",
      tone: "neutral",
    });
  });
  it("handles no earlier period and no data", () => {
    expect(headline(summary(6, null), null)).toEqual({
      text: "6 clicks from Google in this period. No earlier period to compare yet.",
      tone: "neutral",
    });
    expect(headline(summary(6, 0), null).text).toContain("No earlier period");
    expect(headline(summary(null, 3), null)).toEqual({
      text: "No Search Console data for this period yet.",
      tone: "neutral",
    });
  });
  it("names the biggest drop from the weekly report, with its dates", () => {
    const text = headline(
      summary(6, 12),
      report([
        flag("zero_clicks"),
        flag("clicks_dropping", { page: "https://x.com/lock-repair/" }),
      ]),
    ).text;
    expect(text).toBe(
      "Clicks from Google fell 50% compared with the previous 28 days. " +
        "The biggest drop is on /lock-repair/ (weekly report, 12 Oct 2026 – 08 Nov 2026).",
    );
  });
});

describe("nextActions", () => {
  it("turns each flag into a plain action with real numbers", () => {
    const actions = nextActions(
      report([
        flag("zero_clicks"),
        flag("low_ctr", { clicks: 2, ctr: 0.004, median_ctr_for_band: 0.012 }),
        flag("clicks_dropping", { drop_percent: 95.21 }),
        flag("mobile_gap", { mobile_ctr: 0.002, desktop_ctr: 0.011 }),
      ]),
    );
    expect(actions.map(({ title, detail }) => [title, detail])).toEqual([
      [
        "Rewrite the title and description of /panic-bar-repair-washington-dc",
        "Shown 459 times on Google with no clicks.",
      ],
      [
        "Improve the search snippet of /panic-bar-repair-washington-dc",
        "Click rate 0.4% vs 1.2% typical at this position.",
      ],
      [
        "Check what changed on /panic-bar-repair-washington-dc",
        "Clicks down 95.21% vs the previous period.",
      ],
      [
        "Fix the mobile page of /panic-bar-repair-washington-dc",
        "Mobile click rate 0.2% vs desktop 1.1%.",
      ],
    ]);
  });
  it("adds search terms close to page 1 and respects the limit", () => {
    const candidates = [
      {
        query: "commercial locksmith dc",
        top_page: "https://x.com/a",
        clicks: 0,
        impressions: 101,
        ctr: 0,
        avg_position: 19.86,
        reason: "position 8–20, close to page 1",
      },
    ];
    const actions = nextActions(report([flag("zero_clicks")], candidates));
    expect(actions[1]).toMatchObject({
      title: "Push “commercial locksmith dc” onto page 1 of Google",
      detail: "Ranks 19.86 with 101 impressions.",
      page: "https://x.com/a",
    });
    expect(
      nextActions(report([flag("zero_clicks"), flag("trend")], candidates), 1),
    ).toHaveLength(1);
    expect(nextActions(null)).toEqual([]);
  });
});

it("pagePath keeps only the path", () => {
  expect(pagePath("https://x.com/a/b?q=1")).toBe("/a/b");
  expect(pagePath("not a url")).toBe("not a url");
});

it("every glossary entry has a plain label, a technical name and help", () => {
  for (const entry of Object.values(GLOSSARY)) {
    expect(entry.label).toBeTruthy();
    expect(entry.technical).toBeTruthy();
    expect(entry.help.length).toBeGreaterThan(20);
  }
  expect(GLOSSARY.ctr.label).toBe("Click rate");
  expect(GLOSSARY.position.higherIsBetter).toBe(false);
});

describe("comparisonLine", () => {
  it("names both periods only when there is something to compare", async () => {
    const { comparisonLine } = await import("../lib/explain");
    expect(comparisonLine(summary(6, 12))).toBe(
      "12 Oct 2026 – 08 Nov 2026, compared with 14 Sept 2026 – 11 Oct 2026.",
    );
    expect(comparisonLine(summary(6, null))).toBe("12 Oct 2026 – 08 Nov 2026.");
    expect(comparisonLine(summary(null, 3))).toBe("12 Oct 2026 – 08 Nov 2026.");
  });
});
