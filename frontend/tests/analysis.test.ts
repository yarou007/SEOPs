import { describe, expect, it } from "vitest";
import {
  axisDefinitions,
  axisFinding,
  deviceBars,
  funnelBars,
  heatmapValue,
  indexSlices,
  positionBand,
  scatterPoints,
  statusDetails,
} from "../lib/analysis";

describe("axis statuses", () => {
  it.each([
    ["ready", "Ready", "badge-good"],
    ["partial", "Partial", "badge-warning"],
    ["needs_setup", "Needs setup", "badge-muted"],
  ] as const)(
    "labels %s and preserves its reason",
    (status, label, className) => {
      expect(statusDetails(status, "Source limitation")).toEqual({
        label,
        className,
        description: "Source limitation",
      });
    },
  );
  it("describes a ready badge without a missing-data warning", () =>
    expect(statusDetails("ready").description).toBe(
      "Required evidence is available.",
    ));
  it("keeps the product's eight-axis order", () =>
    expect(axisDefinitions.map(([key]) => key)).toEqual([
      "impressions-clicks",
      "funnel",
      "devices",
      "geography",
      "sitemaps",
      "internal-links",
      "site-links",
      "search-requests",
    ]));
});
describe("chart transforms preserve source meaning", () => {
  it("retains real zeros and flags zero-click page points", () => {
    const rows = scatterPoints(
      [
        {
          page: "/a",
          impressions: 200,
          clicks: 0,
          avg_position: 12,
          high_impressions_zero_clicks: true,
        },
      ],
      "clicks",
    );
    expect(rows[0]).toMatchObject({
      x: 200,
      y: 0,
      size: 12,
      highlighted: true,
    });
  });
  it("does not turn unknown chart values into zero", () =>
    expect(
      scatterPoints(
        [{ impressions: 20, clicks: null, avg_position: 3 }],
        "clicks",
      ),
    ).toEqual([]));
  it("uses position on the query chart and keeps outside-range opportunity unknown", () => {
    const point = scatterPoints(
      [
        {
          query: "repair",
          impressions: 20,
          clicks: 2,
          avg_position: 21,
          opportunity: null,
        },
      ],
      "position",
    )[0];
    expect(point).toMatchObject({
      label: "repair",
      x: 20,
      y: 21,
      opportunityBand: "unknown",
    });
  });
  it("separates high and low opportunity colors", () =>
    expect(
      scatterPoints(
        [
          { impressions: 200, clicks: 0, avg_position: 12, opportunity: 200 },
          { impressions: 30, clicks: 0, avg_position: 12, opportunity: 30 },
        ],
        "position",
      ).map((row) => row.opportunityBand),
    ).toEqual(["high", "low"]));
  it("converts CTR ratios to percentages but leaves missing values unknown", () => {
    const rows = deviceBars([
      { device: "MOBILE", ctr: 0.012, avg_position: 14 },
      { device: "TABLET", ctr: null, avg_position: null },
    ]);
    expect(rows[0]).toMatchObject({ ctr_percent: 1.2, position: 14 });
    expect(rows[1]).toMatchObject({ ctr_percent: null, position: null });
  });
  it.each([
    [1, "1–3"],
    [3.9, "1–3"],
    [4, "4–10"],
    [10.9, "4–10"],
    [11, "11–20"],
    [20.9, "11–20"],
    [21, "21+"],
    [null, "Unknown"],
  ])("maps position %s to band %s", (position, band) =>
    expect(positionBand(position)).toBe(band),
  );
  it("omits untracked call counts from bar heights, but keeps recorded zeros", () =>
    expect(
      funnelBars([
        { name: "Clicks", value: 0 },
        { name: "Call clicks", value: null },
      ]),
    ).toEqual([{ name: "Clicks", value: 0 }]));
  it("keeps unknown index verdicts separate from not indexed", () =>
    expect(
      indexSlices({ indexed: 2, not_indexed: 1, unknown: 3 }).map(
        ({ name, value }) => [name, value],
      ),
    ).toEqual([
      ["Indexed in sample", 2],
      ["Not indexed in sample", 1],
      ["Unknown verdict", 3],
    ]));
  it("distinguishes zero links from unknown exports and respects direction", () => {
    const matrix = [
      { source: "a", target: "b", links: 0 },
      { source: "b", target: "a", links: 5 },
    ];
    expect(heatmapValue(matrix, "a", "b")).toBe(0);
    expect(heatmapValue(matrix, "b", "a")).toBe(5);
    expect(heatmapValue(matrix, "a", "missing")).toBeNull();
  });
  it("summarizes the most useful query instead of inventing missing keyword volume", () =>
    expect(
      axisFinding("search-requests", {
        queries: [
          { query: "first", opportunity: 200 },
          { query: "second", opportunity: 20 },
        ],
      }),
    ).toContain("“first”"));
});
