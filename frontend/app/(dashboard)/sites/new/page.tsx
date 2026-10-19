import Link from "next/link";
import { serverApi, result } from "@/lib/server-api";
import { AddSiteForm } from "@/components/add-site-form";
import { GoogleSetup } from "@/components/google-setup";
import { ErrorState } from "@/components/states";

export const metadata = { title: "Add website" };
export default async function NewSite() {
  const setup = await result((await serverApi()).setup());
  return (
    <div className="mx-auto max-w-4xl space-y-7">
      <div>
        <Link className="text-sm text-muted hover:text-accent" href="/sites">
          ← All sites
        </Link>
        <h1 className="mt-4 text-2xl font-semibold tracking-tight">
          Add website
        </h1>
        <p className="mt-2 text-muted">
          Add your website, connect your Google properties, and import real
          performance data. The website will be linked to your account.
        </p>
      </div>
      <AddSiteForm />
      {setup.data ? (
        <GoogleSetup credentials={setup.data} />
      ) : (
        <ErrorState
          message={setup.error ?? "Could not load Google setup information."}
        />
      )}
    </div>
  );
}
