import { describe, expect, it } from "vitest";
import {
  decodeExport,
  periodFromFolder,
  recogniseReport,
  REPORT_LABELS,
} from "../lib/ahrefs";

function utf16le(text: string): Uint8Array {
  const bytes = new Uint8Array(2 + text.length * 2);
  bytes[0] = 0xff;
  bytes[1] = 0xfe;
  for (let i = 0; i < text.length; i++) {
    bytes[2 + i * 2] = text.charCodeAt(i) & 0xff;
    bytes[3 + i * 2] = text.charCodeAt(i) >> 8;
  }
  return bytes;
}
const withRow = (header: string[]) =>
  tsv(
    header,
    header.map(() => "1"),
  );
const tsv = (...rows: string[][]) =>
  rows.map((row) => row.map((cell) => `"${cell}"`).join("\t")).join("\n") +
  "\n";

describe("decodeExport", () => {
  it("decodes UTF-16 LE with a BOM and plain UTF-8", () => {
    expect(decodeExport(utf16le('"Channel"\t"Visitors"'))).toBe(
      '"Channel"\t"Visitors"',
    );
    expect(decodeExport(new TextEncoder().encode("a,b"))).toBe("a,b");
  });
  it("treats a BOM-only file as empty", () => {
    expect(decodeExport(new Uint8Array([0xff, 0xfe]))).toBe("");
  });
});

describe("recogniseReport", () => {
  it("tells reports apart by their header", () => {
    expect(
      recogniseReport(
        withRow(["Page", "Visitors", "Views", "Bounce rate", "Time on page"]),
      ),
    ).toBe("top_pages");
    expect(
      recogniseReport(withRow(["Page", "Visitors", "Exits", "Exit rate"])),
    ).toBe("exit_pages");
    expect(
      recogniseReport(withRow(["Event property: href", "Count", "Visitors"])),
    ).toBe("outbound_links");
    expect(
      recogniseReport(
        withRow(["UTM campaign", "Visitors", "Bounce rate", "Visit duration"]),
      ),
    ).toBe("utm_campaign");
  });
  it("reports empty and unknown files", () => {
    expect(recogniseReport("")).toBe("empty");
    expect(recogniseReport(tsv(["City", "Visitors"]))).toBe("empty");
    expect(recogniseReport(tsv(["Foo", "Bar"], ["a", "b"]))).toBe("unknown");
  });
  it("has a label for every report", () => {
    expect(Object.keys(REPORT_LABELS)).toHaveLength(19);
  });
});

describe("periodFromFolder", () => {
  it("uses the 30 days ending on the export date", () => {
    expect(
      periodFromFolder(
        "dcemergencylockanddoor_all-stats_ahrefs_2026-11-11_21-23-17",
        new Date("2026-12-01T10:00:00Z"),
      ),
    ).toEqual({ start: "2026-10-13", end: "2026-11-11" });
  });
  it("falls back to the 30 days ending today", () => {
    expect(
      periodFromFolder("export", new Date("2026-11-20T10:00:00Z")),
    ).toEqual({
      start: "2026-10-22",
      end: "2026-11-20",
    });
  });
});

describe("weightedBounce and pageLabel", () => {
  it("weights bounce rate by visitors", async () => {
    const { weightedBounce } = await import("../lib/ahrefs");
    expect(
      weightedBounce([
        { name: "a", visitors: 30, bounce_rate: 0.5 },
        { name: "b", visitors: 10, bounce_rate: 1 },
      ]),
    ).toBeCloseTo(0.625);
    expect(weightedBounce([])).toBeNull();
    expect(weightedBounce(undefined)).toBeNull();
  });
  it("shows the host when it is not the website's own", async () => {
    const { pageLabel } = await import("../lib/ahrefs");
    expect(pageLabel("https://x.com/a", "x.com")).toBe("/a");
    expect(pageLabel("https://www.x.com/", "x.com")).toBe("www.x.com/");
    expect(pageLabel("tel:+1703", "x.com")).toBe("tel:+1703");
  });
});
