"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { CheckCircle2, RefreshCw, XCircle } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { formatDate, formatTime } from "@/lib/format";
import { setupProgress, sourceState } from "@/lib/setup";
import type {
  AhrefsData,
  ConnectionOptions,
  ConnectionTestResult,
  SiteConnection,
  SourceStatus,
} from "@/lib/types";
import { Step } from "./ui/steps";
import { StatusPill } from "./ui/status-pill";
import { AccessBox } from "./setup/access-box";
import { PropertyPicker } from "./setup/property-picker";

const NAMES = {
  gsc: "Search Console",
  ga4: "Google Analytics 4",
  report: "Weekly report",
} as const;

export function SiteConnectionForm({
  initial,
  status,
  ahrefs,
}: {
  initial: SiteConnection;
  status: SourceStatus | null;
  ahrefs: AhrefsData | null;
}) {
  const router = useRouter();
  const [connection, setConnection] = useState(initial);
  const [gsc, setGsc] = useState(initial.gsc_property ?? "");
  const [ga4, setGa4] = useState(initial.ga4_property_id ?? "");
  const [options, setOptions] = useState<ConnectionOptions | null>(null);
  const [tests, setTests] = useState<ConnectionTestResult | null>(null);
  const [pending, setPending] = useState<"" | "save" | "test" | "sync">("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const manage = connection.can_manage;
  const running = connection.sync.running;
  const dirty =
    (gsc.trim() || null) !== connection.gsc_property ||
    (ga4.trim() || null) !== connection.ga4_property_id;
  const ready =
    (!!connection.gsc_property && connection.credentials.gsc.configured) ||
    (!!connection.ga4_property_id && connection.credentials.ga4.configured);
  const states = {
    gsc: sourceState(connection, "gsc", tests?.gsc),
    ga4: sourceState(connection, "ga4", tests?.ga4),
    ahrefs:
      ahrefs?.web_analytics || ahrefs?.backlinks || ahrefs?.internal_links
        ? ("connected" as const)
        : ("off" as const),
  };
  const progress = setupProgress([states.gsc, states.ga4, states.ahrefs]);

  function failed(caught: unknown) {
    if (caught instanceof ApiError && caught.status === 401) {
      router.replace("/login");
      return;
    }
    setError(
      caught instanceof Error
        ? caught.message
        : "Something went wrong. Try again.",
    );
  }

  useEffect(() => {
    if (!manage) return;
    let active = true;
    api
      .connectionOptions(initial.slug)
      .then((result) => active && setOptions(result))
      .catch(
        () =>
          active &&
          setOptions({
            gsc: {
              properties: [],
              error: "Could not load the list. You can type the property.",
            },
            ga4: {
              properties: [],
              error: "Could not load the list. You can type the property ID.",
            },
          }),
      );
    return () => {
      active = false;
    };
  }, [manage, initial.slug]);

  useEffect(() => {
    if (!running) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const next = await api.connection(initial.slug);
        if (!active) return;
        setConnection(next);
        if (!next.sync.running) {
          router.refresh();
          return;
        }
      } catch (caught) {
        if (!active) return;
        if (caught instanceof ApiError && caught.status === 401) {
          router.replace("/login");
          return;
        }
        setError(
          "Could not refresh the sync progress. The sync may still be running; retrying.",
        );
      }
      if (active) timer = setTimeout(poll, 2000);
    }
    timer = setTimeout(poll, 2000);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [running, initial.slug, router]);

  async function save() {
    setPending("save");
    setError("");
    setNotice("");
    setTests(null);
    try {
      const next = await api.saveConnection(initial.slug, {
        gsc_property: gsc.trim() || null,
        ga4_property_id: ga4.trim() || null,
      });
      setConnection(next);
      setGsc(next.gsc_property ?? "");
      setGa4(next.ga4_property_id ?? "");
      setNotice("Saved. Test the connection, then sync your data.");
      router.refresh();
    } catch (caught) {
      failed(caught);
    } finally {
      setPending("");
    }
  }
  async function test() {
    setPending("test");
    setError("");
    setNotice("");
    try {
      setTests(await api.testConnection(initial.slug));
    } catch (caught) {
      failed(caught);
    } finally {
      setPending("");
    }
  }
  async function sync() {
    setPending("sync");
    setError("");
    setNotice("");
    try {
      const job = await api.syncSite(initial.slug);
      setConnection((current) => ({ ...current, sync: job }));
    } catch (caught) {
      failed(caught);
    } finally {
      setPending("");
    }
  }

  const busy = pending !== "" || running;
  const googleStep = (source: "gsc" | "ga4") => {
    const result = tests?.[source];
    return (
      <>
        <AccessBox source={source} info={connection.credentials[source]} />
        <PropertyPicker
          source={source}
          value={source === "gsc" ? gsc : ga4}
          onChange={source === "gsc" ? setGsc : setGa4}
          options={options ? options[source].properties : null}
          loading={manage && !options}
          error={options?.[source].error ?? null}
          disabled={!manage || busy}
        />
        {result && (
          <p
            role="status"
            className={`flex items-start gap-2 text-sm ${result.ok ? "text-good" : "text-bad"}`}
          >
            {result.ok ? (
              <CheckCircle2 size={16} aria-hidden className="mt-0.5 shrink-0" />
            ) : (
              <XCircle size={16} aria-hidden className="mt-0.5 shrink-0" />
            )}
            {result.message}
          </p>
        )}
        {status?.[source]?.last_loaded_date && (
          <p className="text-xs text-muted">
            Data loaded up to {formatDate(status[source]!.last_loaded_date)}.
          </p>
        )}
      </>
    );
  };

  return (
    <div className="space-y-5">
      <div className="panel p-5 sm:p-6">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <p className="font-semibold">
            {progress.done} of {progress.total} data sources connected
          </p>
          {!manage && (
            <p className="text-sm text-muted">
              View only: the website’s creator or an admin changes these
              settings.
            </p>
          )}
        </div>
        <div
          className="mt-3 h-2 overflow-hidden rounded-full bg-surface-muted"
          role="progressbar"
          aria-label="Data sources connected"
          aria-valuemin={0}
          aria-valuemax={progress.total}
          aria-valuenow={progress.done}
        >
          <div
            className="h-full rounded-full bg-brass"
            style={{ width: `${(progress.done / progress.total) * 100}%` }}
          />
        </div>
      </div>
      {error && (
        <p role="alert" className="rounded-md bg-bad-soft p-3 text-sm text-bad">
          {error}
        </p>
      )}
      <Step
        number={1}
        title="Google Search Console"
        description="Shows how people find this website on Google: searches, clicks, and positions."
        state={states.gsc}
      >
        {googleStep("gsc")}
      </Step>
      <Step
        number={2}
        title="Google Analytics 4"
        description="Shows what visitors do on the website: visits, visitors, and conversions."
        state={states.ga4}
      >
        {googleStep("ga4")}
      </Step>
      {manage && (
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            className="button button-primary"
            onClick={save}
            disabled={busy || !dirty}
          >
            {pending === "save" ? "Saving…" : "Save Google settings"}
          </button>
          <button
            type="button"
            className="button"
            onClick={test}
            disabled={
              busy ||
              dirty ||
              (!connection.gsc_property && !connection.ga4_property_id)
            }
          >
            {pending === "test" ? "Testing…" : "Test connection"}
          </button>
          {dirty && (
            <span className="text-sm text-muted">Save your changes first.</span>
          )}
          {notice && (
            <span role="status" className="text-sm text-good">
              {notice}
            </span>
          )}
        </div>
      )}
      <Step
        number={3}
        title="Ahrefs"
        description="Adds visitor tracking, backlinks, and site audit data from Ahrefs exports."
        state={states.ahrefs}
      >
        <ul className="space-y-1 text-sm">
          <li>
            Web Analytics:{" "}
            {ahrefs?.web_analytics
              ? `${formatDate(ahrefs.web_analytics.period_start)} – ${formatDate(ahrefs.web_analytics.period_end)}, imported ${formatTime(ahrefs.web_analytics.imported_at)}`
              : "not imported yet"}
          </li>
          <li>
            Backlinks:{" "}
            {ahrefs?.backlinks
              ? `${ahrefs.backlinks.rows} rows, imported ${formatTime(ahrefs.backlinks.imported_at)}`
              : "not imported yet"}
          </li>
          <li>
            Site Audit internal links:{" "}
            {ahrefs?.internal_links
              ? `${ahrefs.internal_links.rows} rows, imported ${formatTime(ahrefs.internal_links.imported_at)}`
              : "not imported yet"}
          </li>
        </ul>
        <Link
          href={`/sites/${encodeURIComponent(initial.slug)}?tab=ahrefs`}
          className="button"
        >
          Import Ahrefs data
        </Link>
      </Step>
      <section
        className="panel space-y-4 p-5 sm:p-6"
        aria-labelledby="sync-title"
      >
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 id="sync-title" className="text-lg font-semibold">
              Sync Google data
            </h2>
            <p className="mt-1 text-sm text-muted">
              Copies new days from Search Console and GA4 into SEOPs and updates
              the weekly report. The first sync can take several minutes.
            </p>
          </div>
          {manage && (
            <button
              type="button"
              className="button button-primary"
              onClick={sync}
              disabled={busy || dirty || !ready}
            >
              <RefreshCw
                size={15}
                aria-hidden
                className={running ? "motion-safe:animate-spin" : ""}
              />
              {running ? "Syncing…" : "Sync now"}
            </button>
          )}
        </div>
        {!ready && (
          <p className="text-sm text-warning">
            Connect Search Console or GA4 above before syncing.
          </p>
        )}
        <div role="status" className="space-y-2 text-sm">
          {running && (
            <p className="flex items-center gap-2">
              <StatusPill state="syncing" /> You can leave this page; finished
              days are saved as they arrive.
            </p>
          )}
          {Object.entries(connection.sync.results).map(([source, item]) => (
            <p
              key={source}
              className={item.status === "error" ? "text-bad" : "text-good"}
            >
              <strong>{NAMES[source as keyof typeof NAMES] ?? "Sync"}:</strong>{" "}
              {item.message}
            </p>
          ))}
        </div>
      </section>
    </div>
  );
}
