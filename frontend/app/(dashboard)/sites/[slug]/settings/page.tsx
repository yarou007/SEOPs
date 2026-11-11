import { serverApi, result } from "@/lib/server-api";
import { SiteConnectionForm } from "@/components/site-connection";
import { ErrorState } from "@/components/states";
import { PageHeader } from "@/components/ui/page-header";

export const metadata = { title: "Setup" };
export default async function SiteSettings({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const api = await serverApi();
  const connection = await result(api.connection(slug), true);
  if (!connection.data)
    return (
      <ErrorState
        message={connection.error ?? "Could not load this website’s settings."}
      />
    );
  const [status, ahrefs] = await Promise.all([
    result(api.status(slug)),
    result(api.ahrefs(slug)),
  ]);
  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader
        title="Connect your data"
        description={
          <>
            {connection.data.display_name}{" "}
            <span className="break-all">({connection.data.domain})</span>.
            Follow the steps in order; each one shows whether it is working.
          </>
        }
      />
      <SiteConnectionForm
        initial={connection.data}
        status={status.data}
        ahrefs={ahrefs.data}
      />
    </div>
  );
}
