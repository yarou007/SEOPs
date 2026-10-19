import Link from "next/link";
import { serverApi, result } from "@/lib/server-api";
import { SiteConnectionForm } from "@/components/site-connection";
import { ErrorState } from "@/components/states";

export const metadata = { title: "Data connections" };
export default async function SiteSettings({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const connection = await result((await serverApi()).connection(slug), true);
  if (!connection.data)
    return (
      <ErrorState
        message={connection.error ?? "Could not load website connections."}
      />
    );
  return (
    <div className="mx-auto max-w-4xl space-y-7">
      <div>
        <Link
          className="text-sm text-muted hover:text-accent"
          href={`/sites/${encodeURIComponent(slug)}`}
        >
          ← Dashboard
        </Link>
        <h1 className="mt-4 text-2xl font-semibold tracking-tight">
          Data connections
        </h1>
        <p className="mt-1 break-all text-muted">
          {connection.data.display_name} · {connection.data.domain}
        </p>
      </div>
      <SiteConnectionForm initial={connection.data} />
    </div>
  );
}
