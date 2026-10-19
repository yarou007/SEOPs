import Link from "next/link";
import { serverApi, result } from "@/lib/server-api";
import { formatDate } from "@/lib/format";
import { EmptyState, ErrorState } from "@/components/states";
import { SourceBadge } from "@/components/source-badge";

export const metadata = { title: "Sites" };
export default async function Sites() {
  const api = await serverApi();
  const list = await result(api.sites());
  if (!list.data)
    return <ErrorState message={list.error ?? "Could not load sites."} />;
  const sites = await Promise.all(
    list.data.map(async (site) => ({
      site,
      status: await result(api.status(site.slug)),
    })),
  );
  return (
    <div>
      <div className="mb-7 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Sites</h1>
          <p className="mt-1 text-muted">
            {sites.length} accessible {sites.length === 1 ? "site" : "sites"}.
            Select a site to review its performance.
          </p>
        </div>
        <Link href="/sites/new" className="button button-primary">
          Add website
        </Link>
      </div>
      {!sites.length ? (
        <EmptyState>No sites are linked to your account.</EmptyState>
      ) : (
        <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
          {sites.map(({ site, status }) => (
            <Link
              data-testid="site-card"
              key={site.slug}
              href={`/sites/${encodeURIComponent(site.slug)}`}
              className="panel block p-5 hover:border-accent"
            >
              <h2 className="break-words text-lg font-semibold [overflow-wrap:anywhere]">
                {site.display_name}
              </h2>
              <p className="mt-1 break-all text-sm text-muted">{site.domain}</p>
              <div className="mt-6 space-y-3">
                {status.data ? (
                  (["gsc", "ga4"] as const).map((source) => (
                    <div
                      key={source}
                      className="flex flex-wrap items-center justify-between gap-2 text-xs"
                    >
                      <span className="font-semibold">
                        {source === "gsc"
                          ? "Search Console"
                          : "Google Analytics 4"}
                      </span>
                      <div className="flex items-center gap-2">
                        <span className="text-muted">
                          {formatDate(status.data![source]?.last_loaded_date)}
                        </span>
                        <SourceBadge log={status.data![source]} />
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="text-xs text-bad">
                    Sync status unavailable: {status.error}
                  </p>
                )}
              </div>
              <p className="mt-6 border-t border-border pt-4 text-sm font-medium text-accent">
                Open dashboard →
              </p>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
