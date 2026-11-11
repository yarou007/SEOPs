"use client";

import { useState } from "react";
import { Check, Copy, ExternalLink } from "lucide-react";
import type { CredentialInfo } from "@/lib/types";

const STEPS = {
  gsc: {
    where:
      "In Search Console, open your property, then Settings, then Users and permissions. Add this email as a user (Full or Restricted).",
    guide: "https://support.google.com/webmasters/answer/7687615",
  },
  ga4: {
    where:
      "In Google Analytics, open Admin, then Property access management. Add this email with the Viewer role.",
    guide: "https://support.google.com/analytics/answer/9305788",
  },
};

/** "Give SEOPs access": the service-account email to add in Google, with a copy button. */
export function AccessBox({
  source,
  info,
}: {
  source: "gsc" | "ga4";
  info: CredentialInfo;
}) {
  const [copied, setCopied] = useState(false);
  if (!info.configured || !info.service_account_email)
    return (
      <p className="rounded-md bg-warning-soft p-3 text-sm text-warning">
        {info.message} An administrator sets this up once on the server.
      </p>
    );
  return (
    <div className="rounded-md bg-surface-muted p-4">
      <p className="text-sm font-medium">Give SEOPs read access</p>
      <p className="mt-1 text-sm text-muted">{STEPS[source].where}</p>
      <div className="mt-3 flex min-w-0 flex-wrap items-center gap-2">
        <code className="min-w-0 flex-1 select-all break-all rounded border border-border bg-surface px-3 py-2 text-xs">
          {info.service_account_email}
        </code>
        <button
          type="button"
          className="button text-xs"
          onClick={async () => {
            try {
              await navigator.clipboard.writeText(info.service_account_email!);
              setCopied(true);
              setTimeout(() => setCopied(false), 2000);
            } catch {
              setCopied(false);
            }
          }}
        >
          {copied ? (
            <Check size={14} aria-hidden />
          ) : (
            <Copy size={14} aria-hidden />
          )}
          {copied ? "Copied" : "Copy email"}
        </button>
      </div>
      <a
        className="mt-3 inline-flex items-center gap-1 text-xs text-accent hover:underline"
        href={STEPS[source].guide}
        target="_blank"
        rel="noreferrer"
      >
        Google’s help page <ExternalLink size={12} aria-hidden />
        <span className="sr-only">(opens in a new tab)</span>
      </a>
    </div>
  );
}
