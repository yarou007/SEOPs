"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import type { SiteConnection } from "@/lib/types";
import { ConnectionFields } from "./connection-fields";
import { GoogleSetup } from "./google-setup";

export function SiteConnectionForm({ initial }: { initial: SiteConnection }) {
  const router = useRouter();
  const [connection, setConnection] = useState(initial);
  const [gsc, setGsc] = useState(initial.gsc_property ?? "");
  const [ga4, setGa4] = useState(initial.ga4_property_id ?? "");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const running = connection.sync.running;
  const dirty =
    (gsc.trim() || null) !== connection.gsc_property ||
    (ga4.trim() || null) !== connection.ga4_property_id;
  const ready =
    (!!connection.gsc_property && connection.credentials.gsc.configured) ||
    (!!connection.ga4_property_id && connection.credentials.ga4.configured);
  function failed(error: unknown) {
    if (error instanceof ApiError && error.status === 401) {
      router.replace("/login");
      return;
    }
    setError(
      error instanceof Error
        ? error.message
        : "Could not update this website. Please try again.",
    );
  }
  useEffect(() => {
    if (!running) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const next = await api.connection(initial.slug);
        if (!active) return;
        setConnection(next);
        setError("");
        if (!next.sync.running) {
          router.refresh();
          return;
        }
      } catch (error) {
        if (!active) return;
        if (error instanceof ApiError && error.status === 401) {
          router.replace("/login");
          return;
        }
        setError(
          "Could not refresh sync progress. The import may still be running; retrying…",
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
  async function save(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError("");
    setNotice("");
    try {
      const next = await api.saveConnection(initial.slug, {
        gsc_property: gsc.trim() || null,
        ga4_property_id: ga4.trim() || null,
      });
      setConnection(next);
      setGsc(next.gsc_property ?? "");
      setGa4(next.ga4_property_id ?? "");
      setNotice("Connections saved. Grant Google access below, then sync.");
      router.refresh();
    } catch (error) {
      failed(error);
    } finally {
      setPending(false);
    }
  }
  async function sync() {
    setPending(true);
    setError("");
    setNotice("");
    try {
      const job = await api.syncSite(initial.slug);
      setConnection((current) => ({ ...current, sync: job }));
    } catch (error) {
      failed(error);
    } finally {
      setPending(false);
    }
  }
  return (
    <div className="space-y-7">
      {error && (
        <p role="alert" className="rounded-md bg-bad-soft p-3 text-sm text-bad">
          {error}
        </p>
      )}
      <form onSubmit={save} className="panel space-y-5 p-5 sm:p-6">
        <h2 className="text-lg font-semibold">Google properties</h2>
        {!connection.can_manage && (
          <p className="text-sm text-muted">
            You can view this website. Only its creator or an admin can change
            connections and start imports.
          </p>
        )}
        <ConnectionFields
          gsc={gsc}
          ga4={ga4}
          setGsc={setGsc}
          setGa4={setGa4}
          disabled={!connection.can_manage || pending || running}
        />
        {connection.can_manage && (
          <button
            className="button"
            type="submit"
            disabled={pending || running}
          >
            {pending ? "Saving…" : "Save connections"}
          </button>
        )}
      </form>
      <GoogleSetup credentials={connection.credentials} />
      <section
        className="panel space-y-4 p-5 sm:p-6"
        aria-labelledby="sync-title"
      >
        <h2 id="sync-title" className="text-lg font-semibold">
          Import real data
        </h2>
        <p className="text-sm text-muted">
          Imports saved properties from Google and updates the weekly report.
          The first import can take several minutes as it loads historical data.
          Later imports resume from the last completed day.
        </p>
        {connection.can_manage && (
          <button
            type="button"
            className="button button-primary"
            onClick={sync}
            disabled={pending || running || dirty || !ready}
          >
            {running ? "Syncing real data…" : "Sync real data"}
          </button>
        )}
        {!ready && (
          <p className="text-sm text-warning">
            Save at least one property and complete the server credentials setup
            before importing.
          </p>
        )}
        {dirty && (
          <p className="text-sm text-muted">
            Save your connection changes before syncing.
          </p>
        )}
        <div role="status" className="space-y-2 text-sm">
          {running && (
            <p>
              Import is running. You can leave this page and return to check
              progress. Completed chunks are saved as they finish.
            </p>
          )}
          {Object.entries(connection.sync.results).map(([source, result]) => (
            <p
              key={source}
              className={result.status === "error" ? "text-bad" : "text-good"}
            >
              <strong>
                {source === "gsc"
                  ? "Search Console"
                  : source === "ga4"
                    ? "GA4"
                    : source === "report"
                      ? "Weekly report"
                      : "Sync"}
                :
              </strong>{" "}
              {result.message}
            </p>
          ))}
          {notice && <p className="text-good">{notice}</p>}
        </div>
        <div className="flex flex-wrap gap-4 text-sm">
          <Link
            className="text-accent underline"
            href={`/sites/${encodeURIComponent(initial.slug)}`}
          >
            Open dashboard
          </Link>
          <Link
            className="text-accent underline"
            href={`/sites/${encodeURIComponent(initial.slug)}?tab=status`}
          >
            View Data status
          </Link>
        </div>
      </section>
    </div>
  );
}
