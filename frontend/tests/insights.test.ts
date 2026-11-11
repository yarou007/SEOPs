import { describe, expect, it } from "vitest";
import { createApi } from "../lib/api";
import {
  STARTER_QUESTIONS,
  filterInsights,
  quotaLabel,
  quotaPercent,
  sortInsights,
} from "../lib/insights";
import type { AiInsight, UsageInfo } from "../lib/types";

const usage = (over: Partial<UsageInfo> = {}): UsageInfo => ({
  configured: true,
  model: "m",
  used: 3,
  budget: 45,
  remaining: 42,
  exhausted: false,
  ...over,
});

const insight = (
  id: string,
  priority: AiInsight["priority"],
  created_at: string,
): AiInsight => ({
  id,
  source: "chat",
  report_date: null,
  message_id: null,
  title: id,
  problem: "",
  evidence: [],
  advice: "",
  target_url: null,
  target_kpi: "ctr",
  priority,
  status: "new",
  model: "m",
  created_at,
  updated_at: created_at,
});

describe("quotaLabel", () => {
  it("says when AI is not configured", () =>
    expect(quotaLabel(usage({ configured: false }))).toBe("AI not configured"));
  it("says when the daily limit is reached", () =>
    expect(quotaLabel(usage({ exhausted: true, remaining: 0 }))).toBe(
      "Daily AI limit reached",
    ));
  it("counts requests left", () =>
    expect(quotaLabel(usage())).toBe("42 AI requests left today"));
});

describe("sortInsights", () => {
  it("orders by priority then newest first", () => {
    const sorted = sortInsights([
      insight("low", "low", "2026-11-03T00:00:00Z"),
      insight("high-old", "high", "2026-11-01T00:00:00Z"),
      insight("medium", "medium", "2026-11-04T00:00:00Z"),
      insight("high-new", "high", "2026-11-02T00:00:00Z"),
    ]);
    expect(sorted.map((item) => item.id)).toEqual([
      "high-new",
      "high-old",
      "medium",
      "low",
    ]);
  });
});

describe("starter questions", () => {
  it("matches the spec", () =>
    expect(STARTER_QUESTIONS).toEqual([
      "Why did clicks change vs last period?",
      "Which pages have the best quick-win potential?",
      "What should we fix first this week?",
    ]));
});

describe("insights API", () => {
  it("posts a question as JSON", async () => {
    const calls: [string, RequestInit][] = [];
    const api = createApi(async (path, init) => {
      calls.push([path, init]);
      return new Response(
        JSON.stringify({ conversation_id: "c", message: {}, insights: [] }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    });
    await api.ask("s", { question: "Why?" });
    expect(calls[0][0]).toBe("/api/sites/s/insights/ask");
    expect(calls[0][1].method).toBe("POST");
    expect(JSON.parse(String(calls[0][1].body))).toEqual({ question: "Why?" });
  });
  it("lists insights without a trailing slash (Next.js strips it)", async () => {
    const paths: string[] = [];
    const api = createApi(async (path) => {
      paths.push(path);
      return new Response("[]", { status: 200 });
    });
    await api.insights("s", { status: "new" });
    expect(paths[0]).toBe("/api/sites/s/insights?status=new");
  });
  it("reports a timeout separately from an unreachable API", async () => {
    const api = createApi(async () => {
      throw new DOMException("timed out", "TimeoutError");
    });
    await expect(api.ask("s", { question: "Why?" })).rejects.toMatchObject({
      status: 504,
      message:
        "This is taking longer than expected. The answer may still appear: reload in a minute.",
    });
  });
  it("patches an insight status", async () => {
    const calls: [string, RequestInit][] = [];
    const api = createApi(async (path, init) => {
      calls.push([path, init]);
      return new Response("{}", { status: 200 });
    });
    await api.updateInsight("s", "i1", "done");
    expect(calls[0][0]).toBe("/api/sites/s/insights/i1");
    expect(calls[0][1].method).toBe("PATCH");
  });
});

describe("filterInsights", () => {
  const items = [
    { ...insight("a", "low", "2026-11-01"), status: "new" as const },
    { ...insight("b", "high", "2026-11-02"), status: "accepted" as const },
    { ...insight("c", "high", "2026-11-03"), status: "done" as const },
    { ...insight("d", "medium", "2026-11-04"), status: "dismissed" as const },
  ];
  it("keeps open advice (new or accepted) by default order of priority", () => {
    expect(filterInsights(items, "open", "all").map((item) => item.id)).toEqual(
      ["b", "a"],
    );
  });
  it("filters by status and priority", () => {
    expect(filterInsights(items, "done", "all").map((item) => item.id)).toEqual(
      ["c"],
    );
    expect(filterInsights(items, "all", "high").map((item) => item.id)).toEqual(
      ["c", "b"],
    );
    expect(filterInsights(items, "open", "medium")).toEqual([]);
  });
});

describe("quotaPercent", () => {
  it("shows the share used", () => {
    expect(quotaPercent(usage({ used: 9, budget: 45 }))).toBe(20);
    expect(quotaPercent(usage({ budget: 0 }))).toBe(0);
    expect(quotaPercent(usage({ exhausted: true }))).toBe(100);
  });
});
