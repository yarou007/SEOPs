import { describe, expect, it } from "vitest";
import { createApi } from "../lib/api";
import { STARTER_QUESTIONS, quotaLabel, sortInsights } from "../lib/insights";
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
