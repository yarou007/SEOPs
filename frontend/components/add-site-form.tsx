"use client";
import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { ConnectionFields } from "./connection-fields";

export function AddSiteForm() {
  const router = useRouter();
  const [gsc, setGsc] = useState("");
  const [ga4, setGa4] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setPending(true);
    setError("");
    try {
      const site = await api.createSite({
        display_name: String(data.get("display_name")).trim(),
        domain: String(data.get("domain")).trim(),
        gsc_property: gsc.trim() || null,
        ga4_property_id: ga4.trim() || null,
      });
      router.push(`/sites/${encodeURIComponent(site.slug)}/settings`);
      router.refresh();
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        router.replace("/login");
        return;
      }
      setError(
        error instanceof Error
          ? error.message
          : "Could not add this website. Please try again.",
      );
      setPending(false);
    }
  }
  return (
    <form onSubmit={submit} className="panel space-y-6 p-5 sm:p-6">
      <div className="grid gap-5 sm:grid-cols-2">
        <div>
          <label htmlFor="display-name" className="mb-1.5 block font-medium">
            Website name
          </label>
          <input
            id="display-name"
            name="display_name"
            className="w-full"
            placeholder="My business"
            required
            maxLength={120}
            disabled={pending}
          />
        </div>
        <div>
          <label htmlFor="domain" className="mb-1.5 block font-medium">
            Website domain
          </label>
          <input
            id="domain"
            name="domain"
            className="w-full"
            placeholder="example.com"
            autoCapitalize="none"
            spellCheck={false}
            required
            maxLength={2048}
            disabled={pending}
            aria-describedby="domain-help"
          />
          <p id="domain-help" className="mt-2 text-xs text-muted">
            A domain or homepage URL. Use a separate website for each domain.
            The domain is fixed after creation.
          </p>
        </div>
      </div>
      <div className="border-t border-border pt-5">
        <h2 className="mb-4 font-semibold">Connect Google data</h2>
        <ConnectionFields
          gsc={gsc}
          ga4={ga4}
          setGsc={setGsc}
          setGa4={setGa4}
          disabled={pending}
        />
        <p className="mt-4 text-xs text-muted">
          You can fill these in later. Adding a website starts with an empty
          dashboard; data appears after a successful Google sync.
        </p>
      </div>
      {error && (
        <p role="alert" className="rounded-md bg-bad-soft p-3 text-sm text-bad">
          {error}
        </p>
      )}
      <div className="flex flex-wrap gap-3">
        <button
          className="button button-primary"
          type="submit"
          disabled={pending}
        >
          {pending ? "Adding…" : "Add website"}
        </button>
        <Link className="button" href="/sites">
          Cancel
        </Link>
      </div>
    </form>
  );
}
