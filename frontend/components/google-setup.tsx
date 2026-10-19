import type { SetupInfo } from "@/lib/types";

export function GoogleSetup({ credentials }: { credentials: SetupInfo }) {
  return (
    <section className="space-y-4" aria-labelledby="google-access">
      <h2 id="google-access" className="text-lg font-semibold">
        Give SEOPs access to your Google data
      </h2>
      <p className="text-sm text-muted">
        Your website must already be set up in Search Console or GA4. Saving a
        domain does not create Google properties or install analytics tracking.
      </p>
      <div className="grid gap-4 md:grid-cols-2">
        {(["gsc", "ga4"] as const).map((source) => {
          const info = credentials[source];
          return (
            <div key={source} className="panel space-y-3 p-5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="font-semibold">
                  {source === "gsc"
                    ? "Google Search Console"
                    : "Google Analytics 4"}
                </h3>
                <span
                  className={`badge ${info.configured ? "badge-good" : "badge-warning"}`}
                >
                  {info.configured
                    ? "Credentials ready"
                    : "Server setup needed"}
                </span>
              </div>
              <p className="text-sm text-muted">{info.message}</p>
              {info.service_account_email && (
                <div>
                  <p className="mb-1 text-xs font-medium text-muted">
                    Service account to add
                  </p>
                  <code className="block select-all break-all rounded bg-surface-muted p-3 text-xs">
                    {info.service_account_email}
                  </code>
                </div>
              )}
              <p className="text-sm">
                {source === "gsc"
                  ? "In Search Console, open your property → Settings → Users and permissions. Add the service account email as a user with access to performance data."
                  : "In Google Analytics, open Admin → Property access management. Add the service account email with the Viewer role."}
              </p>
              <a
                className="text-sm text-accent underline"
                href={
                  source === "gsc"
                    ? "https://support.google.com/webmasters/answer/7687615"
                    : "https://developers.google.com/analytics/devguides/reporting/data/v1/quickstart"
                }
                target="_blank"
                rel="noreferrer"
              >
                Google setup guide ↗
              </a>
            </div>
          );
        })}
      </div>
      <p className="text-xs text-muted">
        An administrator configures service account files on the server once and
        enables the Search Console API and Analytics Data API in Google Cloud.
        No Google password or private key is entered in this form.
      </p>
    </section>
  );
}
