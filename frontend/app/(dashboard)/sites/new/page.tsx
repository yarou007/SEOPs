import { serverApi, result } from "@/lib/server-api";
import { AddSiteForm } from "@/components/add-site-form";
import { GoogleSetup } from "@/components/google-setup";
import { ErrorState } from "@/components/states";
import { PageHeader } from "@/components/ui/page-header";

export const metadata = { title: "Add website" };
export default async function NewSite() {
  const setup = await result((await serverApi()).setup());
  return (
    <div className="mx-auto max-w-4xl space-y-7">
      <PageHeader
        title="Add a website"
        description="Add the website, connect its Google properties, then sync its data. The website is linked to your account."
      />
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
