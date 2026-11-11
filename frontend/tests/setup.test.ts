import { describe, expect, it } from "vitest";
import { createApi } from "../lib/api";
import { setupProgress, sourceState } from "../lib/setup";
import type { SiteConnection } from "../lib/types";

function connection(over: Partial<SiteConnection> = {}): SiteConnection {
  const ready = {
    configured: true,
    service_account_email: "a@b.iam",
    message: "Ready",
  };
  return {
    slug: "s",
    domain: "x.com",
    display_name: "X",
    gsc_property: "sc-domain:x.com",
    ga4_property_id: null,
    can_manage: true,
    credentials: { gsc: ready, ga4: { ...ready, configured: false } },
    sync: { running: false, started_at: null, finished_at: null, results: {} },
    ...over,
  };
}

describe("sourceState", () => {
  it("follows property, credentials, test and sync", () => {
    expect(sourceState(connection(), "gsc")).toBe("connected");
    expect(sourceState(connection(), "ga4")).toBe("off");
    expect(sourceState(connection({ ga4_property_id: "123" }), "ga4")).toBe(
      "action",
    );
    expect(sourceState(connection(), "gsc", { ok: false, message: "x" })).toBe(
      "error",
    );
    expect(sourceState(connection(), "gsc", { ok: true, message: "x" })).toBe(
      "connected",
    );
    expect(
      sourceState(
        connection({
          sync: {
            running: true,
            started_at: null,
            finished_at: null,
            results: {},
          },
        }),
        "gsc",
      ),
    ).toBe("syncing");
    expect(
      sourceState(
        connection({
          sync: {
            running: false,
            started_at: null,
            finished_at: null,
            results: {
              gsc: { status: "error", rows_loaded: null, message: "no" },
            },
          },
        }),
        "gsc",
      ),
    ).toBe("error");
  });
});

it("setupProgress counts connected sources out of three", () => {
  expect(setupProgress(["connected", "off", "connected"])).toEqual({
    done: 2,
    total: 3,
  });
});

describe("setup API calls", () => {
  it("uses the new endpoints", async () => {
    const calls: [string, RequestInit][] = [];
    const api = createApi(async (path, init) => {
      calls.push([path, init]);
      return new Response("{}", {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });
    await api.connectionOptions("a b");
    await api.testConnection("a b");
    await api.ahrefs("a b");
    expect(calls.map(([path, init]) => [path, init.method ?? "GET"])).toEqual([
      ["/api/sites/a%20b/connection/options", "GET"],
      ["/api/sites/a%20b/connection/test", "POST"],
      ["/api/sites/a%20b/ahrefs", "GET"],
    ]);
  });
});

describe("pickerTyping", () => {
  it("lets the user switch back to the list even when the saved value is not in it", async () => {
    const { pickerTyping } = await import("../lib/setup");
    expect(
      pickerTyping({
        manual: false,
        loading: false,
        listLength: 3,
        valueKnown: false,
        value: "x",
      }),
    ).toBe(true);
    expect(
      pickerTyping({
        manual: false,
        loading: false,
        listLength: 3,
        valueKnown: false,
        value: "x",
        chooseList: true,
      }),
    ).toBe(false);
    expect(
      pickerTyping({
        manual: true,
        loading: false,
        listLength: 3,
        valueKnown: true,
        value: "x",
      }),
    ).toBe(true);
    expect(
      pickerTyping({
        manual: false,
        loading: false,
        listLength: 0,
        valueKnown: false,
        value: "",
      }),
    ).toBe(true);
    expect(
      pickerTyping({
        manual: false,
        loading: true,
        listLength: 0,
        valueKnown: false,
        value: "",
      }),
    ).toBe(false);
  });
});
