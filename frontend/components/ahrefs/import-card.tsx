"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  FileCheck2,
  FileQuestion,
  FileX2,
  FolderOpen,
  Upload,
} from "lucide-react";
import { AxisUpload } from "@/components/axis-upload";
import { Card } from "@/components/ui/card";
import {
  decodeExport,
  periodFromFolder,
  recogniseReport,
  REPORT_LABELS,
} from "@/lib/ahrefs";
import { api, ApiError } from "@/lib/api";
import type { WebAnalyticsFile, WebAnalyticsReport } from "@/lib/types";

type Picked = {
  name: string;
  content: string;
  kind: WebAnalyticsReport | "empty" | "unknown";
};
const TABS = [
  ["web", "Web Analytics"],
  ["backlinks", "Backlinks"],
  ["audit", "Site Audit"],
] as const;
const MAX_BYTES = 2_000_000;

function WebAnalyticsImport({ slug }: { slug: string }) {
  const router = useRouter();
  const [picked, setPicked] = useState<Picked[]>([]);
  const [period, setPeriod] = useState(() => periodFromFolder(""));
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(
    null,
  );

  async function choose(list: FileList | null) {
    setMessage(null);
    if (!list?.length) return;
    const files = Array.from(list).filter((file) =>
      /\.(csv|tsv|txt)$/i.test(file.name),
    );
    if (files.reduce((sum, file) => sum + file.size, 0) > MAX_BYTES * 2) {
      setMessage({
        ok: false,
        text: "These files are too large. The export must be at most 2 MB.",
      });
      return;
    }
    try {
      const read = await Promise.all(
        files.map(async (file) => {
          const content = decodeExport(
            new Uint8Array(await file.arrayBuffer()),
          );
          return { name: file.name, content, kind: recogniseReport(content) };
        }),
      );
      setPicked(read.sort((a, b) => a.name.localeCompare(b.name)));
      const folder = (
        files[0] as File & { webkitRelativePath?: string }
      ).webkitRelativePath?.split("/")[0];
      setPeriod(periodFromFolder(folder ?? ""));
    } catch {
      setPicked([]);
      setMessage({
        ok: false,
        text: "A file could not be read. Choose the files exactly as Ahrefs exported them.",
      });
    }
  }

  const recognised = picked.filter(
    (file) => !["empty", "unknown"].includes(file.kind),
  );
  const empty = picked.filter((file) => file.kind === "empty");
  const unknown = picked.filter((file) => file.kind === "unknown");

  async function upload() {
    setBusy(true);
    setMessage(null);
    try {
      const files: WebAnalyticsFile[] = picked
        .filter((file) => file.kind !== "unknown")
        .map(({ name, content }) => ({ name, content }));
      const result = await api.importWebAnalytics(slug, {
        period_start: period.start,
        period_end: period.end,
        files,
      });
      setMessage({
        ok: true,
        text: `Imported ${result.files.recognised} reports for ${period.start} to ${period.end}: ${result.totals.visitors} visitors, ${result.totals.phone_clicks} phone clicks.`,
      });
      setPicked([]);
      router.refresh();
    } catch (caught) {
      setMessage({
        ok: false,
        text:
          caught instanceof ApiError
            ? caught.message
            : "The import failed. Try again.",
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <ol className="list-decimal space-y-1 pl-5 text-sm text-muted">
        <li>
          In Ahrefs, open Web Analytics for this website and pick the period
          (for example, Last 30 days).
        </li>
        <li>Click Export all data, then unzip the downloaded file.</li>
        <li>
          Choose the unzipped folder below, check the period, then import.
        </li>
      </ol>
      <div className="flex flex-wrap gap-2">
        <label className="button cursor-pointer">
          <FolderOpen size={15} aria-hidden /> Choose folder
          <input
            type="file"
            className="sr-only"
            // @ts-expect-error webkitdirectory is supported by every current browser
            webkitdirectory=""
            multiple
            disabled={busy}
            onChange={(event) => choose(event.target.files)}
          />
        </label>
        <label className="button cursor-pointer">
          <Upload size={15} aria-hidden /> Choose files
          <input
            type="file"
            className="sr-only"
            accept=".csv,.tsv,text/csv"
            multiple
            disabled={busy}
            onChange={(event) => choose(event.target.files)}
          />
        </label>
      </div>
      {picked.length > 0 && (
        <div className="space-y-4 rounded-md bg-surface-muted p-4">
          <p className="text-sm font-medium">
            {recognised.length} reports recognised, {empty.length} empty,{" "}
            {unknown.length} not recognised
          </p>
          <ul className="flex flex-wrap gap-1.5">
            {recognised.map((file) => (
              <li key={file.name} className="badge badge-good gap-1">
                <FileCheck2 size={12} aria-hidden />
                {REPORT_LABELS[file.kind as WebAnalyticsReport]}
              </li>
            ))}
            {empty.map((file) => (
              <li key={file.name} className="badge badge-muted gap-1">
                <FileX2 size={12} aria-hidden /> {file.name} (empty)
              </li>
            ))}
            {unknown.map((file) => (
              <li key={file.name} className="badge badge-warning gap-1">
                <FileQuestion size={12} aria-hidden /> {file.name} (skipped)
              </li>
            ))}
          </ul>
          <fieldset className="grid gap-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
            <legend className="mb-2 text-sm font-medium">
              Period this export covers
            </legend>
            <label className="text-xs text-muted">
              From
              <input
                type="date"
                className="mt-1 w-full"
                value={period.start}
                max={period.end}
                onChange={(event) =>
                  setPeriod((current) => ({
                    ...current,
                    start: event.target.value,
                  }))
                }
              />
            </label>
            <label className="text-xs text-muted">
              To
              <input
                type="date"
                className="mt-1 w-full"
                value={period.end}
                min={period.start}
                onChange={(event) =>
                  setPeriod((current) => ({
                    ...current,
                    end: event.target.value,
                  }))
                }
              />
            </label>
            <button
              type="button"
              className="button button-primary"
              disabled={
                busy || !recognised.length || !period.start || !period.end
              }
              onClick={upload}
            >
              {busy ? "Importing…" : "Import"}
            </button>
          </fieldset>
          <p className="text-xs text-muted">
            Importing the same period again replaces it. A different period is
            kept, so you can follow the changes over time.
          </p>
        </div>
      )}
      {message && (
        <p
          role={message.ok ? "status" : "alert"}
          className={`rounded-md p-3 text-sm ${message.ok ? "bg-good-soft text-good" : "bg-bad-soft text-bad"}`}
        >
          {message.text}
        </p>
      )}
    </div>
  );
}

export function AhrefsImport({ slug }: { slug: string }) {
  const [tab, setTab] = useState<(typeof TABS)[number][0]>("web");
  return (
    <Card
      title="Import from Ahrefs"
      description="Upload exports from your Ahrefs account. They are saved in the SEOPs database for this website."
    >
      <div
        role="tablist"
        aria-label="Export type"
        className="mb-5 flex flex-wrap gap-1 border-b border-border"
      >
        {TABS.map(([key, label]) => (
          <button
            key={key}
            type="button"
            role="tab"
            id={`tab-${key}`}
            aria-selected={tab === key}
            aria-controls={`panel-${key}`}
            className={`-mb-px border-b-2 px-3 py-2 text-sm font-medium ${tab === key ? "border-brass text-foreground" : "border-transparent text-muted hover:text-foreground"}`}
            onClick={() => setTab(key)}
          >
            {label}
          </button>
        ))}
      </div>
      <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
        {tab === "web" ? (
          <WebAnalyticsImport slug={slug} />
        ) : tab === "backlinks" ? (
          <div className="space-y-3">
            <ol className="list-decimal space-y-1 pl-5 text-sm text-muted">
              <li>
                In Ahrefs Site Explorer, enter this website and open Backlinks.
              </li>
              <li>Click Export and choose CSV (UTF-8 or UTF-16).</li>
              <li>Upload the file here.</li>
            </ol>
            <AxisUpload slug={slug} kind="backlinks" />
          </div>
        ) : (
          <div className="space-y-3">
            <ol className="list-decimal space-y-1 pl-5 text-sm text-muted">
              <li>
                In Ahrefs Site Audit, open this website’s latest crawl, then
                Page explorer.
              </li>
              <li>
                Export the pages with the columns URL, No. of inlinks and HTTP
                status code.
              </li>
              <li>Upload the file here.</li>
            </ol>
            <AxisUpload slug={slug} kind="internal-links" />
          </div>
        )}
      </div>
    </Card>
  );
}
